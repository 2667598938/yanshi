"""图片处理与附件编排（4 人私密版：无审核，统一转 JPEG，按用户配额）。"""
import secrets
import json
import tempfile
import threading
import warnings
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import func, select

from ..errors import ApiError
from ..models import Attachment, Inspiration, School
from ..time import utcnow

Image.MAX_IMAGE_PIXELS = 4096 * 4096
PROCESS_SLOTS = threading.BoundedSemaphore(2)
FORMATS = {
    'JPEG': ('image/jpeg', {'.jpg', '.jpeg'}),
    'PNG': ('image/png', {'.png'}),
    'WEBP': ('image/webp', {'.webp'}),
}
AVATAR_SIZE = 512
MAX_EDGE = 2048


def transform(upload, *, avatar, max_bytes):
    """读取上传图片，校验后统一转为 JPEG；头像居中裁剪为方形。返回 (file,size,w,h)。"""
    if not PROCESS_SLOTS.acquire(timeout=1):
        raise ApiError(429, 42901, '图片正在处理中，请稍后重试')
    result = None
    try:
        upload.file.seek(0, 2)
        size = upload.file.tell()
        upload.file.seek(0)
        if size <= 0 or size > max_bytes:
            raise ApiError(400, 40001, '图片为空或超出大小限制')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(upload.file) as probe:
                if probe.format not in FORMATS:
                    raise ValueError('bad format')
                mime, suffixes = FORMATS[probe.format]
                if upload.content_type != mime or Path(upload.filename or '').suffix.lower() not in suffixes:
                    raise ValueError('bad mime/ext')
                if min(probe.size) < 1 or max(probe.size) > 4096:
                    raise ValueError('bad dims')
                probe.verify()
            upload.file.seek(0)
            with Image.open(upload.file) as original:
                image = ImageOps.exif_transpose(original)
                image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
                if avatar:
                    image = ImageOps.fit(image, (AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)
                if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
                    rgba = image.convert('RGBA')
                    flat = Image.new('RGB', rgba.size, 'white')
                    flat.paste(rgba, mask=rgba.getchannel('A'))
                    image = flat
                else:
                    image = image.convert('RGB')
                result = tempfile.SpooledTemporaryFile(max_size=64 * 1024, mode='w+b')
                image.save(result, format='JPEG', quality=88)
                size = result.tell()
                result.seek(0)
                return result, size, image.width, image.height
    except ApiError:
        raise
    except Exception:
        if result:
            result.close()
        raise ApiError(400, 40001, '图片无效；仅接受 JPG/PNG/WebP，边长不超过 4096') from None
    finally:
        PROCESS_SLOTS.release()


def used_bytes(db, user_id):
    value = db.scalar(select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
        Attachment.uploader_id == user_id, Attachment.deleted_at.is_(None)))
    return int(value or 0)


def can_view(row, user, db=None):
    if row.deleted_at:
        return False
    if row.uploader_id == user.id or user.role == 'admin':
        return True
    if row.biz_type == 'inspiration' and db is not None:
        return db.scalar(select(Inspiration.id).where(
            Inspiration.image_key == row.object_key,
            Inspiration.status == 'approved').limit(1)) is not None
    if row.biz_type == 'school' and db is not None:
        return any(school.logo_key == row.object_key or row.object_key in json.loads(school.album_keys or '[]')
                   for school in db.scalars(select(School)).all())
    return row.biz_type == 'avatar'   # 头像在自习室互相可见，其余仅本人


def create_attachment(db, settings, user, biz_type, processed, size, width, height):
    if used_bytes(db, user.id) + size > settings.storage_quota_bytes:
        raise ApiError(403, 40301, '图片存储配额不足（每人 200MB）')
    key = f'{biz_type}/{user.id}/{secrets.token_hex(16)}.jpg'
    row = Attachment(
        object_key=key, storage_backend=settings.image_storage,
        uploader_id=user.id, biz_type=biz_type, content_type='image/jpeg',
        size_bytes=size, width=width, height=height, created_at=utcnow())
    db.add(row)
    db.flush()
    return row


def mark_deleted(row):
    if not row.deleted_at:
        row.deleted_at = utcnow()
