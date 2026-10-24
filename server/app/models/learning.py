"""本地优先同步：通用学习记录 + 幂等操作日志（见 ARCHITECTURE.md 附录 A）。

- learning_records：每个用户的通用 JSON 记录，按 (user_id, id) 唯一，revision 单调递增，deleted 软删。
- learning_operations：已提交命令的指纹与结果，用于 operationId 幂等重放。
"""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class LearningRecord(Base):
    __tablename__ = 'learning_records'

    user_id = Column(ForeignKey('users.id'), primary_key=True)
    id = Column(String(500), primary_key=True)
    body = Column(Text, nullable=False)          # JSON 字符串；软删时为 null 记录
    revision = Column(Integer, nullable=False, default=1, server_default='1')
    deleted = Column(Integer, nullable=False, default=0, server_default='0')  # 0 正常 1 已删
    updated_at = Column(DateTime, default=now, nullable=False, index=True)


class LearningOperation(Base):
    __tablename__ = 'learning_operations'

    user_id = Column(ForeignKey('users.id'), primary_key=True)
    operation_id = Column(String(100), primary_key=True)
    signature = Column(String(64), nullable=False)          # 命令语义内容的 sha256
    result = Column(Text, nullable=False)                   # JSON：首次成功的返回，用于幂等重放
    created_at = Column(DateTime, default=now, nullable=False, index=True)
