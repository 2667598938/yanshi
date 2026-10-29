"""Community revision and retained favorite tombstones."""
from alembic import op
import sqlalchemy as sa
revision = 'b5d7f9a1c3e5'
down_revision = 'a4c6e8f0b2d4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('posts', sa.Column('revision', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('resource_favorites', sa.Column('active', sa.Boolean(), nullable=False, server_default='1'))
    op.add_column('resource_favorites', sa.Column('revision', sa.Integer(), nullable=False, server_default='1'))


def downgrade():
    op.drop_column('resource_favorites', 'revision')
    op.drop_column('resource_favorites', 'active')
    op.drop_column('posts', 'revision')
