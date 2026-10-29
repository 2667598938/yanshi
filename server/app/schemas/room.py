"""自习室入参。"""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class HeartbeatInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["offline", "online", "idle", "focusing", "resting", "away"]
    subject_client_id: str = Field(default="", max_length=500)
    subject_name: str = Field(default="", max_length=100)
    activity_type: str = Field(default="", max_length=20)
    mode: str = Field(default="", max_length=12)
    focus_started_at: Optional[int] = Field(default=None, ge=0)
    # Display only; learning totals are still derived from validated session facts.
    focus_elapsed_sec: Optional[int] = Field(default=None, ge=0, le=10800)


class MessageInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=500)


class GoalInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_school: str = Field(default="", max_length=80)
    target_score: str = Field(default="", max_length=80)
    words: str = Field(default="", max_length=200)


class RoomCreate(BaseModel):
    accept_sharing: bool = False
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=2, max_length=20)
    room_type: Literal["checkin_room", "video_small_room", "cloud_video_room"] = (
        "checkin_room"
    )
    intro: str = Field(default="", max_length=200)
    visibility: Literal["public", "private"] = "private"


class RoomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Optional[str] = Field(default=None, min_length=2, max_length=20)
    intro: Optional[str] = Field(default=None, max_length=200)
    visibility: Optional[Literal["public", "private"]] = None


class RoomJoin(BaseModel):
    accept_sharing: bool = False
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(default="", max_length=32)


class RoomApplyInput(BaseModel):
    accept_sharing: bool = False
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(default="", max_length=200)


class ApplyReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
