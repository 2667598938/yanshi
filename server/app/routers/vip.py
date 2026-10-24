"""运营体系：VIP 状态 / 邀请码核销 / 功能申请。"""
import math
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from ..deps import audit, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import FeatureRequest, Invite
from ..schemas.account import FeatureRequestInput, VipRedeemInput
from ..serializers import iso
from ..services.transient import digest
from ..time import utcnow

router = APIRouter(prefix='/api/v1', tags=['vip'])

FEATURE_LABELS = {
    'ai': 'AI 问答权限',
    'materials': '资料区完整链接',
    'room': '云端自习室',
    'other': '其他功能',
}


def vip_payload(user):
    now = utcnow()
    active = bool(user.vip_until and user.vip_until > now)
    days_left = math.ceil((user.vip_until - now).total_seconds() / 86400) if active else 0
    return {
        'is_vip': active,
        'vip_until': iso(user.vip_until),
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
    code_hash = digest(body.code.strip().upper())
    invite = db.scalar(select(Invite).where(Invite.code_hash == code_hash))
    if not invite or invite.used_by or invite.revoked_at or (
            invite.expires_at and invite.expires_at < now):
        raise ApiError(400, 40001, '邀请码无效、已使用或已过期')
    if not invite.vip_days:
        raise ApiError(400, 40001, '该邀请码不含 VIP 权益')

    invite.used_by = user.id
    invite.used_at = now
    base = user.vip_until if (user.vip_until and user.vip_until > now) else now
    user.vip_until = base + timedelta(days=invite.vip_days)
    audit(db, request, 'vip.redeem', user_id=user.id,
          detail=f'{invite.hint} +{invite.vip_days}d')
    db.commit()
    return ok({**vip_payload(user), 'granted_days': invite.vip_days})


# ---------------------------------------------------------------- 功能申请
@router.get('/requests/mine')
def my_requests(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(select(FeatureRequest).where(
        FeatureRequest.user_id == user.id).order_by(FeatureRequest.id.desc())).all()
    return ok([request_dict(r) for r in rows])


@router.post('/requests')
def create_request(body: FeatureRequestInput, request: Request,
                   user=Depends(get_current_user), db=Depends(get_db)):
    pending = db.scalar(select(FeatureRequest.id).where(
        FeatureRequest.user_id == user.id,
        FeatureRequest.feature == body.feature,
        FeatureRequest.status.in_(('pending', 'approved'))))
    if pending:
        raise ApiError(409, 40901, '该功能已申请或已开通')
    # VIP 免审核：直接通过，留痕便于回溯
    is_vip = bool(user.vip_until and user.vip_until > utcnow())
    row = FeatureRequest(user_id=user.id, feature=body.feature, reason=body.reason,
                         status='approved' if is_vip else 'pending',
                         review_note='VIP 免审核自动通过' if is_vip else '',
                         reviewed_at=utcnow() if is_vip else None)
    db.add(row)
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
    row.status = 'withdrawn'
    row.reviewed_at = utcnow()
    audit(db, request, 'request.withdraw', user_id=user.id, detail=str(rid))
    db.commit()
    return ok(request_dict(row))
