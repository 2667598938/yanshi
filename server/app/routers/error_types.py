"""错题 · 用户自定义错误类型。预置 6 类不落库，自定义类型按用户隔离。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..deps import get_current_user, get_db
from ..errors import ApiError, ok
from ..models import UserErrorType
from ..schemas.account import ErrorTypeInput
from ..serializers import iso

router = APIRouter(prefix='/api/v1/mistake', tags=['mistake'])

PRESETS = [
    {'id': 'calc', 'name': '计算失误'},
    {'id': 'concept', 'name': '概念不清'},
    {'id': 'review', 'name': '审题错误'},
    {'id': 'method', 'name': '思路/方法'},
    {'id': 'careless', 'name': '粗心大意'},
    {'id': 'other', 'name': '其他'},
]


def _dict(row):
    return {'id': row.id, 'name': row.name, 'created_at': iso(row.created_at)}


@router.get('/error-types')
def list_error_types(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(select(UserErrorType).where(
        UserErrorType.user_id == user.id).order_by(UserErrorType.id)).all()
    return ok({'presets': PRESETS, 'custom': [_dict(r) for r in rows]})


@router.post('/error-types')
def create_error_type(body: ErrorTypeInput, user=Depends(get_current_user),
                      db=Depends(get_db)):
    total = len(db.scalars(select(UserErrorType.id).where(
        UserErrorType.user_id == user.id)).all())
    if total >= 30:
        raise ApiError(400, 40001, '自定义错误类型最多 30 个')
    row = UserErrorType(user_id=user.id, name=body.name.strip())
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, 40901, '该类型已存在') from None
    db.refresh(row)
    return ok(_dict(row))


@router.put('/error-types/{tid}')
def rename_error_type(tid: int, body: ErrorTypeInput, user=Depends(get_current_user),
                      db=Depends(get_db)):
    row = db.get(UserErrorType, tid)
    if not row or row.user_id != user.id:
        raise ApiError(404, 40401, '错误类型不存在')
    row.name = body.name.strip()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, 40901, '该类型已存在') from None
    return ok(_dict(row))


@router.delete('/error-types/{tid}')
def delete_error_type(tid: int, user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(UserErrorType, tid)
    if not row or row.user_id != user.id:
        raise ApiError(404, 40401, '错误类型不存在')
    db.delete(row)
    db.commit()
    return ok()
