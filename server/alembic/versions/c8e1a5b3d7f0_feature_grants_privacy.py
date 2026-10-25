"""feature grants and privacy mode

Revision ID: c8e1a5b3d7f0
Revises: a6d9e3f1b7c2
Create Date: 2026-10-25 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8e1a5b3d7f0'
down_revision: Union[str, None] = 'a6d9e3f1b7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('privacy_mode', sa.Boolean(),
                                      server_default='0', nullable=False))

    op.create_table(
        'user_feature_grants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('feature', sa.String(length=40), nullable=False),
        sa.Column('source_request_id', sa.Integer(), nullable=True),
        sa.Column('granted_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('granted_at', sa.DateTime(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('user_id', 'feature', name='uq_grant_user_feature'),
    )
    op.create_index('ix_user_feature_grants_user_id', 'user_feature_grants', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_user_feature_grants_user_id', table_name='user_feature_grants')
    op.drop_table('user_feature_grants')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('privacy_mode')
