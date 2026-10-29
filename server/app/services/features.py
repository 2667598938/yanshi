"""功能授权：VIP 或审批通过的 user_feature_grants 才是唯一事实源。"""
from sqlalchemy import select

from ..errors import ApiError
from ..models import UserFeatureGrant
from ..time import utcnow


def is_vip(user) -> bool:
    return bool(user is not None and (user.vip_permanent or (user.vip_until and user.vip_until > utcnow())))


def has_feature(db, user, feature: str) -> bool:
    if is_vip(user):
        return True
    if user is None:
        return False
    row = db.scalar(select(UserFeatureGrant).where(
        UserFeatureGrant.user_id == user.id,
        UserFeatureGrant.feature == feature,
        UserFeatureGrant.revoked_at.is_(None)))
    return row is not None


def require_feature(db, user, feature: str, message: str = '该功能需要 VIP 或审批授权'):
    if not has_feature(db, user, feature):
        raise ApiError(403, 40301, message)


def grant_feature(db, user_id: int, feature: str, admin_id=None, request_id=None):
    row = db.scalar(select(UserFeatureGrant).where(
        UserFeatureGrant.user_id == user_id,
        UserFeatureGrant.feature == feature))
    if row is None:
        db.add(UserFeatureGrant(user_id=user_id, feature=feature,
                                granted_by=admin_id, source_request_id=request_id,
                                granted_at=utcnow()))
    else:
        row.revoked_at = None
        row.granted_by = admin_id
        row.source_request_id = request_id
        row.granted_at = utcnow()


def revoke_feature(db, user_id: int, feature: str, request_id=None):
    row = db.scalar(select(UserFeatureGrant).where(
        UserFeatureGrant.user_id == user_id,
        UserFeatureGrant.feature == feature,
        UserFeatureGrant.revoked_at.is_(None)))
    if row is not None and (request_id is None or row.source_request_id == request_id):
        row.revoked_at = utcnow()
