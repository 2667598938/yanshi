from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from ..database import Base
from ..time import utcnow


class GroupInvite(Base):
    __tablename__ = "group_invites"
    id = Column(Integer, primary_key=True)
    group_id = Column(ForeignKey("study_groups.id"), nullable=False)
    token_hash = Column(String(64), unique=True, nullable=False)
    created_by = Column(ForeignKey("users.id"), nullable=False)
    target_user_id = Column(ForeignKey("users.id"), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime)
    consumed_by = Column(ForeignKey("users.id"))
    created_at = Column(DateTime, nullable=False, default=utcnow)


class GroupApply(Base):
    __tablename__ = "group_applies"
    id = Column(Integer, primary_key=True)
    group_id = Column(ForeignKey("study_groups.id"), nullable=False)
    user_id = Column(ForeignKey("users.id"), nullable=False)
    invite_id = Column(ForeignKey("group_invites.id"), nullable=False)
    pending_key = Column(String(100), unique=True)
    status = Column(String(16), nullable=False, default="pending")
    revision = Column(Integer, nullable=False, default=1)
    reason = Column(String(300), nullable=False, default="")
    remark = Column(String(300), nullable=False, default="")
    reviewed_by = Column(ForeignKey("users.id"))
    reviewed_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=utcnow)
