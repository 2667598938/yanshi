"""vip fields and feature requests

Revision ID: 7d3a1f9b2c4e
Revises: 39eceb792b2e
Create Date: 2026-10-24 23:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7d3a1f9b2c4e'
down_revision: Union[str, None] = '39eceb792b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vip_until', sa.DateTime(), nullable=True))

    with op.batch_alter_table('invite_codes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vip_days', sa.Integer(), server_default='0', nullable=False))

    op.create_table('feature_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('feature', sa.String(length=40), nullable=False),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
        sa.Column('review_note', sa.String(length=300), server_default='', nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('feature_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_feature_requests_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_feature_requests_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_feature_requests_created_at'), ['created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('feature_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_feature_requests_created_at'))
        batch_op.drop_index(batch_op.f('ix_feature_requests_status'))
        batch_op.drop_index(batch_op.f('ix_feature_requests_user_id'))

    op.drop_table('feature_requests')

    with op.batch_alter_table('invite_codes', schema=None) as batch_op:
        batch_op.drop_column('vip_days')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('vip_until')
