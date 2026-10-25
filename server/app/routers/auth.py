import secrets
import re
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from ..deps import audit, clock, decode, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import Config, Invite, LoginLog, RefreshToken, User
from ..schemas.account import (
    ChangePasswordInput, EmailCodeInput, EmailLoginInput, LoginInput, ProfileUpdate,
    RegisterInput, ResetVerifyInput, TokenInput,
)
from ..services.room import join_room_quietly
from ..services.security import (
    REFRESH_COOKIE, clear_refresh_cookie, hash_password, issue_session,
    user_payload, verify_password,
)
from ..services.transient import deliver, digest
from ..services.profile import profile_write
from .public import config_get

router = APIRouter(prefix='/api/v1', tags=['auth'])

CODE_TTL = 300          # 验证码 5 分钟有效
CODE_MAX_ATTEMPTS = 5   # 输错 5 次作废


def ensure_email_domain(request: Request, email: str) -> None:
    """按配置限制邮箱域名（一期为 QQ 邮箱；留空则不限制）。"""
    raw = request.app.state.settings.auth_email_domains
    allowed = {x.strip().lower() for x in raw.split(',') if x.strip()}
    if allowed and email.rsplit('@', 1)[-1].lower() not in allowed:
        raise ApiError(400, 40001, '仅支持 QQ 邮箱登录')
    if allowed == {'qq.com'} and request.app.state.settings.auth_qq_numeric_only \
            and not re.fullmatch(r'[1-9]\d{4,10}@qq\.com', email.lower()):
        raise ApiError(400, 40001, '请使用QQ数字邮箱，暂不支持邮箱别名')


def verify_code(store, key: str, code: str) -> bool:
    return store.verify(key, digest(code), CODE_MAX_ATTEMPTS)



# ----------------------------- 邮箱验证码 -----------------------------

@router.post('/auth/email-code')
def email_code(body: EmailCodeInput, request: Request):
    store = request.app.state.transient
    settings = request.app.state.settings
    db = request.app.state.session_factory()
    try:
        email = body.email
        ensure_email_domain(request, email)
        store.limit('email-minute:' + digest(email), 1, 60)
        store.limit('email-five-minute:' + digest(email), 3, 300)
        store.limit('email-day:' + digest(email), 10, 86400)
        store.limit('email-ip:' + request.client.host, 20, 3600)

        exists = db.scalar(select(User.id).where(User.email == email, User.status != 'deleted'))
        if body.scene == 'register' and exists:
            raise ApiError(409, 40901, '该邮箱已注册，请直接登录')
        if body.scene == 'reset' and not exists:
            # 不暴露邮箱是否注册，统一返回成功但不发码
            return ok({'sent': True})

        value = f'{secrets.randbelow(1000000):06}'
        store.set(f'{body.scene}-code:' + digest(email), digest(value), CODE_TTL)
        title = {'register': '注册验证码', 'reset': '重置密码验证码',
                 'login': '登录验证码'}[body.scene]
        deliver(settings, email, f'研时 · {title}',
                f'你的验证码是 {value}，5 分钟内有效，最多可输错 5 次。如非本人操作请忽略。')
        return ok({'sent': True})
    finally:
        db.close()


# ----------------------------- 注册 -----------------------------

@router.post('/auth/register')
def register(body: RegisterInput, request: Request, response: Response, db=Depends(get_db)):
    if not config_get(db, 'registration_open', False):
        raise ApiError(403, 40301, '注册已关闭，请联系管理员创建账号')
    if not body.accepted_terms:
        raise ApiError(400, 40001, '请先同意用户协议与隐私政策')
    ensure_email_domain(request, body.email)

    store = request.app.state.transient
    store.limit('register-ip:' + request.client.host, 10, 3600)

    if not verify_code(store, 'register-code:' + digest(body.email), body.code):
        raise ApiError(400, 40001, '邮箱验证码错误或过期')
    if db.scalar(select(User.id).where(User.email == body.email, User.status != 'deleted')):
        raise ApiError(409, 40901, '该邮箱已注册')

    now = clock(request)
    invite = None
    if body.invite_code.strip():
        code_hash = digest(body.invite_code.strip().upper())
        invite = db.scalar(select(Invite).where(Invite.code_hash == code_hash))
        if not invite or invite.used_by or invite.revoked_at or (
                invite.expires_at and invite.expires_at < now):
            raise ApiError(400, 40001, '邀请码无效、已使用或已过期')

    from ..services.admission import check_capacity
    check_capacity(db, request.app.state.settings)
    user = User(email=body.email, password_hash=hash_password(body.password),
                nickname=body.nickname, daily_goal_min=300, exam_year=2028,
                exam_date=config_get(db, 'exam_date', '2027-12-25'))
    try:
        db.add(user)
        db.flush()
    except IntegrityError:
        raise ApiError(409, 40901, '该邮箱已注册') from None
    if invite:
        claimed = db.execute(update(Invite).where(Invite.id == invite.id, Invite.used_by.is_(None),
            Invite.revoked_at.is_(None)).values(used_by=user.id, used_at=now)).rowcount
        if claimed != 1: raise ApiError(400, 40001, '邀请码已使用，请刷新后重试')
        if invite.vip_days:
            user.vip_until = now + timedelta(days=invite.vip_days)
    if invite:
        from ..services.group import enroll
        enroll(db, user.id)
    join_room_quietly(db, user)  # 房间满员不阻断注册

    audit(db, request, 'auth.register', user_id=user.id)
    db.add(LoginLog(user_id=user.id, email=body.email, result='success',
                    ip=request.client.host, user_agent=request.headers.get('user-agent', '')))
    db.commit()
    result = issue_session(request, db, user, response, now)
    db.commit()
    return ok(result)


