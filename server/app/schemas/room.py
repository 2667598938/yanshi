"""自习室入参。"""
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class HeartbeatInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    status: Literal['offline', 'online', 'focusing']
    subject_client_id: str = Field(default='', max_length=500)
    subject_name: str = Field(default='', max_length=100)
    activity_type: str = Field(default='', max_length=20)
    mode: str = Field(default='', max_length=12)
    focus_started_at: Optional[int] = Field(default=None, ge=0)


class MessageInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    content: str = Field(min_length=1, max_length=500)


class GoalInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    target_school: str = Field(default='', max_length=80)
    target_score: str = Field(default='', max_length=80)
    words: str = Field(default='', max_length=200)
