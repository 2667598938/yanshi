from datetime import date
from pydantic import BaseModel,ConfigDict,Field,field_validator
class TaskValue(BaseModel):
    model_config=ConfigDict(extra='allow',str_strip_whitespace=True)
    title:str=Field(min_length=1,max_length=200)
    subjectId:str=Field(default='other',max_length=100)
    dueDate:str=''
    estimatedMin:int=Field(default=0,ge=0,le=1440,strict=True)
    acceptCriteria:str=Field(default='',max_length=500)
    done:int=Field(default=0,ge=0,le=1)
    @field_validator('dueDate')
    @classmethod
    def valid_date(cls,value):
        if value and date.fromisoformat(value).isoformat()!=value:raise ValueError('invalid date')
        return value
