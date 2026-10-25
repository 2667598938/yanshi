"""多自习室：列表、创建、凭码加入、房主管理、房内状态与留言。"""
from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from ..deps import audit, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import Room, User
from ..schemas.room import GoalInput, HeartbeatInput, MessageInput, RoomCreate, RoomJoin, RoomUpdate
from ..services import room as room_service

router = APIRouter(prefix='/api/v1/rooms', tags=['rooms'])


@router.get('')
def list_rooms(db=Depends(get_db), user: User = Depends(get_current_user)):
    return ok(room_service.list_rooms(db, user))


@router.post('')
def create_room(body: RoomCreate, request: Request, db=Depends(get_db),
                user: User = Depends(get_current_user)):
    request.app.state.transient.limit(f'room-create:{user.id}', 5, 3600)
    room = room_service.create_room(db, user, body.name, body.intro, body.visibility)
    audit(db, request, 'room.create', user_id=user.id, detail=f'{room.id} {room.name}')
    db.commit()
    return ok(room_service.room_summary(db, room, user))


@router.post('/join-by-code')
def join_by_code(body: RoomJoin, request: Request, db=Depends(get_db),
                 user: User = Depends(get_current_user)):
    code = body.code.strip().upper()
    if len(code) > 32:
        raise ApiError(400, 40001, '房间码不正确')
    room = db.scalar(select(Room).where(
        Room.code == code, Room.dissolved_at.is_(None)))
    if room is None:
        raise ApiError(404, 40401, '房间码不存在')
    state = room_service.join_room(db, user, room, code)
    audit(db, request, 'room.join_by_code', user_id=user.id, detail=str(room.id))
    db.commit()
    return ok(state)


@router.get('/{room_id}')
def get_room(room_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    room = room_service.get_room(db, room_id)
    return ok(room_service.room_state(db, user, room))


@router.post('/{room_id}/join')
def join_room(room_id: int, body: RoomJoin, request: Request, db=Depends(get_db),
              user: User = Depends(get_current_user)):
    room = room_service.get_room(db, room_id)
    state = room_service.join_room(db, user, room, body.code)
    audit(db, request, 'room.join', user_id=user.id, detail=str(room_id))
    db.commit()
    return ok(state)


@router.post('/{room_id}/leave')
def leave_room(room_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    return ok(room_service.leave_room(db, user, room_service.get_room(db, room_id)))


@router.patch('/{room_id}')
def update_room(room_id: int, body: RoomUpdate, db=Depends(get_db),
                user: User = Depends(get_current_user)):
    room = room_service.get_room(db, room_id)
    return ok(room_service.update_room(db, user, room, body.name, body.intro, body.visibility))


@router.post('/{room_id}/code')
def regenerate_code(room_id: int, db=Depends(get_db),
                    user: User = Depends(get_current_user)):
    room = room_service.get_room(db, room_id)
    return ok(room_service.regenerate_code(db, user, room))


@router.delete('/{room_id}/members/{uid}')
def kick_member(room_id: int, uid: int, db=Depends(get_db),
                user: User = Depends(get_current_user)):
    room = room_service.get_room(db, room_id)
    return ok(room_service.kick_member(db, user, room, uid))


@router.delete('/{room_id}')
def dissolve_room(room_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    room = room_service.get_room(db, room_id)
    return ok(room_service.dissolve_room(db, user, room))


@router.get('/{room_id}/ranking')
def get_ranking(room_id: int, range: Literal['today', 'week', 'all'] = 'today',
                db=Depends(get_db), user: User = Depends(get_current_user)):
    state = room_service.room_state(db, user, room_service.get_room(db, room_id))
    return ok({'range': range, 'items': state['ranking'][range],
               'nicknames': {m['user_id']: m['nickname'] for m in state['members']}})


@router.post('/{room_id}/heartbeat')
def heartbeat(room_id: int, body: HeartbeatInput, request: Request, db=Depends(get_db),
              user: User = Depends(get_current_user)):
    request.app.state.transient.limit(f'room-hb:{user.id}', 60, 60)
    room = room_service.get_room(db, room_id)
    return ok(room_service.heartbeat(db, user, body, room))


@router.post('/{room_id}/messages')
def post_message(room_id: int, body: MessageInput, request: Request, db=Depends(get_db),
                 user: User = Depends(get_current_user)):
    request.app.state.transient.limit(f'room-msg:{user.id}', 20, 60)
    room = room_service.get_room(db, room_id)
    content = body.content.strip()
    if not content:
        raise ApiError(400, 40001, '留言不能为空')
    return ok(room_service.add_message(db, user, content, room))


@router.delete('/{room_id}/messages/{message_id}')
def remove_message(room_id: int, message_id: int, db=Depends(get_db),
                   user: User = Depends(get_current_user)):
    room = room_service.get_room(db, room_id)
    return ok(room_service.delete_message(db, user, message_id, user.role == 'admin', room))


@router.put('/{room_id}/goal')
def set_goal(room_id: int, body: GoalInput, db=Depends(get_db),
             user: User = Depends(get_current_user)):
    room = room_service.get_room(db, room_id)
    return ok(room_service.upsert_goal(db, user, body, room))
