"""图片附件与院校库（v0.3-d）。"""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Integer, String, Text,
)
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class Attachment(Base):
    """统一图片附件：头像 avatar / 错题 mistake / 梦校相册 school / 励志 inspiration。

    本地开发落 data/uploads；生产落七牛 Kodo 私有 bucket。对象 key 形如
    avatar/3/ab12....jpg，不可猜测；访问统一走带鉴权的 view 接口。
    """
    __tablename__ = 'attachments'

    id = Column(Integer, primary_key=True)
    object_key = Column(String(255), unique=True, nullable=False, index=True)
    storage_backend = Column(String(12), default='local', server_default='local', nullable=False)
    uploader_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    biz_type = Column(String(16), nullable=False)   # avatar | mistake | school | inspiration
    content_type = Column(String(32), default='image/jpeg', server_default='image/jpeg')
    size_bytes = Column(Integer, default=0, server_default='0', nullable=False)
    width = Column(Integer, default=0, server_default='0')
    height = Column(Integer, default=0, server_default='0')
    created_at = Column(DateTime, default=now, nullable=False)
    deleted_at = Column(DateTime)


class School(Base):
    """全局院校库（内置 7 校 + 管理员维护）；用户个人梦校关系走同步记录 type=userSchool。"""
    __tablename__ = 'schools'

    id = Column(Integer, primary_key=True)
    key = Column(String(40), unique=True, nullable=False, index=True)
    name = Column(String(80), nullable=False)
    short = Column(String(40), default='', server_default='')
    logo_key = Column(String(255), default='', server_default='')   # 空则用前端内置校徽
    album_keys = Column(Text, default='[]', server_default='[]')     # JSON 数组，校园相册 key
    # info JSON：{cutoff, ratio, books, avg_score}，半自动维护，默认空
    info = Column(Text, default='{}', server_default='{}')
    is_builtin = Column(Boolean, default=False, server_default='0', nullable=False)
    sort_order = Column(Integer, default=0, server_default='0')
    created_at = Column(DateTime, default=now, nullable=False)
    updated_at = Column(DateTime, default=now, nullable=False)
