"""社区入参。"""
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class PostInput(Strict):
    content: str = Field(min_length=1, max_length=2000)
    # 离线草稿的客户端 ID（幂等键），在线发帖可不填
    client_id: Optional[str] = Field(default=None, min_length=8, max_length=64,
                                     pattern=r'^[A-Za-z0-9_-]+$')


class PostUpdate(Strict):
    content: str = Field(min_length=1, max_length=2000)
    expected_revision: int = Field(ge=1)


class CommentInput(Strict):
    content: str = Field(min_length=1, max_length=500)
    parent_id: Optional[int] = None


class InspirationInput(Strict):
    content: str = Field(min_length=1, max_length=200)
    image_key: str = Field(default='', max_length=300)


class InspirationReview(Strict):
    action: Literal['approve', 'reject']
    note: str = Field(default='', max_length=300)


class InspirationNote(Strict):
    note: str = Field(default='', max_length=300)


class InspirationTakedown(Strict):
    note: str = Field(min_length=5, max_length=300)
