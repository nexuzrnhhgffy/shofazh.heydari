"""Helper to autogenerate an initial Alembic revision and apply it.

Usage:
    export DATABASE_URL="mysql+pymysql://user:pass@host/db"
    python migrate_initial.py
"""
import os
import sys
from pathlib import Path

try:
    from alembic.config import Config
    from alembic import command
except Exception as exc:
    print("Alembic not installed. Install it with `pip install alembic` and re-run.")
    raise


def run():
    project_root = Path(__file__).resolve().parent
    alembic_ini = project_root / 'alembic.ini'
    if not alembic_ini.exists():
        raise RuntimeError('Missing alembic.ini in project root')

    cfg = Config(str(alembic_ini))
    # let env.py set the URL from DATABASE_URL or app config

    # Ensure versions directory exists
    versions_dir = project_root / 'alembic' / 'versions'
    versions_dir.mkdir(parents=True, exist_ok=True)

    # If there are no existing revisions, autogenerate an initial one
    if not any(versions_dir.iterdir()):
        print('No revisions found — creating initial autogenerate revision...')
        command.revision(cfg, message='initial schema', autogenerate=True)
        print('Revision created.')
    else:
        print('Existing revisions found; skipping revision creation.')

    print('Upgrading database to head...')
    command.upgrade(cfg, 'head')
    print('Database upgraded to head.\n')


if __name__ == '__main__':
    run()
