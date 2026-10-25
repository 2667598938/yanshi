"""本人梦校：个人CRUD、多图相册和排序；旧全局目录仅作首次可删除示例。"""
import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
import threading
from sqlalchemy.exc import IntegrityError

from ..deps import require_enabled_feature, get_admin, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import School, Attachment, User
from ..schemas.school import SchoolInput, SchoolUpdate
from ..serializers import iso
from ..time import utcnow

router = APIRouter(prefix='/api/v1', tags=['schools'], dependencies=[Depends(require_enabled_feature('dream_school'))])


school_lock = threading.RLock()

def initialize_schools(db, user):
    with school_lock:
        db.refresh(user, with_for_update=True)
        if user.schools_initialized: return
        for source in db.scalars(select(School).where(School.owner_id.is_(None))).all():
            db.add(School(owner_id=user.id,key=source.key,name=source.name,short=source.short,
                logo_key=source.logo_key,album_keys=source.album_keys,info=source.info,
                is_builtin=source.is_builtin,sort_order=source.sort_order))
        user.schools_initialized = True
        db.commit()

def owned_school(db, user, key):
    initialize_schools(db,user)
    row = db.scalar(select(School).where(School.key == key,School.owner_id == user.id))
    if not row: raise ApiError(404,40401,'院校不存在')
    return row


def validate_school_images(db, keys, user):
    from ..services.attachments import can_view
    for key in set(keys) - {''}:
        row=db.scalar(select(Attachment).where(Attachment.object_key==key,Attachment.biz_type=='school',Attachment.deleted_at.is_(None)))
        if not row or not can_view(row,user,db):
            raise ApiError(400, 40001, '院校图片必须使用校园图片上传入口生成的有效附件')


def to_dict(row: School):
    return {
        'key': row.key, 'name': row.name, 'short': row.short,
        'logo_key': row.logo_key or '',
        'album_keys': json.loads(row.album_keys or '[]'),
        'info': json.loads(row.info or '{}'),
        'is_builtin': bool(row.is_builtin), 'sort_order': row.sort_order,
        'updated_at': iso(row.updated_at),
    }


@router.get('/schools')
def list_schools(db=Depends(get_db), user=Depends(get_current_user)):
    initialize_schools(db,user)
    rows = db.scalars(select(School).where(School.owner_id == user.id).order_by(School.sort_order, School.id)).all()
    return ok([to_dict(r) for r in rows])


@router.get('/schools/{key}')
def get_school(key: str, db=Depends(get_db), user=Depends(get_current_user)):
    row = owned_school(db,user,key)
    return ok(to_dict(row))


@router.post('/schools')
@router.post('/admin/schools')
def create_school(body: SchoolInput, db=Depends(get_db), admin=Depends(get_current_user)):
    initialize_schools(db,admin)
    validate_school_images(db, [body.logo_key, *body.album_keys], admin)
    if db.scalar(select(School.id).where(School.key == body.key,School.owner_id == admin.id)):
        raise ApiError(409, 40901, '院校标识已存在')
    now = utcnow()
    row = School(
        owner_id=admin.id, key=body.key, name=body.name, short=body.short or body.name,
        logo_key=body.logo_key, album_keys=json.dumps(body.album_keys, ensure_ascii=False),
        info=json.dumps(body.info, ensure_ascii=False), is_builtin=False,
        sort_order=body.sort_order, created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    return ok(to_dict(row))


@router.put('/schools/{key}')
@router.put('/admin/schools/{key}')
def update_school(key: str, body: SchoolUpdate, db=Depends(get_db),
                  admin=Depends(get_current_user)):
    row = owned_school(db,admin,key)
    validate_school_images(db, [body.logo_key or '', *(body.album_keys or [])], admin)
    if body.name:
        row.name = body.name
    if body.short:
        row.short = body.short
    if body.logo_key is not None:
        row.logo_key = body.logo_key
    if body.album_keys is not None:
        row.album_keys = json.dumps(body.album_keys, ensure_ascii=False)
    if body.info is not None:
        row.info = json.dumps(body.info, ensure_ascii=False)
    if body.sort_order is not None: row.sort_order = body.sort_order
    row.updated_at = utcnow()
    db.commit()
    return ok(to_dict(row))


@router.delete('/schools/{key}')
def delete_school(key: str, db=Depends(get_db), user=Depends(get_current_user)):
    row=owned_school(db,user,key)
    db.delete(row); db.commit()
    return ok()
