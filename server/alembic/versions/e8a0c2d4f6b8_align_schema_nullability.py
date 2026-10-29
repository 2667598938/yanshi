"""Align historical AI key mask nullability with the model without losing key ciphertext."""
from alembic import op
import sqlalchemy as sa
revision = 'e8a0c2d4f6b8'
down_revision = 'd7f9b1c3e5a7'
branch_labels = None
depends_on = None


def upgrade():
    keys = sa.table('user_ai_keys', sa.column('key_mask', sa.String(40)))
    op.get_bind().execute(keys.update().where(keys.c.key_mask.is_(None)).values(key_mask=''))
    with op.batch_alter_table('user_ai_keys') as batch:
        batch.alter_column('key_mask', existing_type=sa.String(40), nullable=False)


def downgrade():
    with op.batch_alter_table('user_ai_keys') as batch:
        batch.alter_column('key_mask', existing_type=sa.String(40), nullable=True)
