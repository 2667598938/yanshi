"""图片附件接口（头像 / 错题 / 梦校相册）。"""
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, Response
from sqlalchemy import select
from starlette.concurrency import run_in_threadpool

from ..deps import audit, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import Attachment, User
from ..services import attachments as logic
from ..services.image_storage import ImageStorage

router = APIRouter(prefix='/api/v1/attachments', tags=['attachments'])


def _payload(row):
    return {'key': row.object_key, 'biz_type': row.biz_type,
            'width': row.width, 'height': row.height, 'size': row.size_bytes}


async def _save(db, settings, user, biz_type, file, avatar, max_bytes):
    processed, size, w, h = await run_in_threadpool(
        logic.transform, file, avatar=avatar, max_bytes=max_bytes)
    try:
        row = await run_in_threadpool(
            logic.create_attachment, db, settings, user, biz_type, processed, size, w, h)
        storage = ImageStorage(settings)
        await run_in_threadpool(storage.save, row.object_key, processed, size)
        return row
    except Exception:
        db.rollback()
        raise
    finally:
        processed.close()


@router.post('/avatar')
async def upload_avatar(request: Request, file: UploadFile = File(...),
                        user: User = Depends(get_current_user), db=Depends(get_db)):
    if user.status != 'active':
        raise ApiError(403, 40301, '当前账号状态不能上传')
    request.app.state.transient.limit(f'upload:{user.id}', 30, 60)
    settings = request.app.state.settings
    old_key = user.avatar_key
    row = await _save(db, settings, user, 'avatar', file, True,
                      settings.image_max_avatar_bytes)
    user.avatar_key = row.object_key
    if old_key:
        old = db.scalar(select(Attachment).where(Attachment.object_key == old_key))
        if old:
            logic.mark_deleted(old)
    audit(db, request, 'avatar.update', user_id=user.id)
    db.commit()
    return ok(_payload(row))


@router.post('/image')
async def upload_image(request: Request, biz: Literal['mistake', 'school', 'inspiration', 'ai'] = 'mistake',
                       file: UploadFile = File(...),
                       user: User = Depends(get_current_user), db=Depends(get_db)):
    if user.status != 'active':
        raise ApiError(403, 40301, '当前账号状态不能上传')
    request.app.state.transient.limit(f'upload:{user.id}', 30, 60)
    settings = request.app.state.settings
    if biz == 'ai':
        from ..services.features import require_feature
        require_feature(db, user, 'ai')
        if not settings.ai_vision_enabled: raise ApiError(403, 40310, 'AI图片功能暂未开放')
    row = await _save(db, settings, user, biz, file, False, settings.image_max_bytes)
    db.commit()
    return ok(_payload(row))


@router.get('/view')
def view(key: str, request: Request, user: User = Depends(get_current_user), db=Depends(get_db)):
    row = db.scalar(select(Attachment).where(Attachment.object_key == key))
    if not row or not logic.can_view(row, user, db):
        raise ApiError(404, 40401, '图片不存在或无权查看')
    settings = request.app.state.settings
    storage = ImageStorage.for_attachment(settings, row)
    if row.storage_backend == 'local':
        path = storage.path(key)
        if not path.is_file():
            raise ApiError(404, 40401, '图片文件不存在')
        return FileResponse(path, media_type='image/jpeg',
                            headers={'Cache-Control': 'private, no-store'})
    if row.biz_type in {'mistake','ai'}:
        return Response(storage.read_private(key),media_type='image/jpeg',headers={'Cache-Control':'private, no-store'})
    return RedirectResponse(storage.presigned_url(key), status_code=302)


@router.get('/storage')
def storage(request: Request, user: User = Depends(get_current_user),
            db=Depends(get_db)):
    settings = request.app.state.settings
    return ok(logic.storage_summary(db, user.id, settings.storage_quota_bytes))


@router.post('/reclaim')
def reclaim(request: Request, user: User = Depends(get_current_user),
            db=Depends(get_db)):
    rows = logic.orphan_attachments(db, user.id)
    freed = 0
    deleted = []
    failures = []
    for row in rows:
        try:
            storage = ImageStorage.for_attachment(request.app.state.settings, row)
            storage.delete(row.object_key)
        except ApiError:
            failures.append(row.object_key)
            continue
        logic.mark_deleted(row)
        freed += int(row.size_bytes or 0)
        deleted.append(row.object_key)
    audit(db, request, 'image.reclaim', user_id=user.id,
          detail=f'{len(deleted)} items {freed} bytes')
    db.commit()
    return ok({
        'deleted': len(deleted),
        'freed_bytes': freed,
        'failed': len(failures),
        'grace_hours': logic.ORPHAN_GRACE_HOURS,
    })


@router.delete('')
def delete_attachment(key: str, request: Request, user: User = Depends(get_current_user),
                      db=Depends(get_db)):
    row = db.scalar(select(Attachment).where(Attachment.object_key == key))
    if not row or (row.uploader_id != user.id and (user.role != 'admin' or row.biz_type in {'mistake','ai'})):
        raise ApiError(404, 40401, '图片不存在')
    logic.mark_deleted(row)
    if user.avatar_key == key:
        user.avatar_key = ''
    audit(db, request, 'image.delete', user_id=user.id, detail=key)
    db.commit()
    return ok()