# ----------------------------- 验证码登录 / 自动注册 -----------------------------

@router.post('/auth/email-login')
def email_login(body: EmailLoginInput, request: Request, response: Response,
                db=Depends(get_db)):
    store = request.app.state.transient
    store.limit('email-login-ip:' + request.client.host, 30, 3600)
    store.limit('email-login:' + digest(body.email), 10, 900)
    ensure_email_domain(request, body.email)

    if not verify_code(store, 'login-code:' + digest(body.email), body.code):
        raise ApiError(400, 40001, '验证码错误或过期')

    now = clock(request)
    ua = request.headers.get('user-agent', '')
    user = db.scalar(select(User).where(User.email == body.email, User.status != 'deleted'))
    registered = False
    if user is None:
        if not config_get(db, 'registration_open', False):
            raise ApiError(403, 40301, '注册已关闭，请联系管理员创建账号')
        if not body.accepted_terms:
            raise ApiError(400, 40001, '请先同意用户协议与隐私政策')
        nickname = body.nickname.strip() or body.email.split('@')[0][:20] or '研友'
        if len(nickname) < 2:
            nickname = '研友'
        from ..services.admission import check_capacity
        check_capacity(db, request.app.state.settings)
        user = User(email=body.email, nickname=nickname,
                    password_hash=hash_password(secrets.token_urlsafe(18)),
                    daily_goal_min=300, exam_year=2028,
                    exam_date=config_get(db, 'exam_date', '2027-12-25'))
        try:
            db.add(user)
            db.flush()
        except IntegrityError:
            raise ApiError(409, 40901, '该邮箱已注册') from None
        join_room_quietly(db, user)
        registered = True
    if user.status in ('banned', 'deleted'):
        db.add(LoginLog(user_id=user.id, email=body.email, result='banned',
                        ip=request.client.host, user_agent=ua))
        db.commit()
        raise ApiError(403, 40302, '账号不可用', user.status_reason or '请联系管理员')

    user.last_login_at = now
    db.add(LoginLog(user_id=user.id, email=body.email, result='success',
                    ip=request.client.host, user_agent=ua))
    audit(db, request, 'auth.email_login', user_id=user.id,
          detail='register' if registered else 'login')
    db.commit()
    result = issue_session(request, db, user, response, now)
    db.commit()
    return ok({**result, 'registered': registered})


# ----------------------------- 登录 -----------------------------

@router.post('/auth/login')
def login(body: LoginInput, request: Request, response: Response, db=Depends(get_db)):
    store = request.app.state.transient
    now = clock(request)
    email = body.email
    user = db.scalar(select(User).where(User.email == email, User.status != 'deleted'))
    akey, ipkey = 'login-account:' + digest(email), 'login-ip:' + request.client.host
    ua = request.headers.get('user-agent', '')

    if store.get('locked:' + akey) or store.get('locked:' + ipkey):
        db.add(LoginLog(user_id=user.id if user else None, email=email, result='locked',
                        ip=request.client.host, user_agent=ua))
        db.commit()
        raise ApiError(403, 40302, '尝试次数过多，请 15 分钟后再试')

    if not user or not verify_password(body.password, user.password_hash):
        ac, ic = store.count(akey, 900), store.count(ipkey, 900)
        if ac >= 5:
            store.set('locked:' + akey, '1', 900)
        if ic >= 10:
            store.set('locked:' + ipkey, '1', 900)
        db.add(LoginLog(user_id=user.id if user else None, email=email, result='bad_password',
                        ip=request.client.host, user_agent=ua))
        db.commit()
        raise ApiError(401, 40101, '邮箱或密码错误')

    if user.status in ('banned', 'deleted'):
        db.add(LoginLog(user_id=user.id, email=email, result='banned',
                        ip=request.client.host, user_agent=ua))
        db.commit()
        raise ApiError(403, 40302, '账号不可用', user.status_reason or '请联系管理员')

    store.consume(akey)
    store.consume(ipkey)
    user.last_login_at = now
    db.add(LoginLog(user_id=user.id, email=email, result='success',
                    ip=request.client.host, user_agent=ua))
    audit(db, request, 'login.success', user_id=user.id)
    db.commit()
    result = issue_session(request, db, user, response, now)
    db.commit()
    return ok(result)


