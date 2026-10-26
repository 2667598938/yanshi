"""多房间自习室域：按房间管理成员与心跳，无摄像头或媒体推流。"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from ..database import Base
from ..time import utcnow


def now():
    return utcnow()


class Room(Base):
    __tablename__ = "rooms"

    id = Column(Integer, primary_key=True)
    code = Column(String(32), unique=True, nullable=False)  # 每房间唯一的房间码
    name = Column(String(80), nullable=False)
    intro = Column(String(500), default="", server_default="")
    owner_id = Column(ForeignKey("users.id"), nullable=True)
    capacity = Column(Integer, default=4, server_default="4", nullable=False)
    visibility = Column(
        String(12), default="public", server_default="public", nullable=False
    )
    room_type = Column(
        String(24),
        default="checkin_room",
        server_default="checkin_room",
        nullable=False,
    )
    created_at = Column(DateTime, default=now, nullable=False)
    dissolved_at = Column(DateTime)


class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_room_user"),)

    id = Column(Integer, primary_key=True)
    room_id = Column(ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(ForeignKey("users.id"), nullable=False, index=True)
    role = Column(
        String(12), default="member", server_default="member", nullable=False
    )  # owner|member
    joined_at = Column(DateTime, default=now, nullable=False)


class RoomPresence(Base):
    """在线 / 专注状态，由前端 30s 心跳驱动；查询时以 90 秒阈值判定离线。"""

    __tablename__ = "room_presence"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", name="uq_presence_room_user"),
    )

    id = Column(Integer, primary_key=True)
    room_id = Column(ForeignKey("rooms.id"), nullable=False, index=True)
    user_id = Column(ForeignKey("users.id"), nullable=False, index=True)
    status = Column(
        String(12), default="offline", server_default="offline", nullable=False
    )
    # offline | idle | focusing | resting
    subject_client_id = Column(String(500), default="", server_default="")
    subject_name = Column(String(100), default="", server_default="")
    activity_type = Column(String(20), default="", server_default="")
    mode = Column(String(12), default="", server_default="")
    focus_started_at = Column(BigInteger, nullable=True)  # epoch ms
    last_heartbeat_at = Column(DateTime, default=now, nullable=False)


class RoomJoinApply(Base):
    """私密房间入房申请：pending_key 只约束「待审唯一」，历史驳回可留多条。"""

    __tablename__ = "room_join_applies"
    __table_args__ = (
        UniqueConstraint("pending_key", name="uq_room_join_pending_key"),
        Index("ix_room_join_applies_room_status", "room_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    room_id = Column(ForeignKey("rooms.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False, index=True)
    status = Column(
        String(12), default="pending", server_default="pending", nullable=False
    )
    message = Column(String(200), default="", server_default="", nullable=False)
    # 待审时为 f'{room_id}-{user_id}'，审批后置 NULL，让同一人可再次申请
    pending_key = Column(String(40), nullable=True)
    created_at = Column(DateTime, default=now, nullable=False, index=True)
    handled_at = Column(DateTime)
    handled_by = Column(ForeignKey("users.id"), nullable=True)


class RoomMessage(Base):
    """留言板 / 互相打气（软删）。"""

    __tablename__ = "room_messages"
    __table_args__ = (Index("ix_room_messages_room_created", "room_id", "created_at"),)

    id = Column(Integer, primary_key=True)
    room_id = Column(ForeignKey("rooms.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    content = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=now, nullable=False)
    deleted_at = Column(DateTime)


class RoomGoal(Base):
    """目标墙：每人一条（目标院校 + 目标分 + 一句话）。"""

    __tablename__ = "room_goals"
    __table_args__ = (UniqueConstraint("room_id", "user_id", name="uq_goal_room_user"),)

    id = Column(Integer, primary_key=True)
    room_id = Column(ForeignKey("rooms.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    target_school = Column(String(80), default="", server_default="")
    target_score = Column(String(80), default="", server_default="")
    words = Column(String(200), default="", server_default="")
    updated_at = Column(DateTime, default=now, nullable=False)
