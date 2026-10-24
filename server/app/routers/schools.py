"""院校库：普通成员只读，管理员维护。用户个人梦校关系走同步 type=userSchool。"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy import select

from ..deps import get_admin, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import School
from ..schemas.school import SchoolInput, SchoolUpdate
from ..serializers import iso
from ..time import utcnow

router = APIRouter(prefix='/api/v1', tags=['schools'])


def to_dict(row: School):
    return {
        'key': row.key, 'name': row.name, 'short': row.short,
        'logo_key': row.logo_key or '',
        'album_keys': json.loads(row.album_keys or '[]'),
        'info': json.loads(row.info or '{}'),
        'is_builtin': bool(row.is_builtin),
        'updated_at': iso(row.updated_at),
    }


@router.get('/schools')
def list_schools(db=Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(School).order_by(School.sort_order, School.id)).all()
    return ok([to_dict(r) for r in rows])


@router.get('/schools/{key}')
def get_school(key: str, db=Depends(get_db), user=Depends(get_current_user)):
    row = db.scalar(select(School).where(School.key == key))
    if not row:
        raise ApiError(404, 40401, '院校不存在')
    return ok(to_dict(row))


@router.post('/admin/schools')
def create_school(body: SchoolInput, db=Depends(get_db), admin=Depends(get_admin)):
    if db.scalar(select(School.id).where(School.key == body.key)):
        raise ApiError(409, 40901, '院校标识已存在')
    now = utcnow()
    row = School(
        key=body.key, name=body.name, short=body.short or body.name,
        logo_key=body.logo_key, album_keys=json.dumps(body.album_keys, ensure_ascii=False),
        info=json.dumps(body.info, ensure_ascii=False), is_builtin=False,
        sort_order=999, created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    return ok(to_dict(row))


@router.put('/admin/schools/{key}')
def update_school(key: str, body: SchoolUpdate, db=Depends(get_db),
                  admin=Depends(get_admin)):
    row = db.scalar(select(School).where(School.key == key))
    if not row:
        raise ApiError(404, 40401, '院校不存在')
    if body.name:
        row.name = body.name
    if body.short:
        row.short = body.short
    if body.logo_key:
        row.logo_key = body.logo_key
    if body.album_keys is not None:
        row.album_keys = json.dumps(body.album_keys, ensure_ascii=False)
    if body.info is not None:
        row.info = json.dumps(body.info, ensure_ascii=False)
    row.updated_at = utcnow()
    db.commit()
    return ok(to_dict(row))
