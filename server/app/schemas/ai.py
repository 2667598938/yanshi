"""AI 入参。"""
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Scene = Literal['general', 'kaoyan', 'essay', 'plan', 'review']


class ChatInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    scene: Scene = 'general'
    content: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[int] = None
    context: Optional[dict] = None      # 复盘等场景附带的本地统计数据


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    title: str = Field(default='新对话', max_length=80)
    scene: Scene = 'general'


class ConversationUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=80)
