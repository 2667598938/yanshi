"""Invited-group sharing, canonical privacy and personal schools/time nodes."""
from alembic import op
import sqlalchemy as sa
revision='f9b1d3e5a7c9'
down_revision='e8a0c2d4f6b8'
branch_labels=None
depends_on=None


def upgrade():
    with op.batch_alter_table('users') as batch:
        batch.alter_column('privacy_mode',new_column_name='is_private_mode',existing_type=sa.Boolean(),existing_nullable=False)
        batch.add_column(sa.Column('custom_motto',sa.String(500),nullable=False,server_default=''))
        batch.add_column(sa.Column('time_nodes_initialized',sa.Boolean(),nullable=False,server_default='0'))
        batch.add_column(sa.Column('schools_initialized',sa.Boolean(),nullable=False,server_default='0'))
    op.create_table('study_groups',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('name',sa.String(80),nullable=False))
    op.create_table('study_group_members',sa.Column('group_id',sa.Integer(),sa.ForeignKey('study_groups.id'),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),primary_key=True))
    db=op.get_bind()
    db.execute(sa.text("INSERT INTO study_groups (id,name) VALUES (1,'研时学习小组')"))
    db.execute(sa.text("INSERT INTO study_group_members (group_id,user_id) SELECT 1,id FROM users WHERE status != 'deleted' AND (role = 'admin' OR id IN (SELECT used_by FROM invite_codes WHERE used_by IS NOT NULL) OR id IN (SELECT user_id FROM audit_logs WHERE action = 'admin.create_member'))"))
    op.create_table('time_nodes',sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),primary_key=True),
        sa.Column('id',sa.String(100),primary_key=True),sa.Column('node_name',sa.String(80),nullable=False),
        sa.Column('target_date',sa.String(10),nullable=False),sa.Column('show_on_home',sa.Boolean(),nullable=False,server_default='1'),
        sa.Column('custom_msg',sa.String(500),nullable=False,server_default=''))
    op.drop_index('ix_schools_key',table_name='schools')
    with op.batch_alter_table('schools') as batch:
        batch.add_column(sa.Column('owner_id',sa.Integer(),sa.ForeignKey('users.id',name='fk_school_owner'),nullable=True))
        batch.create_unique_constraint('uq_school_owner_key',['owner_id','key'])
    op.create_index('ix_schools_key','schools',['key'],unique=False)


def downgrade():
    # 私有同名院校无法无损还原为全局唯一，禁止静默删用户院校。
    db=op.get_bind()
    duplicates=db.execute(sa.text('SELECT key FROM schools GROUP BY key HAVING COUNT(*)>1')).first()
    if duplicates: raise RuntimeError('请先备份并处理同名个人院校，再回退该迁移')
    op.drop_index('ix_schools_key',table_name='schools')
    with op.batch_alter_table('schools') as batch:
        batch.drop_constraint('uq_school_owner_key',type_='unique')
        batch.drop_column('owner_id')
    op.create_index('ix_schools_key','schools',['key'],unique=True)
    op.drop_table('time_nodes');op.drop_table('study_group_members');op.drop_table('study_groups')
    with op.batch_alter_table('users') as batch:
        for col in ('schools_initialized','time_nodes_initialized','custom_motto'):batch.drop_column(col)
        batch.alter_column('is_private_mode',new_column_name='privacy_mode',existing_type=sa.Boolean(),existing_nullable=False)
