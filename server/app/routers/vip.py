"""运营体系：VIP 状态 / 邀请码核销 / 功能申请。"""
import math
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update, or_
from sqlalchemy.exc import IntegrityError

from ..deps import audit, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import FeatureRequest, Invite
from ..schemas.account import FeatureRequestInput, VipRedeemInput
from ..serializers import iso
from ..services.transient import digest
from ..time import utcnow
from ..services.features import is_vip as user_is_vip

router = APIRouter(prefix='/api/v1', tags=['vip'])

FEATURE_LABELS = {
    'ai': 'AI 问答权限',
    'materials': '资料区完整链接',
    'room': '云端自习室',
    'other': '其他功能',
}


def vip_payload(user):
    now = utcnow()
    active = user_is_vip(user)
    days_left = None if user.vip_permanent else math.ceil((user.vip_until - now).total_seconds() / 86400) if active else 0
    return {
        'is_vip': active,
        'vip_until': iso(user.vip_until),
        'vip_permanent': bool(user.vip_permanent),
        'days_left': days_left,
    }


def request_dict(row):
    return {
        'id': row.id, 'feature': row.feature,
        'feature_label': FEATURE_LABELS.get(row.feature, row.feature),
        'reason': row.reason, 'status': row.status,
        'review_note': row.review_note or '',
        'created_at': iso(row.created_at), 'reviewed_at': iso(row.reviewed_at),
    }


# ---------------------------------------------------------------- VIP
@router.get('/vip/status')
def vip_status(user=Depends(get_current_user)):
    return ok(vip_payload(user))


@router.post('/vip/redeem')
def redeem(body: VipRedeemInput, request: Request, user=Depends(get_current_user),
           db=Depends(get_db)):
    now = utcnow()
    db.refresh(user, with_for_update=True)
    if user.vip_permanent:
        raise ApiError(400, 40001, '永久VIP无需兑换续期')
    code_hash = digest(body.code.strip().upper())
    claimed = db.execute(update(Invite).where(Invite.code_hash == code_hash,
        Invite.used_by.is_(None), Invite.revoked_at.is_(None), Invite.vip_days > 0,
        or_(Invite.expires_at.is_(None), Invite.expires_at >= now)).values(used_by=user.id, used_at=now)).rowcount
    if claimed != 1:
        raise ApiError(400, 40001, '邀请码无效、已使用或已过期')
    invite = db.scalar(select(Invite).where(Invite.code_hash == code_hash).execution_options(populate_existing=True))
    db.refresh(user, with_for_update=True)
    if user.vip_permanent:
        raise ApiError(400, 40001, '永久VIP无需兑换续期')
    base = user.vip_until if (user.vip_until and user.vip_until > now) else now
    user.vip_until = base + timedelta(days=invite.vip_days)
    user.vip_expiry_notified_until = None
    audit(db, request, 'vip.redeem', user_id=user.id,
          detail=f'{invite.hint} +{invite.vip_days}d')
    db.commit()
    return ok({**vip_payload(user), 'granted_days': invite.vip_days})


# ---------------------------------------------------------------- 功能申请
@router.get('/requests/mine')
def my_requests(user=Depends(get_current_user), db=Depends(get_db)):
    if not user_is_vip(user):
        changed = db.execute(update(FeatureRequest).where(FeatureRequest.user_id == user.id,
            FeatureRequest.approval_source == 'vip', FeatureRequest.status == 'approved')
            .values(status='revoked', active_key=None)).rowcount
        if changed: db.commit()
    rows = db.scalars(select(FeatureRequest).where(
        FeatureRequest.user_id == user.id).order_by(FeatureRequest.id.desc())).all()
    return ok([request_dict(r) for r in rows])


@router.post('/requests')
def create_request(body: FeatureRequestInput, request: Request,
                   user=Depends(get_current_user), db=Depends(get_db)):
    if not user_is_vip(user):
        db.execute(update(FeatureRequest).where(FeatureRequest.user_id == user.id,
            FeatureRequest.approval_source == 'vip', FeatureRequest.status == 'approved').values(status='revoked', active_key=None))
    pending = db.scalar(select(FeatureRequest.id).where(
        FeatureRequest.user_id == user.id,
        FeatureRequest.feature == body.feature,
        FeatureRequest.status.in_(('pending', 'approved'))))
    if pending:
        raise ApiError(409, 40901, '该功能已申请或已开通')
    # VIP 免审核：直接通过，留痕便于回溯
    is_vip = user_is_vip(user)
    row = FeatureRequest(user_id=user.id, feature=body.feature, reason=body.reason,
                         status='approved' if is_vip else 'pending',
                         review_note='VIP 免审核自动通过' if is_vip else '',
                         reviewed_at=utcnow() if is_vip else None)
    row.active_key = f'{user.id}:{body.feature}'
    row.approval_source = 'vip' if is_vip else 'manual'
    db.add(row)
    try: db.flush()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, 40901, '该功能已申请或已开通') from None
    audit(db, request, 'request.create', user_id=user.id, detail=body.feature)
    db.commit()
    db.refresh(row)
    return ok(request_dict(row))


@router.post('/requests/{rid}/withdraw')
def withdraw(rid: int, request: Request, user=Depends(get_current_user),
             db=Depends(get_db)):
    row = db.get(FeatureRequest, rid)
    if not row or row.user_id != user.id:
        raise ApiError(404, 40401, '申请不存在')
    if row.status != 'pending':
        raise ApiError(400, 40001, '只有审核中的申请可以撤回')
    claimed = db.execute(update(FeatureRequest).where(FeatureRequest.id == rid,
        FeatureRequest.user_id == user.id, FeatureRequest.status == 'pending').values(status='withdrawn', active_key=None)).rowcount
    if claimed != 1: raise ApiError(400, 40001, '申请状态已变化，请刷新')
    row.status = 'withdrawn'
    row.active_key = None
    row.reviewed_at = utcnow()
    audit(db, request, 'request.withdraw', user_id=user.id, detail=str(rid))
    db.commit()
    return ok(request_dict(row))
