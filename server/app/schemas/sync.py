"""学习数据同步入参（字段名与前端同步引擎保持 camelCase）。"""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class Change(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=500)
    expectedRevision: int = Field(ge=0)
    # 必填：可以是记录对象（dict）或 null（删除）
    record: Any = Field(...)


class SyncCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operationId: str = Field(min_length=1, max_length=100)
    changes: list[Change] = Field(min_length=1, max_length=200)


class LearningPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    bulletEnabled: bool = True
    # 本人偏好，随账号同步；不进入公共励志投稿池。
    bulletText: str = Field(default="", max_length=80)
    focusMin: int = Field(default=25, ge=5, le=180)
    shortBreakMin: int = Field(default=5, ge=1, le=60)
    longBreakMin: int = Field(default=15, ge=1, le=180)
    longBreakEvery: int = Field(default=4, ge=1, le=8)
