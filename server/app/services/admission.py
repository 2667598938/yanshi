"""账号名额独立于房间容量；0表示不设置账号数上限。"""
from sqlalchemy import select, update
from ..models import User
from ..errors import ApiError


def check_capacity(db, settings):
    if not settings.account_max_users: return
    # 同一管理员行提供MySQL写锁，SQLite写事务亦由此串行化；无副作用地保持版本值。
    db.execute(update(User).where(User.role == 'admin').values(token_version=User.token_version))
    ids = db.scalars(select(User.id).where(User.status != 'deleted').with_for_update()).all()
    if len(ids) >= settings.account_max_users:
        raise ApiError(403, 40301, f'当前内测账号名额已满（{settings.account_max_users}人）')
