"""AI 会话与消息（v0.3-e）：Key 只在服务端，前端不接触。"""
from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class AIConversation(Base):
    __tablename__ = 'ai_conversations'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    title = Column(String(80), default='新对话', server_default='新对话')
    scene = Column(String(20), default='general', server_default='general', nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)
    updated_at = Column(DateTime, default=now, nullable=False, index=True)


class AIMessage(Base):
    __tablename__ = 'ai_messages'
    __table_args__ = (Index('ix_ai_messages_convo_id', 'conversation_id', 'id'),)

    id = Column(Integer, primary_key=True)
    conversation_id = Column(ForeignKey('ai_conversations.id'), nullable=False)
    role = Column(String(12), nullable=False)   # user | assistant
    content = Column(Text, nullable=False)
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    latency_ms = Column(Integer)
    created_at = Column(DateTime, default=now, nullable=False)


class UserAIKey(Base):
    """VIP 用户自填的 AI Key：仅存 AES-GCM 密文，不落明文。"""
    __tablename__ = 'user_ai_keys'

    user_id = Column(ForeignKey('users.id'), primary_key=True)
    provider = Column(String(24), nullable=False, default='deepseek')
    base_url = Column(String(200), nullable=False, default='')
    model = Column(String(120), default='', server_default='')
    key_cipher = Column(Text, nullable=False)
    key_mask = Column(String(40), nullable=False, default='', server_default='')
    updated_at = Column(DateTime, default=now, nullable=False)
