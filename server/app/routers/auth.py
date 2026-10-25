import json
import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
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
from ..services.security import hash_password, issue_tokens, user_payload, verify_password
from ..services.transient import deliver, digest
from .public import config_get

router = APIRouter(prefix='/api/v1', tags=['auth'])


# ----------------------------- 邮箱验证码 -----------------------------

@router.post('/auth/email-code')
def email_code(body: EmailCodeInput, request: Request):
    store = request.app.state.transient
    settings = request.app.state.settings
    db = request.app.state.session_factory()
    try:
        email = body.email
        store.limit('email-minute:' + digest(email), 1, 60)
        store.limit('email-day:' + digest(email), 10, 86400)
        store.limit('email-ip:' + request.client.host, 20, 3600)

        exists = db.scalar(select(User.id).where(User.email == email, User.status != 'deleted'))
        if body.scene == 'register' and exists:
            raise ApiError(409, 40901, '该邮箱已注册，请直接登录')
        if body.scene == 'reset' and not exists:
            # 不暴露邮箱是否注册，统一返回成功但不发码
            return ok({'sent': True})

        value = f'{secrets.randbelow(1000000):06}'
        store.set(f'{body.scene}-code:' + digest(email), digest(value), 600)
        title = {'register': '注册验证码', 'reset': '重置密码验证码',
                 'login': '登录验证码'}[body.scene]
        deliver(settings, email, f'研时 · {title}',
                f'你的验证码是 {value}，10 分钟内有效。如非本人操作请忽略。')
        return ok({'sent': True})
    finally:
        db.close()


# ----------------------------- 注册 -----------------------------

@router.post('/auth/register')
def register(body: RegisterInput, request: Request, db=Depends(get_db)):
    if not config_get(db, 'registration_open', False):
        raise ApiError(403, 40301, '注册已关闭，请联系管理员创建账号')
    if not body.accepted_terms:
        raise ApiError(400, 40001, '请先同意用户协议与隐私政策')

    store = request.app.state.transient
    store.limit('register-ip:' + request.client.host, 10, 3600)

    expected = store.consume('register-code:' + digest(body.email))
    if not expected or not secrets.compare_digest(expected, digest(body.code)):
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

    user = User(email=body.email, password_hash=hash_password(body.password),
                nickname=body.nickname, daily_goal_min=300, exam_year=2028,
                exam_date=config_get(db, 'exam_date', '2027-12-25'))
    try:
        db.add(user)
        db.flush()
    except IntegrityError:
        raise ApiError(409, 40901, '该邮箱已注册') from None
    if invite:
        invite.used_by = user.id
        invite.used_at = now
        if invite.vip_days:
            user.vip_until = now + timedelta(days=invite.vip_days)
    join_room_quietly(db, user)  # 房间满员不阻断注册

    audit(db, request, 'auth.register', user_id=user.id)
    db.add(LoginLog(user_id=user.id, email=body.email, result='success',
                    ip=request.client.host, user_agent=request.headers.get('user-agent', '')))
    db.commit()
    result = issue_tokens(request, db, user, now)
    db.commit()
    return ok({**result, 'user': user_payload(user)})


# ----------------------------- 验证码登录 / 自动注册 -----------------------------

@router.post('/auth/email-login')
def email_login(body: EmailLoginInput, request: Request, db=Depends(get_db)):
    store = request.app.state.transient
    store.limit('email-login-ip:' + request.client.host, 30, 3600)
    store.limit('email-login:' + digest(body.email), 10, 900)

    expected = store.consume('login-code:' + digest(body.email))
    if not expected or not secrets.compare_digest(expected, digest(body.code)):
        raise ApiError(400, 40001, '验证码错误或过期')

    now = clock(request)
    ua = request.headers.get('user-agent', '')
    user = db.scalar(select(User).where(User.email == body.email, User.status != 'deleted'))
    registered = False
    if user is None:
        if not config_get(db, 'registration_open', True):
            raise ApiError(403, 40301, '注册已关闭，请联系管理员创建账号')
        if not body.accepted_terms:
            raise ApiError(400, 40001, '请先同意用户协议与隐私政策')
        nickname = body.nickname.strip() or body.email.split('@')[0][:20] or '研友'
        if len(nickname) < 2:
            nickname = '研友'
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
    result = issue_tokens(request, db, user, now)
    db.commit()
    return ok({**result, 'user': user_payload(user), 'registered': registered})


# ----------------------------- 登录 -----------------------------

@router.post('/auth/login')
def login(body: LoginInput, request: Request, db=Depends(get_db)):
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
    result = issue_tokens(request, db, user, now)
    db.commit()
    return ok({**result, 'user': user_payload(user)})


# ----------------------------- 刷新 / 登出 -----------------------------

@router.post('/auth/refresh')
def refresh(body: TokenInput, request: Request, db=Depends(get_db)):
    data = decode(request, body.refresh_token, 'refresh')
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
    tokens = issue_tokens(request, db, user, now)
    db.commit()
    return ok(tokens)


@router.post('/auth/logout')
def logout(body: TokenInput, request: Request, db=Depends(get_db)):
    try:
        data = decode(request, body.refresh_token, 'refresh')
        db.execute(update(RefreshToken).where(RefreshToken.id == digest(data['jti']))
                   .values(revoked_at=clock(request)))
        db.commit()
    except ApiError:
        pass
    return ok()


# ----------------------------- 当前用户 -----------------------------

@router.get('/auth/me')
def me(user=Depends(get_current_user)):
    return ok(user_payload(user))


@router.put('/users/me')
def update_me(body: ProfileUpdate, request: Request, user=Depends(get_current_user),
              db=Depends(get_db)):
    data = body.model_dump(exclude_none=True)
    for key, value in data.items():
        setattr(user, key, value)
    audit(db, request, 'user.update_profile', user_id=user.id)
    db.commit()
    return ok(user_payload(user))


@router.put('/users/me/password')
def change_password(body: ChangePasswordInput, request: Request,
                    user=Depends(get_current_user), db=Depends(get_db)):
    if not verify_password(body.old_password, user.password_hash):
        raise ApiError(400, 40001, '原密码错误')
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked_at=clock(request)))
    audit(db, request, 'auth.change_password', user_id=user.id)
    db.commit()
    tokens = issue_tokens(request, db, user)
    db.commit()
    return ok({'reauthenticate': True, **tokens})


# ----------------------------- 找回密码（邮箱验证码） -----------------------------

@router.post('/auth/reset-password')
def reset_password(body: ResetVerifyInput, request: Request, db=Depends(get_db)):
    store = request.app.state.transient
    expected = store.consume('reset-code:' + digest(body.email))
    if not expected or not secrets.compare_digest(expected, digest(body.code)):
        raise ApiError(400, 40001, '验证码错误或过期')
    user = db.scalar(select(User).where(User.email == body.email, User.status != 'deleted'))
    if not user:
        raise ApiError(400, 40001, '账号不存在')
    user.password_hash = hash_password(body.password)
    user.token_version += 1
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked_at=clock(request)))
    audit(db, request, 'auth.reset_password', user_id=user.id)
    db.commit()
    return ok()
