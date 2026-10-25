"""oauth channels and phone binding

Revision ID: c2e8d5f7a9b1
Revises: b1f7c2d4e6a8
Create Date: 2026-10-25 09:10:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2e8d5f7a9b1'
down_revision: Union[str, None] = 'b1f7c2d4e6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone', sa.String(length=20), nullable=True))
        batch_op.create_unique_constraint('uq_users_phone', ['phone'])

    op.create_table('user_auth',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=16), nullable=False),
        sa.Column('provider_uid', sa.String(length=128), nullable=False),
        sa.Column('nickname', sa.String(length=40), server_default='', nullable=True),
        sa.Column('avatar_url', sa.String(length=500), server_default='', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'provider_uid', name='uq_user_auth_provider_uid')
    )
    with op.batch_alter_table('user_auth', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_auth_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('user_auth', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_auth_user_id'))
    op.drop_table('user_auth')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('uq_users_phone', type_='unique')
        batch_op.drop_column('phone')
