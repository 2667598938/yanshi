from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Float,
                        UniqueConstraint)
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class TransientState(Base):
    __tablename__ = 'transient_states'
    state_key = Column(String(200), primary_key=True)
    value_cipher = Column(Text, nullable=False)
    expires_at = Column(Float, nullable=False, index=True)


class Config(Base):
    __tablename__ = 'system_config'

    config_key = Column(String(80), primary_key=True)
    config_value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=now, nullable=False)
    updated_by = Column(ForeignKey('users.id'), nullable=True)


class Announcement(Base):
    __tablename__ = 'announcements'
    revision = Column(Integer,nullable=False,default=1,server_default='1')

    id = Column(Integer, primary_key=True)
    content = Column(String(1000), nullable=False)
    is_active = Column(Boolean, default=True, server_default='1', nullable=False)
    created_by = Column(ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=now, nullable=False)


class OfficialEvent(Base):
    __tablename__ = 'official_events'

    id = Column(Integer, primary_key=True)
    title = Column(String(80), nullable=False)
    event_date = Column(String(10), nullable=False)  # YYYY-MM-DD
    year = Column(String(8), default='', server_default='')
    sort_order = Column(Integer, default=0, server_default='0')


class Audit(Base):
    __tablename__ = 'audit_logs'
    actor_id = Column(ForeignKey('users.id'), nullable=True)

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=True)
    action = Column(String(80), nullable=False, index=True)
    ip = Column(String(64), default='', server_default='')
    user_agent = Column(String(300), default='', server_default='')
    detail = Column(Text, default='', server_default='')
    created_at = Column(DateTime, default=now, nullable=False, index=True)


class FeatureRequest(Base):
    __tablename__ = 'feature_requests'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    feature = Column(String(40), nullable=False)
    active_key = Column(String(80), unique=True, nullable=True)
    approval_source = Column(String(12), nullable=False, default='manual', server_default='manual')
    reason = Column(String(500), nullable=False)
    status = Column(String(16), nullable=False, default='pending', server_default='pending',
                    index=True)   # pending | approved | rejected | revoked | withdrawn
    review_note = Column(String(300), default='', server_default='')
    reviewed_by = Column(ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=now, nullable=False, index=True)


class UserFeatureGrant(Base):
    """审批后的功能授权事实源；鉴权只读本表或 VIP。"""
    __tablename__ = 'user_feature_grants'
    __table_args__ = (
        UniqueConstraint('user_id', 'feature', name='uq_grant_user_feature'),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    feature = Column(String(40), nullable=False)
    source_request_id = Column(Integer, nullable=True)
    granted_by = Column(ForeignKey('users.id'), nullable=True)
    granted_at = Column(DateTime, default=now, nullable=False)
    revoked_at = Column(DateTime)


class Message(Base):
    """站内消息：审批结果、VIP 调整、内容处理等通知。"""
    __tablename__ = 'messages'
    __table_args__ = (
        UniqueConstraint('user_id', 'dedupe_key', name='uq_messages_user_dedupe'),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    kind = Column(String(24), nullable=False, default='system')  # system|apply|vip|content
    title = Column(String(80), nullable=False)
    content = Column(String(500), nullable=False, default='', server_default='')
    link = Column(String(200), default='', server_default='')
    is_read = Column(Boolean, default=False, server_default='0', nullable=False)
    dedupe_key = Column(String(120), nullable=True)
    created_at = Column(DateTime, default=now, nullable=False, index=True)


class EmailJob(Base):
    __tablename__ = 'email_jobs'
    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    message_id = Column(ForeignKey('messages.id'), nullable=False, unique=True)
    recipient = Column(String(254), nullable=False)
    subject = Column(String(160), nullable=False)
    content = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default='pending', server_default='pending')
    attempts = Column(Integer, nullable=False, default=0, server_default='0')
    next_attempt_at = Column(DateTime, nullable=False, default=now)
    locked_at = Column(DateTime)
    lease_token = Column(String(64))
    last_error = Column(String(300), default='', server_default='')
    sent_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=now)
