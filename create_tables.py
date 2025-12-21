"""Helper script to create all tables.

Usage:
    export DATABASE_URL="mysql+pymysql://user:pass@localhost/hvac_ecommerce"
    python create_tables.py

Or use any SQLALCHEMY_DATABASE_URI that SQLAlchemy supports.
"""
import os
from app import app
from extensions import db
from models import (
    Vendor, Brand, Category, Attribute,
    Product, ProductVariant, ProductAttribute
)  # Import models so SQLAlchemy knows about them


def main():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        # Prefer Alembic migrations when Alembic is available
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

        # Drop all tables first (be careful - this deletes data!)
        db.drop_all()
        print("Dropped all tables")
        
        # Create all tables
        db.create_all()
        print("✅ Tables created successfully")


if __name__ == "__main__":
    main()