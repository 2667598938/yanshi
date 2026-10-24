from sqlalchemy import (Boolean, Column, DateTime, ForeignKey, Integer, String, Text)
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class Config(Base):
    __tablename__ = 'system_config'

    config_key = Column(String(80), primary_key=True)
    config_value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=now, nullable=False)
    updated_by = Column(ForeignKey('users.id'), nullable=True)


class Announcement(Base):
    __tablename__ = 'announcements'

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

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=True)
    action = Column(String(80), nullable=False, index=True)
    ip = Column(String(64), default='', server_default='')
    user_agent = Column(String(300), default='', server_default='')
    detail = Column(Text, default='', server_default='')
    created_at = Column(DateTime, default=now, nullable=False, index=True)
