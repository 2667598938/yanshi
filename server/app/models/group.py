"""Legacy study-group tables are retained for history only; room membership grants sharing.

TimeNode remains a live, owner-private model.
"""

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from ..database import Base


class StudyGroup(Base):
    __tablename__ = "study_groups"
    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)


class StudyGroupMember(Base):
    __tablename__ = "study_group_members"
    group_id = Column(ForeignKey("study_groups.id"), primary_key=True)
    user_id = Column(ForeignKey("users.id"), primary_key=True)


class TimeNode(Base):
    __tablename__ = "time_nodes"
    user_id = Column(ForeignKey("users.id"), primary_key=True)
    id = Column(String(100), primary_key=True)
    node_name = Column(String(80), nullable=False)
    target_date = Column(String(10), nullable=False)
    show_on_home = Column(Boolean, nullable=False, default=True, server_default="1")
    custom_msg = Column(String(500), nullable=False, default="", server_default="")