# ----------------------------- 刷新 / 登出 -----------------------------

@router.post('/auth/refresh')
def refresh(request: Request, response: Response, body: Optional[TokenInput] = None,
            db=Depends(get_db)):
    token = (body.refresh_token if body and body.refresh_token else '') \
        or request.cookies.get(REFRESH_COOKIE, '')
    if not token:
        raise ApiError(401, 40101, '请重新登录')
    data = decode(request, token, 'refresh')
    now = clock(request)
    user = db.get(User, int(data['sub']))
    if not user or user.token_version != data.get('ver') or user.status in ('banned', 'deleted'):
        raise ApiError(401, 40101, '请重新登录')
    result = db.execute(
        update(RefreshToken)
        .where(RefreshToken.id == digest(data['jti']), RefreshToken.user_id == user.id,
               RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now)
        .values(revoked_at=now))
    if result.rowcount != 1:
        raise ApiError(401, 40101, '此刷新凭证已失效，请重新登录')
    db.commit()
    tokens = issue_session(request, db, user, response, now)
    db.commit()
    return ok(tokens)


@router.post('/auth/logout')
def logout(request: Request, response: Response, body: Optional[TokenInput] = None,
           db=Depends(get_db)):
    token = (body.refresh_token if body and body.refresh_token else '') \
        or request.cookies.get(REFRESH_COOKIE, '')
    try:
        if token:
            data = decode(request, token, 'refresh')
            db.execute(update(RefreshToken).where(RefreshToken.id == digest(data['jti']))
                       .values(revoked_at=clock(request)))
            from ..models import RoomPresence
            db.execute(update(RoomPresence).where(RoomPresence.user_id == int(data['sub'])).values(status='offline', focus_started_at=None))
            db.commit()
    except ApiError:
        pass
    clear_refresh_cookie(response)
    return ok()


# ----------------------------- 当前用户 -----------------------------

@router.get('/auth/me')
def me(user=Depends(get_current_user)):
    return ok(user_payload(user))


@router.put('/users/me')
@profile_write
def update_me(body: ProfileUpdate, request: Request, user=Depends(get_current_user),
              db=Depends(get_db)):
    db.refresh(user, with_for_update=True)
    data = body.model_dump(exclude_none=True)
    if 'privacy_mode' in data and 'is_private_mode' in data and data['privacy_mode'] != data['is_private_mode']:
        raise ApiError(400,40001,'隐私设置字段冲突')
    for key, value in data.items():
        setattr(user, key, value)
    audit(db, request, 'user.update_profile', user_id=user.id)
    from ..services.profile import snapshot_profile
    snapshot_profile(db, user)
    db.commit()
    return ok(user_payload(user))


@router.put('/users/me/password')
def change_password(body: ChangePasswordInput, request: Request, response: Response,
                    user=Depends(get_current_user), db=Depends(get_db)):
    if not verify_password(body.old_password, user.password_hash):
        raise ApiError(400, 40001, '原密码错误')
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked_at=clock(request)))
    audit(db, request, 'auth.change_password', user_id=user.id)
    db.commit()
    tokens = issue_session(request, db, user, response)
    db.commit()
    return ok({'reauthenticate': True, **tokens})


# ----------------------------- 找回密码（邮箱验证码） -----------------------------

@router.post('/auth/reset-password')
def reset_password(body: ResetVerifyInput, request: Request, response: Response,
                   db=Depends(get_db)):
    store = request.app.state.transient
    ensure_email_domain(request, body.email)
    if not verify_code(store, 'reset-code:' + digest(body.email), body.code):
        raise ApiError(400, 40001, '验证码错误或过期')
    user = db.scalar(select(User).where(User.email == body.email, User.status != 'deleted'))
    if not user:
        raise ApiError(400, 40001, '账号不存在')
    user.password_hash = hash_password(body.password)
    user.token_version += 1
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked_at=clock(request)))
    audit(db, request, 'auth.reset_password', user_id=user.id)
    db.commit()
    clear_refresh_cookie(response)
    return ok()
