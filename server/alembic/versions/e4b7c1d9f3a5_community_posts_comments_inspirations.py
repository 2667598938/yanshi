"""community posts comments inspirations

Revision ID: e4b7c1d9f3a5
Revises: d3f9e6a8b2c4
Create Date: 2026-10-25 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4b7c1d9f3a5'
down_revision: Union[str, None] = 'd3f9e6a8b2c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.String(length=2000), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_posts_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_posts_created_at'), ['created_at'], unique=False)

    op.create_table('comments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('reply_to_user_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.String(length=500), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reply_to_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_comments_post_id'), ['post_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comments_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_comments_parent_id'), ['parent_id'], unique=False)

    op.create_table('inspirations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content', sa.String(length=200), server_default='', nullable=False),
        sa.Column('image_key', sa.String(length=300), server_default='', nullable=True),
        sa.Column('status', sa.String(length=16), server_default='pending', nullable=False),
        sa.Column('review_note', sa.String(length=300), server_default='', nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('inspirations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_inspirations_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_inspirations_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_inspirations_created_at'), ['created_at'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('inspirations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_inspirations_created_at'))
        batch_op.drop_index(batch_op.f('ix_inspirations_status'))
        batch_op.drop_index(batch_op.f('ix_inspirations_user_id'))
    op.drop_table('inspirations')

    with op.batch_alter_table('comments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_comments_parent_id'))
        batch_op.drop_index(batch_op.f('ix_comments_user_id'))
        batch_op.drop_index(batch_op.f('ix_comments_post_id'))
    op.drop_table('comments')

    with op.batch_alter_table('posts', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_posts_created_at'))
        batch_op.drop_index(batch_op.f('ix_posts_user_id'))
    op.drop_table('posts')
