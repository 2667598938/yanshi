"""profile, error types, ai byok

Revision ID: b1f7c2d4e6a8
Revises: 7d3a1f9b2c4e
Create Date: 2026-10-25 01:20:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1f7c2d4e6a8'
down_revision: Union[str, None] = '7d3a1f9b2c4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('signature', sa.String(length=80),
                                      server_default='', nullable=True))
        batch_op.add_column(sa.Column('figure_id', sa.String(length=24),
                                      server_default='figure-1', nullable=True))

    with op.batch_alter_table('ai_messages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('prompt_tokens', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('completion_tokens', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('latency_ms', sa.Integer(), nullable=True))

    op.create_table('user_error_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', name='uq_user_error_type')
    )
    with op.batch_alter_table('user_error_types', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_error_types_user_id'), ['user_id'], unique=False)

    op.create_table('user_ai_keys',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=24), nullable=False),
        sa.Column('base_url', sa.String(length=200), nullable=False),
        sa.Column('model', sa.String(length=120), server_default='', nullable=True),
        sa.Column('key_cipher', sa.Text(), nullable=False),
        sa.Column('key_mask', sa.String(length=40), server_default='', nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('user_ai_keys')

    with op.batch_alter_table('user_error_types', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_error_types_user_id'))
    op.drop_table('user_error_types')

    with op.batch_alter_table('ai_messages', schema=None) as batch_op:
        batch_op.drop_column('latency_ms')
        batch_op.drop_column('completion_tokens')
        batch_op.drop_column('prompt_tokens')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('figure_id')
        batch_op.drop_column('signature')
