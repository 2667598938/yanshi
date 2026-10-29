"""AI 会话与消息（v0.3-e）：Key 只在服务端，前端不接触。"""
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class AIConversation(Base):
    __tablename__ = 'ai_conversations'

    id = Column(Integer, primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    title = Column(String(80), default='新对话', server_default='新对话')
    busy_until = Column(DateTime)
    request_token = Column(String(64))
    scene = Column(String(20), default='general', server_default='general', nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)
    updated_at = Column(DateTime, default=now, nullable=False, index=True)


class AIMessage(Base):
    __tablename__ = 'ai_messages'
    __table_args__ = (Index('ix_ai_messages_convo_id', 'conversation_id', 'id'),)

    id = Column(Integer, primary_key=True)
    conversation_id = Column(ForeignKey('ai_conversations.id'), nullable=False)
    image_keys = Column(Text, nullable=False, default='[]', server_default='[]')
    tool_trace = Column(Text, nullable=False, default='{}', server_default='{}')
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
    supports_images = Column(Boolean, nullable=False, default=False, server_default='0')
    supports_tools = Column(Boolean, nullable=False, default=False, server_default='0')
    provider = Column(String(24), nullable=False, default='deepseek')
    base_url = Column(String(200), nullable=False, default='')
    model = Column(String(120), default='', server_default='')
    key_cipher = Column(Text, nullable=False)
    key_mask = Column(String(40), nullable=False, default='', server_default='')
    updated_at = Column(DateTime, default=now, nullable=False)


class AIUsageDaily(Base):
    __tablename__ = 'ai_usage_daily'
    user_id = Column(ForeignKey('users.id'), primary_key=True)
    day = Column(String(10), primary_key=True)
    requests = Column(Integer, nullable=False, default=0)
    succeeded = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)


class AIModelCache(Base):
    __tablename__ = 'ai_model_cache'
    cache_key = Column(String(64), primary_key=True)
    user_id = Column(ForeignKey('users.id'), nullable=False, index=True)
    models_json = Column(Text, nullable=False, default='[]')
    details_json = Column(Text, nullable=False, default='[]', server_default='[]')
    fetched_at = Column(DateTime, nullable=False, default=now)
