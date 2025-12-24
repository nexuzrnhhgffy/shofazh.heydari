"""
Helper script to create all tables (Windows-compatible).

Usage (PowerShell):
    $env:DATABASE_URL="mysql+pymysql://user:pass@localhost/hvac_ecommerce"
    python create_tables.py
"""

import os
from app import app
from extensions import db
from models import (
    Vendor, Brand, Category, Attribute,
    Product, ProductVariant, ProductAttribute
)  # Import models so SQLAlchemy knows about them


def main():
    # Get database URL from environment variable
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return

    print("Using DATABASE_URL:", database_url)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        # Try Alembic first
        try:
            from alembic.config import Config
            from alembic import command

            print('Alembic detected — applying migrations (upgrade head)')
            cfg = Config('alembic.ini')
            command.upgrade(cfg, 'head')
            print('✅ Alembic migrations applied (upgrade head)')
            return
        except Exception:
            print('Alembic not available or failed — falling back to drop/create (destructive)')

        # Drop all tables first
        db.drop_all()
        print("Dropped all tables")

        # Create all tables
        db.create_all()
        print("✅ Tables created successfully")


if __name__ == "__main__":
    main()
