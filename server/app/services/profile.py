"""直接资料编辑与通用同步共用版本，防止旧本机快照覆盖管理员更新。"""
import json
from functools import wraps
from ..models import LearningRecord, LearningChange
from ..schemas.account import ProfileUpdate
from ..time import utcnow


def profile_write(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        from .sync import sync_write_lock
        with sync_write_lock:
            return function(*args, **kwargs)
    return guarded


def snapshot_profile(db, user):
    value = {field: getattr(user, field) for field in ProfileUpdate.model_fields if field not in {'privacy_mode','is_private_mode'}}
    record = {'id': 'profile', 'key': 'profile', 'type': 'profile', 'value': value}
    row = db.get(LearningRecord, (user.id, 'profile'))
    revision = row.revision + 1 if row else 1
    body = json.dumps(record, ensure_ascii=False, separators=(',', ':'))
    if row:
        row.body, row.revision, row.deleted, row.updated_at = body, revision, 0, utcnow()
    else:
        db.add(LearningRecord(user_id=user.id, id='profile', body=body, revision=revision, deleted=0))
    db.add(LearningChange(user_id=user.id, record_id='profile', revision=revision))
