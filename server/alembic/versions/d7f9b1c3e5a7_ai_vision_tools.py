"""AI images, bounded tools and conversation request leases."""
from alembic import op
import sqlalchemy as sa
revision = 'd7f9b1c3e5a7'
down_revision = 'c6e8a0b2d4f6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('ai_model_cache', sa.Column('details_json', sa.Text(), nullable=False, server_default='[]'))
    op.add_column('ai_conversations', sa.Column('busy_until', sa.DateTime()))
    op.add_column('ai_conversations', sa.Column('request_token', sa.String(64)))
    op.add_column('ai_messages', sa.Column('image_keys', sa.Text(), nullable=False, server_default='[]'))
    op.add_column('ai_messages', sa.Column('tool_trace', sa.Text(), nullable=False, server_default='{}'))
    op.add_column('user_ai_keys', sa.Column('supports_images', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('user_ai_keys', sa.Column('supports_tools', sa.Boolean(), nullable=False, server_default='0'))


def downgrade():
    op.drop_column('ai_model_cache', 'details_json')
    for name in ('supports_tools', 'supports_images'): op.drop_column('user_ai_keys', name)
    for name in ('tool_trace', 'image_keys'): op.drop_column('ai_messages', name)
    for name in ('request_token', 'busy_until'): op.drop_column('ai_conversations', name)
