#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import subprocess
import platform
from pathlib import Path
from typing import Optional


ROOT = Path(__file__).resolve().parent


def which_python_in_venv(venv_path: Path) -> Path:
    if platform.system() == "Windows":
        return venv_path / "Scripts" / "python.exe"
    else:
        return venv_path / "bin" / "python"


def create_or_use_venv(venv_names=("venv", ".venv")) -> Path:
    for name in venv_names:
        venv_path = ROOT / name
        py = which_python_in_venv(venv_path)
        if py.exists():
            print(f"✓ Using existing virtualenv: {venv_path}")
            return py

    venv_path = ROOT / "venv"
    print(f"Creating virtualenv at: {venv_path}")
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_path)])
    py = which_python_in_venv(venv_path)
    if not py.exists():
        raise RuntimeError("Failed to create venv")
    print("✓ Virtualenv created")
    return py


def run_subprocess(cmd, env=None, check=True, capture_output=False):
    print("$", " ".join(map(str, cmd)))
    kwargs = {"env": env or os.environ.copy(), "check": check}
    if capture_output:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def ensure_requirements(venv_python: Path):
    req = ROOT / "requirements.txt"
    if not req.exists():
        print("⚠ No requirements.txt found; skipping pip install")
        return
    print("Installing requirements...")
    run_subprocess([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    run_subprocess([str(venv_python), "-m", "pip", "install", "-r", str(req)])
    print("✓ Requirements installed")


def install_in_venv(venv_python: Path, package: str):
    print(f"Installing {package} into venv...")
    try:
        run_subprocess([str(venv_python), "-m", "pip", "install", package])
        print(f"✓ {package} installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install {package}: {e}")
        return False


def get_database_url_from_env_or_args_or_prompt() -> str:
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        print("✓ Using DATABASE_URL from environment")
        return env_url

    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg:
            print("✓ Using DATABASE_URL from command-line argument")
            return arg

    from urllib.parse import urlparse

    attempts = 3
    for _ in range(attempts):
        val = input("Enter DATABASE_URL (mysql+pymysql://user:pass@host:3306/dbname): ").strip()
        if not val:
            print("Empty input, try again")
            continue
        parsed = urlparse(val)
        if parsed.scheme and parsed.path and parsed.hostname:
            return val
        print("Invalid URL format, try again")
    raise SystemExit("ERROR: No valid DATABASE_URL provided")


def persist_env_var(key: str, value: str):
    os.environ[key] = value
    if platform.system() == "Windows":
        try:
            subprocess.run(["setx", key, value], check=True, capture_output=True)
            print(f"✓ Persisted {key} to Windows user environment")
        except Exception:
            print(f"⚠ Could not persist {key} with setx")
    else:
        env_file = ROOT / ".env"
        try:
            existing_content = ""
            if env_file.exists():
                existing_content = env_file.read_text(encoding="utf-8")
            
            if f"{key}=" not in existing_content:
                with open(env_file, "a", encoding="utf-8") as f:
                    f.write(f"\n{key}={value}\n")
                print(f"✓ Added {key} to .env file")
            else:
                print(f"⚠ {key} already in .env file")
        except Exception as e:
            print(f"⚠ Could not write .env: {e}")


def ensure_database_exists(database_url: str, venv_python: Path) -> None:
    print("Checking database...")
    check_script = f"""
from sqlalchemy.engine.url import make_url
from sqlalchemy import create_engine, text

url = make_url(r'{database_url}')
dbname = url.database
if not dbname:
    raise SystemExit('ERROR: No database name in URL')

server_url = url.set(database=None)
engine = create_engine(str(server_url))

with engine.connect() as conn:
    conn.execute(text("CREATE DATABASE IF NOT EXISTS `{{}}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci".format(dbname)))
print('✓ Database ready')
"""
    python_exec = str(venv_python)
    attempts = 2
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            result = run_subprocess([python_exec, "-c", check_script], capture_output=True, check=True)
            out = (result.stdout or "").strip()
            if out:
                print(out)
            print("✓ Database check/create succeeded")
            return
        except subprocess.CalledProcessError as e:
            last_exc = e
            stdout = e.stdout or ""
            stderr = e.stderr or ""
            combined = (stdout + "\n" + stderr).lower()
            print("ERROR: Database check failed (attempt", attempt, "):")
            if stdout:
                print("--- stdout ---")
                print(stdout.strip())
            if stderr:
                print("--- stderr ---")
                print(stderr.strip())

            # Auto-fix: missing pymysql driver
            if "no module named 'pymysql'" in combined or "modulenotfounderror: no module named 'pymysql'" in combined:
                print("Detected missing 'pymysql' driver. Attempting to install in venv...")
                ok = install_in_venv(venv_python, "pymysql")
                if ok and attempt < attempts:
                    print("Retrying database creation...")
                    continue
                else:
                    print("Please ensure 'pymysql' is installed in the venv and try again.")
                    break

            # Access/permission issues
            if "access denied for user" in combined or "(1045," in combined:
                print("Access denied: check username/password and privileges for the database user.")
                print("Suggestion: verify credentials and that the user has CREATE DATABASE privilege.")
                break

            # Connection issues
            if "can't connect to" in combined or "connection refused" in combined or "2003" in combined or "can't connect" in combined:
                print("Connection error: unable to reach MySQL server.")
                print("- Verify host/port and that MySQL is running and accessible from this machine.")
                print("- If using 127.0.0.1, ensure MySQL listens on TCP (not only socket).")
                break

            # Other errors: show message and stop
            print("Unhandled database error; see output above for details.")
            break
    # if reached here, raise last exception to abort
    if last_exc:
        raise last_exc


def run_alembic(venv_python: Path, database_url: str) -> bool:
    if not (ROOT / "alembic.ini").exists():
        print("⚠ No alembic.ini found; skipping migrations")
        return True
    
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    print("Running Alembic migrations...")
    try:
        run_subprocess([str(venv_python), "-m", "alembic", "upgrade", "head"], env=env)
        print("✓ Migrations complete")
        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Alembic migration failed: {e}")
        return False


def run_seed_scripts(venv_python: Path):
    seeds = ["seed_site_settings.py", "seed_sample_data.py"]
    for s in seeds:
        p = ROOT / s
        if p.exists():
            print(f"Running seed script: {s}")
            try:
                run_subprocess([str(venv_python), str(p)])
                print(f"✓ {s} completed")
            except subprocess.CalledProcessError as e:
                print(f"ERROR: Seed script {s} failed: {e}")


def start_application(venv_python: Path, database_url: str):
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url
    
    app_py = ROOT / "app.py"
    if not app_py.exists():
        print("ERROR: No app.py found; cannot start application")
        return
    
    content = app_py.read_text(encoding="utf-8").lower()
    
    if "fastapi" in content or "from fastapi" in content:
        cmd = [str(venv_python), "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
        print("\n" + "="*60)
        print("Starting FastAPI on http://0.0.0.0:8000")
        print("="*60 + "\n")
    elif "flask" in content or "from flask" in content:
        env["FLASK_APP"] = "app.py"
        env["FLASK_ENV"] = "development"
        cmd = [str(venv_python), "-m", "flask", "run", "--host=0.0.0.0"]
        print("\n" + "="*60)
        print("Starting Flask on http://0.0.0.0:5000")
        print("="*60 + "\n")
    else:
        cmd = [str(venv_python), str(app_py)]
        print("\n" + "="*60)
        print("Starting application: python app.py")
        print("="*60 + "\n")

    try:
        run_subprocess(cmd, env=env, check=True)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Application failed to start: {e}")
    except KeyboardInterrupt:
        print("\n\nShutting down...")


def main():
    print("\n" + "="*60)
    print("PROJECT SETUP & RUN")
    print("="*60 + "\n")
    print(f"Working directory: {ROOT}\n")

    try:
        venv_python = create_or_use_venv()
        ensure_requirements(venv_python)
        database_url = get_database_url_from_env_or_args_or_prompt()
        persist_env_var("DATABASE_URL", database_url)
        ensure_database_exists(database_url, venv_python=venv_python)
        run_alembic(venv_python, database_url)
        run_seed_scripts(venv_python)
        start_application(venv_python, database_url)
    except KeyboardInterrupt:
        print("\n\nSetup interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
