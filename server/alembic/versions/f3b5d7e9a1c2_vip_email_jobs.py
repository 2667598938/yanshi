"""Permanent VIP, expiry notification marker and transactional email outbox."""
from alembic import op
import sqlalchemy as sa

revision = 'f3b5d7e9a1c2'
down_revision = 'e2a4c6d8f0b1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('vip_permanent', sa.Boolean(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('vip_expiry_notified_until', sa.DateTime()))
    op.add_column('users', sa.Column('ai_context_turns', sa.Integer(), nullable=False, server_default='10'))
    with op.batch_alter_table('feature_requests') as batch:
        batch.add_column(sa.Column('active_key', sa.String(80), nullable=True))
        batch.add_column(sa.Column('approval_source', sa.String(12), nullable=False, server_default='manual'))
        batch.create_unique_constraint('uq_feature_request_active_key', ['active_key'])
    requests = sa.table('feature_requests', sa.column('approval_source'), sa.column('reviewed_by'), sa.column('review_note'))
    op.get_bind().execute(requests.update().where(requests.c.reviewed_by.is_(None),
        requests.c.review_note.like('VIP 免审核%')).values(approval_source='vip'))
    op.create_table('email_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('message_id', sa.Integer(), sa.ForeignKey('messages.id'), nullable=False, unique=True),
        sa.Column('recipient', sa.String(254), nullable=False),
        sa.Column('subject', sa.String(160), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('next_attempt_at', sa.DateTime(), nullable=False),
        sa.Column('locked_at', sa.DateTime()),
        sa.Column('lease_token', sa.String(64)),
        sa.Column('last_error', sa.String(300), server_default=''),
        sa.Column('sent_at', sa.DateTime()),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_index('ix_email_jobs_user_id', 'email_jobs', ['user_id'])


def downgrade():
    op.drop_index('ix_email_jobs_user_id', table_name='email_jobs')
    op.drop_table('email_jobs')
    with op.batch_alter_table('feature_requests') as batch:
        batch.drop_constraint('uq_feature_request_active_key', type_='unique')
        batch.drop_column('approval_source')
        batch.drop_column('active_key')
    op.drop_column('users', 'ai_context_turns')
    op.drop_column('users', 'vip_expiry_notified_until')
    op.drop_column('users', 'vip_permanent')
