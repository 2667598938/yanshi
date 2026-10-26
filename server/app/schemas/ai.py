"""AI 入参。"""
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

Scene = Literal['general', 'kaoyan', 'essay', 'plan', 'review']
Provider = Literal['deepseek', 'moonshot', 'zhipu', 'siliconflow', 'openai', 'custom']


class ChatInput(BaseModel):
    model_config = ConfigDict(extra='forbid')

    scene: Scene = 'general'
    content: str = Field(min_length=1, max_length=4000)
    conversation_id: Optional[int] = None
    image_keys: list[str] = Field(default_factory=list, max_length=4)
    use_tools: bool = False
    use_search: bool = False
    context: Optional[dict] = None      # 复盘等场景附带的本地统计数据


class ConversationCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    title: str = Field(default='新对话', max_length=80)
    scene: Scene = 'general'


class ConversationUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=80)


class AIPreferencesInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    context_turns: int = Field(ge=0, le=50)


class AIKeyInput(BaseModel):
    supports_images: bool = False
    supports_tools: bool = False
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    provider: Provider = 'deepseek'
    base_url: str = Field(default='', max_length=200)
    model: str = Field(default='', max_length=120)
    api_key: str = Field(min_length=8, max_length=400)


class AIModelsInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    provider: Provider = 'deepseek'
    base_url: str = Field(default='', max_length=200)
    api_key: str = Field(default='', max_length=400)   # 留空则用已保存的 Key
    force_refresh: bool = False
