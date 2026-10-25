"""资料区：网盘资料、点赞、收藏。"""
from sqlalchemy import (Column, DateTime, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class Resource(Base):
    __tablename__ = 'resources'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    title = Column(String(80), nullable=False)
    url = Column(String(600), nullable=False)
    code = Column(String(20), default='', server_default='')
    category = Column(String(20), default='', server_default='', index=True)
    intro = Column(String(300), default='', server_default='')
    created_at = Column(DateTime, default=now, nullable=False, index=True)
    updated_at = Column(DateTime, default=now, nullable=False)
    deleted_at = Column(DateTime, nullable=True)


class ResourceLike(Base):
    __tablename__ = 'resource_likes'
    __table_args__ = (UniqueConstraint('resource_id', 'user_id', name='uq_resource_like'),)

    id = Column(Integer, primary_key=True)
    resource_id = Column(ForeignKey('resources.id'), nullable=False, index=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=now, nullable=False)


class ResourceFavorite(Base):
    __tablename__ = 'resource_favorites'
    __table_args__ = (
        UniqueConstraint('resource_id', 'user_id', name='uq_resource_favorite'),
    )

    id = Column(Integer, primary_key=True)
    resource_id = Column(ForeignKey('resources.id'), nullable=False, index=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    created_at = Column(DateTime, default=now, nullable=False)
