"""院校库入参。"""
from pydantic import BaseModel, ConfigDict, Field


class SchoolInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    key: str = Field(min_length=1, max_length=32, pattern=r'^[a-zA-Z0-9_-]+$')
    name: str = Field(min_length=1, max_length=80)
    short: str = Field(default='', max_length=40)
    logo_key: str = Field(default='', max_length=255)
    album_keys: list[str] = Field(default_factory=list, max_length=20)
    info: dict = Field(default_factory=dict)


class SchoolUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    name: str = Field(default='', max_length=80)
    short: str = Field(default='', max_length=40)
    logo_key: str | None = Field(default=None, max_length=255)
    album_keys: list[str] | None = Field(default=None, max_length=20)
    info: dict | None = None
