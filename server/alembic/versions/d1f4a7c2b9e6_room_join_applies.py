"""room join applies

Revision ID: d1f4a7c2b9e6
Revises: c8e1a5b3d7f0
Create Date: 2026-10-25 20:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1f4a7c2b9e6'
down_revision: Union[str, None] = 'c8e1a5b3d7f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'room_join_applies',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('room_id', sa.Integer(), sa.ForeignKey('rooms.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('status', sa.String(length=12), server_default='pending', nullable=False),
        sa.Column('message', sa.String(length=200), server_default='', nullable=False),
        # 仅待审申请有值，审批后置 NULL；唯一约束保证同一房间同一人只有一条 pending
        sa.Column('pending_key', sa.String(length=40), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('handled_at', sa.DateTime(), nullable=True),
        sa.Column('handled_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.UniqueConstraint('pending_key', name='uq_room_join_pending_key'),
    )
    op.create_index('ix_room_join_applies_room_status', 'room_join_applies',
                    ['room_id', 'status'])
    op.create_index('ix_room_join_applies_user_id', 'room_join_applies', ['user_id'])
    op.create_index('ix_room_join_applies_created_at', 'room_join_applies', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_room_join_applies_created_at', table_name='room_join_applies')
    op.drop_index('ix_room_join_applies_user_id', table_name='room_join_applies')
    op.drop_index('ix_room_join_applies_room_status', table_name='room_join_applies')
    op.drop_table('room_join_applies')
