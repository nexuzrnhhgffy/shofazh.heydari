# shofazh.heydari

## Database & Migrations 🔧

This project uses **Flask-SQLAlchemy** for models and **Alembic** for schema migrations.

- Set your DB connection (example MySQL):

```bash
export DATABASE_URL="mysql+pymysql://user:pass@host/dbname"
```

- To create and apply an initial migration (autogenerate from models):

```bash
pip install alembic
python migrate_initial.py
# or using alembic directly:
# alembic revision --autogenerate -m "initial"
# alembic upgrade head
```

- If Alembic isn't available, `create_tables.py` falls back to a destructive `drop_all()` + `create_all()` (DO NOT RUN in production unless you know what you're doing):

```bash
python create_tables.py
```

- To seed sample data after the schema exists:

```bash
python seed_sample_data.py
```

Notes:
- `migrate_initial.py` will create an `alembic/versions` revision if none exists, then run `upgrade head`.
- The Alembic environment reads `DATABASE_URL` if present; otherwise it uses the app's default DB configuration.
