"""Incremental learning sync cursor; existing clients retain full-snapshot support."""
from alembic import op
import sqlalchemy as sa

revision = 'e2a4c6d8f0b1'
down_revision = 'd1f4a7c2b9e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('learning_changes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('record_id', sa.String(500), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False))
    op.create_index('ix_learning_changes_user_id', 'learning_changes', ['user_id'])


def downgrade():
    op.drop_index('ix_learning_changes_user_id', table_name='learning_changes')
    op.drop_table('learning_changes')
