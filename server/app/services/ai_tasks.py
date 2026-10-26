import json
import re
from datetime import date
from pydantic import BaseModel, ConfigDict, Field, field_validator, ValidationError


class SuggestedTask(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title:str=Field(min_length=1,max_length=200)
    due_date:str=''
    estimated_min:int=Field(default=0,ge=0,le=1440,strict=True)
    subject_id:str=Field(default='other',max_length=100)
    accept_criteria:str=Field(default='',max_length=500)

    @field_validator('due_date')
    @classmethod
    def valid_date(cls,value):
        if not value:return ''
        if date.fromisoformat(value).isoformat()!=value:raise ValueError('invalid date')
        return value


def proposals(content):
    blocks=re.findall(r'```(?:yanshi_tasks|json)\s*(.*?)```',content,re.S)
    if content.strip().startswith('{'):blocks.append(content.strip())
    aliases={'acceptance':'accept_criteria','acceptCriteria':'accept_criteria','estimate_min':'estimated_min','estimatedMin':'estimated_min','dueDate':'due_date','subjectId':'subject_id'}
    for block in blocks:
        if len(block)>30000:continue
        try:
            data=json.loads(block)
            if not isinstance(data,dict) or set(data)!={'tasks'}:continue
            rows=data['tasks']
            if not isinstance(rows,list) or not 1<=len(rows)<=30:continue
            clean=[]
            for row in rows:
                if not isinstance(row,dict):raise ValueError('invalid task')
                normalized={}
                for key,value in row.items():
                    field=aliases.get(key,key)
                    if field in normalized and normalized[field]!=value:raise ValueError('conflicting fields')
                    normalized[field]=value
                clean.append(SuggestedTask.model_validate(normalized).model_dump())
            return clean
        except (ValueError,ValidationError,TypeError):continue
    return []
