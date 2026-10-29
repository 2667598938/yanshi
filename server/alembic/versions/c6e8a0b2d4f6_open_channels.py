"""Room variants and shared encrypted transient state."""
from alembic import op
import sqlalchemy as sa
revision = 'c6e8a0b2d4f6'
down_revision = 'b5d7f9a1c3e5'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('rooms', sa.Column('room_type', sa.String(24), nullable=False, server_default='checkin_room'))
    op.create_table('transient_states',
        sa.Column('state_key', sa.String(200), primary_key=True),
        sa.Column('value_cipher', sa.Text(), nullable=False),
        sa.Column('expires_at', sa.Float(), nullable=False))
    op.create_index('ix_transient_states_expires_at', 'transient_states', ['expires_at'])


def downgrade():
    op.drop_index('ix_transient_states_expires_at', table_name='transient_states')
    op.drop_table('transient_states')
    op.drop_column('rooms', 'room_type')
