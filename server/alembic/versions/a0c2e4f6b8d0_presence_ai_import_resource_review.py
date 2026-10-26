"""Device presence, durable AI import receipts and moderated resources."""
from alembic import op
import sqlalchemy as sa
revision='a0c2e4f6b8d0'
down_revision='f9b1d3e5a7c9'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('announcements') as b:
        b.add_column(sa.Column('revision',sa.Integer(),nullable=False,server_default='1'))
    with op.batch_alter_table('audit_logs') as b:
        b.add_column(sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id',name='fk_audit_actor')))
    op.create_table('device_presence',sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),primary_key=True),
        sa.Column('device_id',sa.String(80),primary_key=True),sa.Column('room_id',sa.Integer(),sa.ForeignKey('rooms.id')),
        sa.Column('status',sa.String(12),nullable=False),sa.Column('detail',sa.Text(),nullable=False),
        sa.Column('entered_at',sa.DateTime(),nullable=False),sa.Column('heartbeat_at',sa.DateTime(),nullable=False))
    op.create_index('ix_device_presence_heartbeat_at','device_presence',['heartbeat_at'])
    op.create_table('ai_task_imports',sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),primary_key=True),
        sa.Column('message_id',sa.Integer(),primary_key=True),sa.Column('selection',sa.Text(),nullable=False),
        sa.Column('tasks',sa.Text(),nullable=False),sa.Column('undo_result',sa.Text()),sa.Column('created_at',sa.DateTime(),nullable=False))
    with op.batch_alter_table('resources') as b:
        b.add_column(sa.Column('review_status',sa.String(12),nullable=False,server_default='pending'))
        b.add_column(sa.Column('revision',sa.Integer(),nullable=False,server_default='1'))
        b.add_column(sa.Column('approved_snapshot',sa.Text()))
        b.add_column(sa.Column('review_note',sa.String(500),nullable=False,server_default=''))
        b.add_column(sa.Column('reviewed_by',sa.Integer(),sa.ForeignKey('users.id',name='fk_resource_reviewer')))
        b.add_column(sa.Column('reviewed_at',sa.DateTime()))
        b.add_column(sa.Column('personal_note',sa.String(1000),nullable=False,server_default=''))
    # Existing content is retained for its author but requires explicit review before public access.

def downgrade():
    with op.batch_alter_table('announcements') as b:
        b.drop_column('revision')
    with op.batch_alter_table('audit_logs') as b:
        b.drop_constraint('fk_audit_actor',type_='foreignkey')
        b.drop_column('actor_id')
    with op.batch_alter_table('resources') as b:
        b.drop_constraint('fk_resource_reviewer',type_='foreignkey')
        for c in ['personal_note','reviewed_at','reviewed_by','review_note','approved_snapshot','revision','review_status']: b.drop_column(c)
    op.drop_table('ai_task_imports')
    op.drop_index('ix_device_presence_heartbeat_at',table_name='device_presence')
    op.drop_table('device_presence')
