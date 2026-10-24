"""四人自习室接口（固定房间、状态同步、无视频）。"""
from typing import Literal

from fastapi import APIRouter, Depends, Request

from ..deps import get_current_user, get_db
from ..errors import ApiError, ok
from ..models import User
from ..schemas.room import GoalInput, HeartbeatInput, MessageInput
from ..services import room as room_service

router = APIRouter(prefix='/api/v1/room', tags=['room'])


@router.get('')
def get_room(db=Depends(get_db), user: User = Depends(get_current_user)):
    return ok(room_service.room_state(db, user))


@router.get('/ranking')
def get_ranking(range: Literal['today', 'week', 'all'] = 'today',
                db=Depends(get_db), user: User = Depends(get_current_user)):
    state = room_service.room_state(db, user)
    return ok({'range': range, 'items': state['ranking'][range],
               'nicknames': {m['user_id']: m['nickname'] for m in state['members']}})


@router.post('/heartbeat')
def heartbeat(body: HeartbeatInput, request: Request, db=Depends(get_db),
              user: User = Depends(get_current_user)):
    request.app.state.transient.limit(f'room-hb:{user.id}', 60, 60)
    return ok(room_service.heartbeat(db, user, body))


@router.post('/messages')
def post_message(body: MessageInput, request: Request, db=Depends(get_db),
                 user: User = Depends(get_current_user)):
    request.app.state.transient.limit(f'room-msg:{user.id}', 20, 60)
    content = body.content.strip()
    if not content:
        raise ApiError(400, 40001, '留言不能为空')
    return ok(room_service.add_message(db, user, content))


@router.delete('/messages/{message_id}')
def remove_message(message_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    return ok(room_service.delete_message(db, user, message_id, user.role == 'admin'))


@router.put('/goal')
def set_goal(body: GoalInput, db=Depends(get_db), user: User = Depends(get_current_user)):
    return ok(room_service.upsert_goal(db, user, body))
