"""add is_active to site_settings

Revision ID: 20251224_add_site_settings_is_active
Revises: 
Create Date: 2025-12-24 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251224_add_site_settings_is_active'
down_revision = 'e12cea3080d1'
branch_labels = None
depends_on = None


def upgrade():
    # add column with server default True so existing rows become active
    op.add_column('site_settings', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')))
    op.add_column('site_settings', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
    # remove server defaults (optional)
    with op.get_context().autocommit_block():
        op.alter_column('site_settings', 'is_active', server_default=None)
        op.alter_column('site_settings', 'sort_order', server_default=None)


def downgrade():
    op.drop_column('site_settings', 'sort_order')
    op.drop_column('site_settings', 'is_active')
