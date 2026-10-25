"""图片只接受本人现有附件，永不接受客户端任意URL供服务器抓取。"""
import base64
from sqlalchemy import select
from ..models import Attachment
from ..errors import ApiError
from .image_storage import ImageStorage


def user_content(db, settings, user_id, text, image_keys, *, strict=True):
    if not image_keys: return text
    if len(image_keys) > 4: raise ApiError(400, 40001, '每次最多4张图片')
    parts = [{'type': 'text', 'text': text}]
    storage = ImageStorage(settings)
    for key in dict.fromkeys(image_keys):
        row = db.scalar(select(Attachment).where(Attachment.object_key == key,
            Attachment.uploader_id == user_id, Attachment.deleted_at.is_(None),
            Attachment.biz_type.in_(['mistake', 'ai'])))
        if not row:
            if strict: raise ApiError(400, 40001, '图片不存在、已删除或不属于本人')
            continue
        if settings.image_storage == 'qiniu': url = storage.presigned_url(key)
        else:
            path = storage.path(key)
            if not path.is_file():
                if strict: raise ApiError(400, 40001, '图片文件已不可用，请重新上传')
                continue
            if path.stat().st_size > settings.image_max_bytes: raise ApiError(400, 40001, '图片过大')
            url = 'data:image/jpeg;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
        parts.append({'type': 'image_url', 'image_url': {'url': url}})
    if len(parts) == 1: return text + '\n[历史附件已不可用]'
    return parts
