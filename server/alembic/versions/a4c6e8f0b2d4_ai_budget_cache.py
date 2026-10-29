"""Persistent daily AI budget and model catalog cache."""
from alembic import op
import sqlalchemy as sa

revision = 'a4c6e8f0b2d4'
down_revision = 'f3b5d7e9a1c2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_usage_daily',
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('day', sa.String(10), primary_key=True),
        *[sa.Column(name, sa.Integer(), nullable=False, server_default='0') for name in
          ('requests', 'succeeded', 'failed', 'prompt_tokens', 'completion_tokens')])
    op.create_table('ai_model_cache',
        sa.Column('cache_key', sa.String(64), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('models_json', sa.Text(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(), nullable=False))
    op.create_index('ix_ai_model_cache_user_id', 'ai_model_cache', ['user_id'])


def downgrade():
    op.drop_index('ix_ai_model_cache_user_id', table_name='ai_model_cache')
    op.drop_table('ai_model_cache')
    op.drop_table('ai_usage_daily')
