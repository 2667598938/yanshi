"""资料区入参。"""
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


def url_value(v: str) -> str:
    if not v.strip().startswith(('http://', 'https://')):
        raise ValueError('链接必须以 http:// 或 https:// 开头')
    return v.strip()


class ResourceInput(Strict):
    title: str = Field(min_length=2, max_length=80)
    url: str = Field(min_length=8, max_length=600)
    code: str = Field(default='', max_length=20)
    category: str = Field(default='', max_length=20)
    intro: str = Field(default='', max_length=300)

    _url = field_validator('url')(url_value)


class FavoriteState(Strict):
    favorited: bool


class ResourceUpdate(Strict):
    title: Optional[str] = Field(default=None, min_length=2, max_length=80)
    url: Optional[str] = Field(default=None, min_length=8, max_length=600)
    code: Optional[str] = Field(default=None, max_length=20)
    category: Optional[str] = Field(default=None, max_length=20)
    intro: Optional[str] = Field(default=None, max_length=300)

    @field_validator('url')
    @classmethod
    def check_url(cls, v):
        if v is None:
            return v
        return url_value(v)
