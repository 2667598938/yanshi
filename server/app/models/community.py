"""社区：动态帖子、二级评论、励志区投稿。"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    content = Column(String(2000), nullable=False)
    revision = Column(Integer, nullable=False, default=1, server_default='1')
    # 离线发帖客户端 ID：同一用户重复上传返回同一条，避免重试产生重复帖子
    client_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=now, nullable=False, index=True)
    updated_at = Column(DateTime, default=now, nullable=False)
    deleted_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('uq_posts_user_client', 'user_id', 'client_id', unique=True),
    )


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    post_id = Column(ForeignKey('posts.id'), nullable=False, index=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    parent_id = Column(Integer, nullable=True, index=True)  # 一级评论为空；二级指向一级
    reply_to_user_id = Column(ForeignKey('users.id'), nullable=True)
    content = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)
    deleted_at = Column(DateTime, nullable=True)


class Inspiration(Base):
    __tablename__ = 'inspirations'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    content = Column(String(200), nullable=False, default='', server_default='')
    image_key = Column(String(300), default='', server_default='')
    status = Column(String(16), nullable=False, default='pending', server_default='pending',
                    index=True)  # pending | approved | rejected
    review_note = Column(String(300), default='', server_default='')
    reviewed_by = Column(ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, default=now, nullable=False, index=True)
