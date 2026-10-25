"""第三方登录骨架：微信 / QQ / 手机号。

一期只开放 email；其余渠道代码完整保留，由 `AUTH_CHANNELS` 开关控制：
渠道未启用时统一返回 403「暂未开放」，前端按 /config/public 下发值灰显入口。
"""
import json
import secrets
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..deps import audit, clock, get_db
from ..errors import ApiError, ok
from ..models import LoginLog, User, UserAuth
from ..schemas.account import OAuthTicketInput, PhoneCodeInput, PhoneVerifyInput
from ..services.room import join_room_quietly
from ..services.security import hash_password, issue_session, user_payload
from ..services.transient import digest
from ..time import utcnow
from .public import config_get

router = APIRouter(prefix='/api/v1/auth', tags=['oauth'])

PROVIDERS = {'wechat': '微信', 'qq': 'QQ', 'phone': '手机号'}


def _require_channel(request: Request, provider: str):
    if provider not in PROVIDERS:
        raise ApiError(404, 40401, '未知的登录方式')
    if provider not in request.app.state.settings.enabled_auth_channels:
        raise ApiError(403, 40301, f'{PROVIDERS[provider]}登录暂未开放')


def _callback_url(request: Request, provider: str) -> str:
    origin = request.app.state.settings.public_origin.rstrip('/')
    return f'{origin}/api/v1/auth/oauth/{provider}/callback'


def _oauth_email(provider: str, uid: str) -> str:
    safe = ''.join(ch for ch in uid if ch.isalnum())[:32] or secrets.token_hex(8)
    return f'{provider}_{safe}@oauth.local'


def _get_or_create_user(db, request, provider, uid, nickname, avatar='', phone=None):
    row = db.scalar(select(UserAuth).where(
        UserAuth.provider == provider, UserAuth.provider_uid == uid))
    if row:
        user = db.get(User, row.user_id)
        if not user or user.status in ('banned', 'deleted'):
            raise ApiError(403, 40302, '账号不可用', '请联系管理员')
        return user, False
    if not config_get(db, 'registration_open', True):
        raise ApiError(403, 40301, '注册已关闭，请联系管理员创建账号')

    name = (nickname or '').strip()[:40] or f'{PROVIDERS[provider]}用户'
    if len(name) < 2:
        name = '研友'
    user = User(email=_oauth_email(provider, uid), phone=phone, nickname=name,
                password_hash=hash_password(secrets.token_urlsafe(18)),
                daily_goal_min=300, exam_year=2028,
                exam_date=config_get(db, 'exam_date', '2027-12-25'))
    try:
        db.add(user)
        db.flush()
    except IntegrityError:
        raise ApiError(409, 40901, '该第三方账号已绑定其他用户') from None
    db.add(UserAuth(user_id=user.id, provider=provider, provider_uid=uid,
                    nickname=nickname or '', avatar_url=avatar or ''))
    join_room_quietly(db, user)
    return user, True


def _finish_login(db, request, user, provider, response):
    now = clock(request)
    user.last_login_at = now
    db.add(LoginLog(user_id=user.id, email=user.email, result='success',
                    ip=request.client.host,
                    user_agent=request.headers.get('user-agent', '')))
    audit(db, request, f'auth.oauth_{provider}', user_id=user.id)
    db.commit()
    result = issue_session(request, db, user, response, now)
    db.commit()
    return result


# ---------------------------------------------------------------- 授权入口
@router.get('/oauth/{provider}/authorize')
def authorize(provider: str, request: Request):
    _require_channel(request, provider)
    settings = request.app.state.settings
    state = secrets.token_urlsafe(16)
    request.app.state.transient.set('oauth-state:' + digest(state), provider, 600)
    redirect_uri = _callback_url(request, provider)

    if provider == 'wechat':
        if not settings.wechat_app_id:
            raise ApiError(503, 50301, '微信登录未配置 AppID')
        url = ('https://open.weixin.qq.com/connect/qrconnect'
               f'?appid={settings.wechat_app_id}&redirect_uri={quote(redirect_uri, safe="")}'
               f'&response_type=code&scope=snsapi_login&state={state}#wechat_redirect')
    elif provider == 'qq':
        if not settings.qq_app_id:
            raise ApiError(503, 50301, 'QQ 登录未配置 AppID')
        url = ('https://graph.qq.com/oauth2.0/authorize'
               f'?response_type=code&client_id={settings.qq_app_id}'
               f'&redirect_uri={quote(redirect_uri, safe="")}&state={state}')
    else:
        raise ApiError(400, 40001, '手机号登录请使用短信接口')
    return ok({'url': url, 'state': state})


@router.get('/oauth/{provider}/callback')
async def callback(request: Request, response: Response, provider: str, code: str = '',
                   state: str = '', db=Depends(get_db)):
    _require_channel(request, provider)
    if provider == 'phone':
        raise ApiError(400, 40001, '手机号登录请使用短信接口')
    if not code:
        raise ApiError(400, 40001, '缺少授权码')

    store = request.app.state.transient
    expected = store.consume('oauth-state:' + digest(state)) if state else None
    if state and expected != provider:
        raise ApiError(400, 40001, '授权状态校验失败，请重新发起登录')

    settings = request.app.state.settings
    if provider == 'wechat':
        uid, nickname, avatar = await _wechat_profile(settings, code)
    else:
        uid, nickname, avatar = await _qq_profile(settings, code, _callback_url(request, provider))

    user, _ = _get_or_create_user(db, request, provider, uid, nickname, avatar)
    if request.query_params.get('format') == 'json':
        return ok(_finish_login(db, request, user, provider, response))
    # 浏览器流程：用一次性 ticket 换 access token，refresh 已写入 httpOnly Cookie
    ticket = secrets.token_urlsafe(24)
    origin = request.app.state.settings.public_origin.rstrip('/')
    redirect = RedirectResponse(f'{origin}/login?oauth_ticket={ticket}')
    result = _finish_login(db, request, user, provider, redirect)
    request.app.state.transient.set('oauth-ticket:' + digest(ticket),
                                    json.dumps(result), 120)
    return redirect


