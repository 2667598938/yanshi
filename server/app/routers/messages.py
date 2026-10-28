"""站内消息中心：列表、未读数、已读与全部已读。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, update

from ..deps import get_current_user, get_db
from ..errors import ApiError, ok
from ..models import Message
from ..services.messages import message_dict
from ..time import utcnow

router = APIRouter(prefix='/api/v1/messages', tags=['messages'])


@router.get('')
def list_messages(limit: int = 50, before_id: int | None = None,
                  user=Depends(get_current_user), db=Depends(get_db)):
    limit = min(max(limit, 1), 100)
    query = select(Message).where(Message.user_id == user.id)
    if before_id:
        query = query.where(Message.id < before_id)
    rows = db.scalars(query.order_by(Message.id.desc()).limit(limit)).all()
    return ok([message_dict(r) for r in rows])


@router.get('/unread-count')
def unread_count(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(select(Message.id).where(
        Message.user_id == user.id, Message.is_read.is_(False))).all()
    return ok({'count': len(rows)})


@router.post('/{mid}/read')
def mark_read(mid: int, user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(Message, mid)
    if not row or row.user_id != user.id:
        raise ApiError(404, 40401, '消息不存在')
    if not row.is_read:
        row.is_read = True
        db.commit()
    return ok(message_dict(row))


@router.post('/read-all')
def mark_all_read(user=Depends(get_current_user), db=Depends(get_db)):
    db.execute(update(Message).where(
        Message.user_id == user.id, Message.is_read.is_(False)
    ).values(is_read=True))
    db.commit()
    return ok({'read_at': utcnow().isoformat() + 'Z'})
