"""add is_active to site_settings

Revision ID: a1b2c3d4
Revises: e12cea3080d1
Create Date: 2025-12-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4'
down_revision = 'e12cea3080d1'
branch_labels = None
depends_on = None


def upgrade():
    # add column with server default True so existing rows become active
    try:
        op.add_column('site_settings', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')))
    except Exception:
        # column may already exist
        pass
    try:
        op.add_column('site_settings', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
    except Exception:
        pass
    # remove server defaults (optional)
    try:
        with op.get_context().autocommit_block():
            try:
                op.alter_column('site_settings', 'is_active', server_default=None)
            except Exception:
                pass
            try:
                op.alter_column('site_settings', 'sort_order', server_default=None)
            except Exception:
                pass
    except Exception:
        pass


def downgrade():
    op.drop_column('site_settings', 'sort_order')
    op.drop_column('site_settings', 'is_active')
