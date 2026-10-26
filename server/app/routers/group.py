from typing import Literal
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, delete
from ..deps import get_current_user, get_db, get_admin, audit
from ..models import User, StudyGroupMember
from ..schemas.room import HeartbeatInput
from ..services.presence import member_state, update_presence
from pydantic import Field
from ..errors import ok, ApiError
from ..services.group import same_group, shared_records, enroll

router = APIRouter(prefix='/api/v1', tags=['study-group'])


@router.get('/group/members')
def members(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(select(User).where(User.status == 'active').order_by(User.id)).all()
    return ok([{'id': row.id, 'nickname': row.nickname, 'avatar_key': row.avatar_key or '',
        'is_private_mode': bool(row.is_private_mode), **member_state(db,user,row)}
        for row in rows if same_group(db, user.id, row.id)])


@router.get('/group/members/{uid}/learning')
def learning(uid: int, after: str = '', kind: Literal['subject','session','task','mistake'] | None = None,
             user=Depends(get_current_user), db=Depends(get_db)):
    return ok(shared_records(db, user, uid, after, kind))


@router.post('/admin/group-members/{uid}')
def add_member(uid: int, request: Request, user=Depends(get_admin), db=Depends(get_db)):
    target = db.get(User, uid)
    if not target or target.status != 'active': raise ApiError(404,40401,'账号不存在')
    enroll(db, uid); audit(db,request,'admin.group_add',user_id=uid); db.commit(); return ok()


@router.delete('/admin/group-members/{uid}')
def remove_member(uid: int, request: Request, user=Depends(get_admin), db=Depends(get_db)):
    db.execute(delete(StudyGroupMember).where(StudyGroupMember.user_id == uid))
    audit(db,request,'admin.group_remove',user_id=uid)
    db.commit(); return ok()


class SiteHeartbeat(HeartbeatInput):
    device_id: str = Field(default='legacy',min_length=1,max_length=80,pattern=r'^[A-Za-z0-9_-]+$')
    room_id: int | None = Field(default=None,gt=0)

@router.post('/group/presence')
def presence(body: SiteHeartbeat,user=Depends(get_current_user),db=Depends(get_db)):
    return ok(update_presence(db,user,body))
