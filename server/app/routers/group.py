from typing import Literal
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, delete
from ..deps import get_current_user, get_db, get_admin, audit
from ..models import User, StudyGroupMember, Room, RoomMember, RoomPresence
from ..schemas.room import HeartbeatInput
from ..time import utcnow
from ..errors import ok, ApiError
from ..services.group import same_group, shared_records, enroll

router = APIRouter(prefix='/api/v1', tags=['study-group'])


@router.get('/group/members')
def members(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(select(User).where(User.status == 'active').order_by(User.id)).all()
    return ok([{'id': row.id, 'nickname': row.nickname, 'avatar_key': row.avatar_key or '',
        'is_private_mode': bool(row.is_private_mode), 'status': 'private' if row.is_private_mode else 'shared'}
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


@router.post('/group/presence')
def presence(body: HeartbeatInput, user=Depends(get_current_user), db=Depends(get_db)):
    ids=db.scalars(select(RoomMember.room_id).join(Room,Room.id==RoomMember.room_id).where(
        RoomMember.user_id==user.id,Room.dissolved_at.is_(None))).all()
    for rid in ids:
        row=db.scalar(select(RoomPresence).where(RoomPresence.room_id==rid,RoomPresence.user_id==user.id))
        if row is None:
            row=RoomPresence(room_id=rid,user_id=user.id);db.add(row)
        for key,value in body.model_dump().items(): setattr(row,key,value)
        if body.status!='focusing': row.focus_started_at=None
        row.last_heartbeat_at=utcnow()
    db.commit()
    return ok({'status':body.status})
