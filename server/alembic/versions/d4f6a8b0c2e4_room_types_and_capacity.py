"""Replace legacy room variants with text / AV and preserve memberships and data."""
from alembic import op
import sqlalchemy as sa
revision = 'd4f6a8b0c2e4'
down_revision = 'f0c3a7b9d2e4'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table('rooms') as batch:
        batch.add_column(sa.Column('media_mode',sa.String(12),nullable=False,server_default=''))
        batch.alter_column('capacity',existing_type=sa.Integer(),server_default='50')
        batch.alter_column('room_type',existing_type=sa.String(24),server_default='text_room')
    op.execute("UPDATE rooms SET room_type='text_room',capacity=CASE WHEN capacity<=4 THEN MAX(50,(SELECT COUNT(*) FROM room_members WHERE room_id=rooms.id)) ELSE capacity END WHERE room_type='checkin_room'")
    op.execute("UPDATE rooms SET room_type='av_room',media_mode='mesh',capacity=MAX(6,(SELECT COUNT(*) FROM room_members WHERE room_id=rooms.id)) WHERE room_type='video_small_room'")
    op.execute("UPDATE rooms SET room_type='av_room',media_mode='sfu',capacity=MAX(25,(SELECT COUNT(*) FROM room_members WHERE room_id=rooms.id)) WHERE room_type='cloud_video_room'")
    op.execute("UPDATE rooms SET name='研时 · 文字自习室' WHERE name='研时 · 四人自习室'")

def downgrade():
    # Retain increased capacity; shrinking it would invalidate existing memberships.
    op.execute("UPDATE rooms SET room_type=CASE WHEN media_mode='sfu' THEN 'cloud_video_room' ELSE 'video_small_room' END WHERE room_type='av_room'")
    op.execute("UPDATE rooms SET room_type='checkin_room' WHERE room_type='text_room'")
    with op.batch_alter_table('rooms') as batch:
        batch.drop_column('media_mode')
        batch.alter_column('room_type',existing_type=sa.String(24),server_default='checkin_room')
        batch.alter_column('capacity',existing_type=sa.Integer(),server_default='0')