@router.post('/oauth/exchange')
def exchange_ticket(body: OAuthTicketInput, request: Request):
    key = 'oauth-ticket:' + digest(body.ticket)
    store = request.app.state.transient
    raw = store.consume(key)
    if not raw:
        raise ApiError(400, 40001, '登录票据无效或已过期')
    try:
        return ok(json.loads(raw))
    except ValueError:
        raise ApiError(400, 40001, '登录票据无效') from None


# ---------------------------------------------------------------- 手机号
@router.post('/phone/send-code')
def phone_send_code(body: PhoneCodeInput, request: Request):
    _require_channel(request, 'phone')
    store = request.app.state.transient
    store.limit('phone-minute:' + digest(body.phone), 1, 60)
    store.limit('phone-day:' + digest(body.phone), 10, 86400)
    code = f'{secrets.randbelow(1000000):06}'
    store.set('phone-code:' + digest(body.phone), digest(code), 300)
    _send_sms(request.app.state.settings, body.phone, code)
    return ok({'sent': True})


@router.post('/phone/verify-code')
def phone_verify_code(body: PhoneVerifyInput, request: Request, response: Response,
                      db=Depends(get_db)):
    _require_channel(request, 'phone')
    store = request.app.state.transient
    if not store.verify('phone-code:' + digest(body.phone), digest(body.code), 5):
        raise ApiError(400, 40001, '验证码错误或过期')

    row = db.scalar(select(UserAuth).where(
        UserAuth.provider == 'phone', UserAuth.provider_uid == body.phone))
    if row:
        user = db.get(User, row.user_id)
        if not user or user.status in ('banned', 'deleted'):
            raise ApiError(403, 40302, '账号不可用', '请联系管理员')
    else:
        user = db.scalar(select(User).where(
            User.phone == body.phone, User.status != 'deleted'))
        if user is None:
            user, _ = _get_or_create_user(
                db, request, 'phone', body.phone,
                f'研友{body.phone[-4:]}', phone=body.phone)
        else:
            db.add(UserAuth(user_id=user.id, provider='phone', provider_uid=body.phone))
    return ok(_finish_login(db, request, user, 'phone', response))


# ---------------------------------------------------------------- 提供商适配
async def _wechat_profile(settings, code):
    if not (settings.wechat_app_id and settings.wechat_app_secret):
        raise ApiError(503, 50301, '微信登录未配置 AppID / Secret')
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            token = await client.get(
                'https://api.weixin.qq.com/sns/oauth2/access_token',
                params={'appid': settings.wechat_app_id,
                        'secret': settings.wechat_app_secret,
                        'code': code, 'grant_type': 'authorization_code'})
            data = token.json()
            if data.get('errcode') or not data.get('access_token'):
                raise ApiError(502, 50201, '微信授权失败，请重试')
            info = await client.get('https://api.weixin.qq.com/sns/userinfo',
                                    params={'access_token': data['access_token'],
                                            'openid': data['openid'], 'lang': 'zh_CN'})
            profile = info.json()
            if profile.get('errcode'):
                raise ApiError(502, 50201, '微信用户信息获取失败')
            return (data.get('unionid') or data['openid'],
                    profile.get('nickname', ''), profile.get('headimgurl', ''))
    except httpx.HTTPError:
        raise ApiError(502, 50201, '微信服务连接失败，请稍后重试') from None


async def _qq_profile(settings, code, redirect_uri):
    if not (settings.qq_app_id and settings.qq_app_secret):
        raise ApiError(503, 50301, 'QQ 登录未配置 AppID / Secret')
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            token = await client.get(
                'https://graph.qq.com/oauth2.0/token',
                params={'grant_type': 'authorization_code',
                        'client_id': settings.qq_app_id,
                        'client_secret': settings.qq_app_secret,
                        'code': code, 'redirect_uri': redirect_uri, 'fmt': 'json'})
            data = token.json()
            if not data.get('access_token'):
                raise ApiError(502, 50201, 'QQ 授权失败，请重试')
            me = await client.get('https://graph.qq.com/oauth2.0/me',
                                  params={'access_token': data['access_token'], 'fmt': 'json'})
            openid = (me.json() or {}).get('openid')
            if not openid:
                raise ApiError(502, 50201, 'QQ 用户标识获取失败')
            info = await client.get(
                'https://graph.qq.com/user/get_user_info',
                params={'access_token': data['access_token'],
                        'oauth_consumer_key': settings.qq_app_id, 'openid': openid})
            profile = info.json()
            if profile.get('ret') not in (0, None):
                raise ApiError(502, 50201, 'QQ 用户信息获取失败')
            return openid, profile.get('nickname', ''), profile.get('figureurl_qq_2', '')
    except httpx.HTTPError:
        raise ApiError(502, 50201, 'QQ 服务连接失败，请稍后重试') from None


def _send_sms(settings, phone, code):
    """短信通道骨架：未接入服务商时打印到后端控制台（仅开发）。"""
    text = f'【研时】登录验证码 {code}，5 分钟内有效。'
    if not settings.sms_provider:
        print(f'[SMS] {phone}: {text}')
        return
    raise ApiError(503, 50301, f'短信服务商 {settings.sms_provider} 尚未接入')
