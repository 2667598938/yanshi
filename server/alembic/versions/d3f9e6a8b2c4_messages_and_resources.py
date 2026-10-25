"""messages and resources

Revision ID: d3f9e6a8b2c4
Revises: c2e8d5f7a9b1
Create Date: 2026-10-25 10:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3f9e6a8b2c4'
down_revision: Union[str, None] = 'c2e8d5f7a9b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=24), nullable=False),
        sa.Column('title', sa.String(length=80), nullable=False),
        sa.Column('content', sa.String(length=500), server_default='', nullable=False),
        sa.Column('link', sa.String(length=200), server_default='', nullable=True),
        sa.Column('is_read', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('dedupe_key', sa.String(length=120), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'dedupe_key', name='uq_messages_user_dedupe')
    )
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_messages_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_messages_created_at'), ['created_at'], unique=False)

    op.create_table('resources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=80), nullable=False),
        sa.Column('url', sa.String(length=600), nullable=False),
        sa.Column('code', sa.String(length=20), server_default='', nullable=True),
        sa.Column('category', sa.String(length=20), server_default='', nullable=True),
        sa.Column('intro', sa.String(length=300), server_default='', nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_resources_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_resources_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_resources_created_at'), ['created_at'], unique=False)

    op.create_table('resource_likes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resource_id', 'user_id', name='uq_resource_like')
    )
    with op.batch_alter_table('resource_likes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_resource_likes_resource_id'), ['resource_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_resource_likes_user_id'), ['user_id'], unique=False)

    op.create_table('resource_favorites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('resource_id', 'user_id', name='uq_resource_favorite')
    )
    with op.batch_alter_table('resource_favorites', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_resource_favorites_resource_id'), ['resource_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_resource_favorites_user_id'), ['user_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('resource_favorites', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_resource_favorites_user_id'))
        batch_op.drop_index(batch_op.f('ix_resource_favorites_resource_id'))
    op.drop_table('resource_favorites')

    with op.batch_alter_table('resource_likes', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_resource_likes_user_id'))
        batch_op.drop_index(batch_op.f('ix_resource_likes_resource_id'))
    op.drop_table('resource_likes')

    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_resources_created_at'))
        batch_op.drop_index(batch_op.f('ix_resources_category'))
        batch_op.drop_index(batch_op.f('ix_resources_user_id'))
    op.drop_table('resources')

    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_messages_created_at'))
        batch_op.drop_index(batch_op.f('ix_messages_user_id'))
    op.drop_table('messages')
