#!/usr/bin/env python3
"""
Autogenerate an Alembic revision (if any changes) and apply migrations.
Usage:
  python scripts/auto_migrate.py [--message "msg"] [DATABASE_URL]

If DATABASE_URL is provided as the first arg it will be used, otherwise env var is used.
"""
import os
import sys
from alembic.config import Config
from alembic import command
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = ROOT / "alembic.ini"
if not ALEMBIC_INI.exists():
    print("alembic.ini not found in project root.")
    sys.exit(1)

cfg = Config(str(ALEMBIC_INI))

# accept DATABASE_URL as first positional arg
database_url = os.environ.get("DATABASE_URL")
if len(sys.argv) > 1 and not sys.argv[1].startswith("--"):
    database_url = sys.argv[1]

if database_url:
    cfg.set_main_option("sqlalchemy.url", database_url)

# message
msg = "autogenerate"
for i, a in enumerate(sys.argv[1:], start=1):
    if a.startswith("--message"):
        # allow --message "text" or --message=text
        if a == "--message" and len(sys.argv) > i:
            msg = sys.argv[i]
        else:
            parts = a.split("=", 1)
            if len(parts) == 2:
                msg = parts[1]

# run autogenerate revision
print("Creating autogenerate revision (if there are changes)...")
try:
    command.revision(cfg, message=msg, autogenerate=True)
except Exception as e:
    print("Revision generation failed:", e)
    # continue to upgrade attempt (may be no-op)

# upgrade head
print("Applying migrations: alembic upgrade head")
try:
    command.upgrade(cfg, "head")
    print("Migrations applied.")
except Exception as e:
    print("Upgrade failed:", e)
    sys.exit(1)
