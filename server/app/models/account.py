from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String)
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(254), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    nickname = Column(String(40), nullable=False)
    avatar_key = Column(String(255), default='', server_default='')
    role = Column(String(12), nullable=False, default='member')   # admin | member
    status = Column(String(20), nullable=False, default='active')  # active | banned | deleted
    status_reason = Column(String(500), default='', server_default='')

    # 学习偏好（与前端「我的」设置对应）
    target_school = Column(String(32), default='', server_default='')
    exam_year = Column(Integer, default=2028, server_default='2028')
    daily_goal_min = Column(Integer, default=300, server_default='300')
    exam_date = Column(String(10), default='', server_default='')   # 空则用系统配置
    notify_enabled = Column(Boolean, default=False, server_default='0', nullable=False)

    vip_until = Column(DateTime)

    token_version = Column(Integer, nullable=False, default=0, server_default='0')
    last_login_at = Column(DateTime)
    last_seen_at = Column(DateTime, index=True)
    delete_requested_at = Column(DateTime)
    created_at = Column(DateTime, default=now, nullable=False)
    deleted_at = Column(DateTime)


class RefreshToken(Base):
    __tablename__ = 'refresh_tokens'

    id = Column(String(64), primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime)


class Invite(Base):
    __tablename__ = 'invite_codes'

    id = Column(Integer, primary_key=True)
    code_hash = Column(String(64), unique=True, nullable=False)
    hint = Column(String(16), nullable=False, default='')
    created_by = Column(ForeignKey('users.id'), nullable=False)
    used_by = Column(ForeignKey('users.id'), nullable=True)
    remark = Column(String(200), default='', server_default='')
    vip_days = Column(Integer, nullable=False, default=0, server_default='0')
    expires_at = Column(DateTime)
    used_at = Column(DateTime)
    revoked_at = Column(DateTime)
    created_at = Column(DateTime, default=now, nullable=False)


class LoginLog(Base):
    __tablename__ = 'login_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=True)
    email = Column(String(254), nullable=False, default='', server_default='')
    result = Column(String(20), nullable=False)  # success | bad_password | banned | locked
    ip = Column(String(64), default='', server_default='')
    user_agent = Column(String(300), default='', server_default='')
    created_at = Column(DateTime, default=now, nullable=False, index=True)
