"""图片附件接口（头像 / 错题 / 梦校相册）。"""
from typing import Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
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
async def upload_image(request: Request, biz: Literal['mistake', 'school', 'inspiration'] = 'mistake',
                       file: UploadFile = File(...),
                       user: User = Depends(get_current_user), db=Depends(get_db)):
    if user.status != 'active':
        raise ApiError(403, 40301, '当前账号状态不能上传')
    request.app.state.transient.limit(f'upload:{user.id}', 30, 60)
    settings = request.app.state.settings
    row = await _save(db, settings, user, biz, file, False, settings.image_max_bytes)
    db.commit()
    return ok(_payload(row))


@router.get('/view')
def view(key: str, request: Request, user: User = Depends(get_current_user), db=Depends(get_db)):
    row = db.scalar(select(Attachment).where(Attachment.object_key == key))
    if not row or not logic.can_view(row, user, db):
        raise ApiError(404, 40401, '图片不存在或无权查看')
    settings = request.app.state.settings
    storage = ImageStorage(settings)
    if settings.image_storage != 'qiniu':
        path = storage.path(key)
        if not path.is_file():
            raise ApiError(404, 40401, '图片文件不存在')
        return FileResponse(path, media_type='image/jpeg',
                            headers={'Cache-Control': 'private, max-age=3600'})
    return RedirectResponse(storage.presigned_url(key), status_code=302)


@router.delete('')
def delete_attachment(key: str, request: Request, user: User = Depends(get_current_user),
                      db=Depends(get_db)):
    row = db.scalar(select(Attachment).where(Attachment.object_key == key))
    if not row or (row.uploader_id != user.id and user.role != 'admin'):
        raise ApiError(404, 40401, '图片不存在')
    logic.mark_deleted(row)
    if user.avatar_key == key:
        user.avatar_key = ''
    audit(db, request, 'image.delete', user_id=user.id, detail=key)
    db.commit()
    return ok()
