from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TimeNodeValue(BaseModel):
    model_config = ConfigDict(extra='forbid')
    node_name: str = Field(min_length=1, max_length=80)
    target_date: str
    show_on_home: bool = True
    custom_msg: str = Field(default='', max_length=500)

    @field_validator('target_date')
    @classmethod
    def valid_date(cls, value):
        if date.fromisoformat(value).isoformat() != value: raise ValueError('日期格式无效')
        return value
