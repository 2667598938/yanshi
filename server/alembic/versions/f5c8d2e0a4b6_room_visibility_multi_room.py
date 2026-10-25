"""room visibility for multi-room

Revision ID: f5c8d2e0a4b6
Revises: e4b7c1d9f3a5
Create Date: 2026-10-25 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f5c8d2e0a4b6'
down_revision: Union[str, None] = 'e4b7c1d9f3a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('rooms', schema=None) as batch_op:
        batch_op.add_column(sa.Column('visibility', sa.String(length=12),
                                      server_default='public', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('rooms', schema=None) as batch_op:
        batch_op.drop_column('visibility')
