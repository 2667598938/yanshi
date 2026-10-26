from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    CheckConstraint,
)
from ..database import Base
from ..time import utcnow


class SessionFact(Base):
    __tablename__ = "session_facts"
    __table_args__ = (
        CheckConstraint("started_at >= 1767225600000", name="ck_session_start"),
        CheckConstraint("ended_at >= started_at", name="ck_session_interval"),
        CheckConstraint(
            "actual_sec >= 0 AND actual_sec <= 10800", name="ck_session_duration"
        ),
    )
    user_id = Column(ForeignKey("users.id"), primary_key=True)
    record_id = Column(String(500), primary_key=True)
    started_at = Column(BigInteger, nullable=False)
    ended_at = Column(BigInteger, nullable=False)
    actual_sec = Column(Integer, nullable=False)
    study_date = Column(String(10), nullable=False)
    conflict = Column(Boolean, nullable=False, default=False, server_default="0")


class TimerLease(Base):
    __tablename__ = "timer_leases"
    user_id = Column(ForeignKey("users.id"), primary_key=True)
    session_id = Column(String(100), nullable=False)
    device_id = Column(String(80), nullable=False)
    started_at = Column(BigInteger, nullable=False)
    detail = Column(Text, nullable=False, default="{}")
    expires_at = Column(DateTime, nullable=False, default=utcnow)
