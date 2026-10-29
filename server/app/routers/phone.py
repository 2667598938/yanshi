"""登录账号绑定手机号；登录渠道关闭时仍由同一后端开关阻止调用。"""
import secrets
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from ..deps import get_current_user, get_db, audit
from ..errors import ApiError, ok
from ..models import User, UserAuth
from ..schemas.account import PhoneCodeInput, PhoneVerifyInput
from ..services.sms import send_sms
from ..services.transient import digest
from ..services.security import user_payload

router = APIRouter(prefix='/api/v1/users/me/phone', tags=['phone'])


def require_phone(request):
    if 'phone' not in request.app.state.settings.enabled_auth_channels:
        raise ApiError(403, 40310, '手机号绑定暂未开放')


@router.post('/send-code')
def send_code(body: PhoneCodeInput, request: Request, user=Depends(get_current_user)):
    require_phone(request)
    store = request.app.state.transient
    store.limit(f'bind-phone-user:{user.id}', 1, 60)
    store.limit('phone-day:' + digest(body.phone), 10, 86400)
    store.limit('phone-ip:' + request.client.host, 20, 3600)
    code = f'{secrets.randbelow(1000000):06}'
    send_sms(request.app.state.settings, body.phone, code)
    store.set(f'bind-phone:{user.id}:' + digest(body.phone), digest(code), 300)
    return ok({'sent': True})


@router.put('')
def bind_phone(body: PhoneVerifyInput, request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    require_phone(request)
    if not request.app.state.transient.verify(f'bind-phone:{user.id}:' + digest(body.phone), digest(body.code), 5):
        raise ApiError(400, 40001, '验证码错误或过期')
    db.refresh(user, with_for_update=True)
    existing = db.scalar(select(UserAuth).where(UserAuth.provider == 'phone', UserAuth.provider_uid == body.phone))
    if existing and existing.user_id != user.id:
        raise ApiError(409, 40901, '该手机号已被其他账号绑定')
    other = db.scalar(select(User.id).where(User.phone == body.phone, User.id != user.id))
    if other: raise ApiError(409, 40901, '该手机号已被其他账号绑定')
    db.execute(delete(UserAuth).where(UserAuth.user_id == user.id, UserAuth.provider == 'phone'))
    db.flush()
    user.phone = body.phone
    db.add(UserAuth(user_id=user.id, provider='phone', provider_uid=body.phone))
    audit(db, request, 'user.bind_phone', user_id=user.id, detail='手机号绑定或更换')
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, 40901, '手机号已被绑定，请重新获取验证码') from None
    return ok(user_payload(user))
