"""账号名额独立于房间容量；0表示不设置账号数上限。"""
from sqlalchemy import func, select, update
from ..models import User
from ..errors import ApiError


def registration_slots(db, settings):
    if not settings.account_max_users:
        return None
    count = db.scalar(select(func.count(User.id)).where(User.status != 'deleted'))
    return max(0, settings.account_max_users - count)


def check_capacity(db, settings):
    if not settings.account_max_users: return
    # 同一管理员行提供MySQL写锁，SQLite写事务亦由此串行化；无副作用地保持版本值。
    db.execute(update(User).where(User.role == 'admin').values(token_version=User.token_version))
    if settings.is_sqlite:
        full = registration_slots(db, settings) == 0
    else:
        ids = db.scalars(select(User.id).where(User.status != 'deleted')
                         .limit(settings.account_max_users).with_for_update()).all()
        full = len(ids) >= settings.account_max_users
    if full:
        raise ApiError(403, 40301, f'本站注册名额已满（{settings.account_max_users} 人）')
