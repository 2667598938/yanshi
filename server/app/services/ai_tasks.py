import json
import re
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError


class SuggestedTask(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title:str=Field(min_length=1,max_length=200)
    due_date:str
    estimated_min:int=Field(default=0,ge=0,le=1440,strict=True)
    subject_id:str=Field(default='other',max_length=100)
    accept_criteria:str=Field(default='',max_length=500)

    @field_validator('due_date')
    @classmethod
    def valid_date(cls,value):
        if date.fromisoformat(value).isoformat()!=value:raise ValueError('invalid date')
        return value


def proposals(content):
    for block in re.findall(r'```(?:yanshi_tasks|json)\s*\n(.*?)```',content,re.S):
        if len(block)>30000:continue
        try:
            data=json.loads(block)
            if not isinstance(data,dict) or set(data)!={'tasks'}:continue
            rows=data['tasks']
            if not isinstance(rows,list) or not 1<=len(rows)<=30:continue
            return [SuggestedTask.model_validate(row).model_dump() for row in rows]
        except (ValueError,ValidationError,TypeError):continue
    return []
