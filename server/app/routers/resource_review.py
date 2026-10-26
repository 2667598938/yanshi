import json
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field
from fastapi import APIRouter,Depends,Request
from sqlalchemy import select,update
from ..deps import get_admin,get_db,audit
from ..models import Resource,User
from ..errors import ApiError,ok
from ..services.messages import create_message
from ..time import utcnow

router=APIRouter(prefix='/api/v1/admin/resources',tags=['resource-review'],dependencies=[Depends(get_admin)])
FIELDS=('title','url','code','category','intro')

def review_payload(row):
    return {'id':row.id,'user_id':row.user_id,**{k:getattr(row,k) for k in FIELDS},
        'revision':row.revision,'review_status':row.review_status,'review_note':row.review_note,
        'has_published_version':bool(row.approved_snapshot)}

class ReviewInput(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    action:Literal['approve','reject']
    expected_revision:int=Field(ge=1)
    note:str=Field(default='',max_length=500)

@router.get('')
def queue(status:Literal['pending','approved','rejected','all']='pending',after_id:int=0,db=Depends(get_db)):
    q=select(Resource).where(Resource.deleted_at.is_(None),Resource.id>after_id)
    if status!='all':q=q.where(Resource.review_status==status)
    rows=db.scalars(q.order_by(Resource.id).limit(100)).all()
    return ok({'items':[review_payload(row) for row in rows],'next':rows[-1].id if len(rows)==100 else None})

@router.post('/{rid}/review')
def review(rid:int,body:ReviewInput,request:Request,user=Depends(get_admin),db=Depends(get_db)):
    row=db.get(Resource,rid)
    if not row or row.deleted_at:raise ApiError(404,40401,'资料不存在')
    if row.review_status!='pending' or row.revision!=body.expected_revision:raise ApiError(409,40902,'资料已修改或已处理，请刷新审核队列')
    if body.action=='reject' and not body.note:raise ApiError(400,40001,'驳回必须填写原因')
    values={'review_status':'approved' if body.action=='approve' else 'rejected','review_note':body.note,
            'reviewed_by':user.id,'reviewed_at':utcnow(),'revision':row.revision+1}
    if body.action=='approve':values['approved_snapshot']=json.dumps({k:getattr(row,k) for k in FIELDS},ensure_ascii=False)
    updated=db.execute(update(Resource).where(Resource.id==rid,Resource.revision==body.expected_revision,Resource.review_status=='pending',Resource.deleted_at.is_(None)).values(**values)).rowcount
    if not updated:db.rollback();raise ApiError(409,40902,'审核状态已变化')
    owner=db.get(User,row.user_id)
    create_message(db,owner,kind='content',title='资料审核通过' if body.action=='approve' else '资料审核未通过',
        content=f'「{row.title}」'+('已公开' if body.action=='approve' else '未通过：'+body.note),link=f'/resources/{rid}',
        dedupe_key=f'resource-review:{rid}:{body.expected_revision}',email=True,settings=request.app.state.settings)
    audit(db,request,'admin.resource_review',user_id=row.user_id,detail=json.dumps({'resource_id':rid,'action':body.action,'note':body.note,'revision':body.expected_revision},ensure_ascii=False))
    db.commit();db.refresh(row);return ok(review_payload(row))
