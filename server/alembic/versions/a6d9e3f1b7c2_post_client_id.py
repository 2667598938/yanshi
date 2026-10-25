"""post client_id for offline idempotent publishing

Revision ID: a6d9e3f1b7c2
Revises: f5c8d2e0a4b6
Create Date: 2026-10-25 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a6d9e3f1b7c2'
down_revision: Union[str, None] = 'f5c8d2e0a4b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('client_id', sa.String(length=64), nullable=True))
        batch_op.create_index('uq_posts_user_client', ['user_id', 'client_id'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_index('uq_posts_user_client')
        batch_op.drop_column('client_id')
