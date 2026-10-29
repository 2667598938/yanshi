from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from ..database import Base
from ..time import utcnow


class DevicePresence(Base):
    __tablename__ = "device_presence"
    user_id = Column(ForeignKey("users.id"), primary_key=True)
    device_id = Column(String(80), primary_key=True)
    room_id = Column(ForeignKey("rooms.id"), nullable=True)
    status = Column(String(12), nullable=False, default="idle")
    detail = Column(Text, nullable=False, default="{}")
    entered_at = Column(DateTime, nullable=False, default=utcnow)
    heartbeat_at = Column(DateTime, nullable=False, default=utcnow, index=True)


class AITaskImport(Base):
    # No message FK: task provenance and undo receipt survive deletion of the chat.
    __tablename__ = "ai_task_imports"
    user_id = Column(ForeignKey("users.id"), primary_key=True)
    message_id = Column(Integer, primary_key=True)
    selection = Column(Text, nullable=False, default="[]")
    tasks = Column(Text, nullable=False, default="[]")
    undo_result = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
