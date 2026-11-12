"""第三方登录骨架：微信 / QQ / 手机号。

一期只开放 email；其余渠道代码完整保留，由 `AUTH_CHANNELS` 开关控制：
渠道未启用时统一返回 403「暂未开放」，前端按 /config/public 下发值灰显入口。
"""

import json
import secrets
import base64
import hashlib
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError

from ..deps import audit, clock, get_db
from ..errors import ApiError, ok
from ..models import LoginLog, User, UserAuth
from ..schemas.account import OAuthTicketInput, PhoneCodeInput, PhoneVerifyInput
from ..services.security import hash_password, issue_session
from ..services.transient import digest
from .public import config_get

router = APIRouter(prefix="/api/v1/auth", tags=["oauth"])

PROVIDERS = {"wechat": "微信", "qq": "QQ", "phone": "手机号", "github": "GitHub"}


def _require_channel(request: Request, provider: str):
    if provider not in PROVIDERS:
        raise ApiError(404, 40401, "未知的登录方式")
    if provider not in request.app.state.settings.enabled_auth_channels:
        raise ApiError(403, 40301, f"{PROVIDERS[provider]}登录暂未开放")


def _callback_url(request: Request, provider: str) -> str:
    origin = request.app.state.settings.public_origin.rstrip("/")
    return f"{origin}/api/v1/auth/oauth/{provider}/callback"


def _oauth_email(provider: str, uid: str) -> str:
    safe = "".join(ch for ch in uid if ch.isalnum())[:32] or secrets.token_hex(8)
    return f"{provider}_{safe}@oauth.local"


def _get_or_create_user(
    db, request, provider, uid, nickname, avatar="", phone=None, accepted_terms=False, verified_email=None
):
    row = db.scalar(
        select(UserAuth).where(
            UserAuth.provider == provider, UserAuth.provider_uid == uid
        )
    )
    if row:
        user = db.get(User, row.user_id)
        if not user or user.status in ("banned", "deleted"):
            raise ApiError(403, 40302, "账号不可用", "请联系管理员")
        return user, False
    # GitHub identities are keyed by immutable provider ID. Only a verified email may link an existing account.
    if provider == "github" and verified_email:
        existing = db.scalar(select(User).where(func.lower(User.email) == verified_email.casefold()))
        if existing:
            if existing.status in ("banned", "deleted"):
                raise ApiError(403, 40302, "账号不可用")
            other = db.scalar(select(UserAuth).where(UserAuth.user_id == existing.id, UserAuth.provider == provider))
            if other:
                raise ApiError(409, 40901, "此邮箱已绑定其他 GitHub 账号")
            db.add(UserAuth(user_id=existing.id,provider=provider,provider_uid=uid,nickname=nickname or "",avatar_url=avatar or ""))
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                raise ApiError(409,40901,"GitHub账号绑定已变化，请重新登录") from None
            return existing, False
    if not config_get(db, "registration_open", False):
        raise ApiError(403, 40301, "注册已关闭，请联系管理员创建账号")

    if not accepted_terms:
        raise ApiError(400, 40001, "新账号请先同意用户协议与隐私政策")
    name = (nickname or "").strip()[:40] or f"{PROVIDERS[provider]}用户"
    if len(name) < 2:
        name = "研友"
    from ..services.admission import check_capacity

    check_capacity(db, request.app.state.settings)
    user = User(
        email=verified_email or _oauth_email(provider, uid),
        phone=phone,
        nickname=name,
        password_hash=hash_password(secrets.token_urlsafe(18)),
        daily_goal_min=300,
        exam_year=config_get(db, "exam_year", 2028),
        exam_date=config_get(db, "exam_date", "2027-12-25"),
    )
    try:
        db.add(user)
        db.flush()
    except IntegrityError:
        raise ApiError(409, 40901, "该第三方账号已绑定其他用户") from None
    db.add(
        UserAuth(
            user_id=user.id,
            provider=provider,
            provider_uid=uid,
            nickname=nickname or "",
            avatar_url=avatar or "",
        )
    )
    return user, True


def _finish_login(db, request, user, provider, response):
    now = clock(request)
    user.last_login_at = now
    db.add(
        LoginLog(
            user_id=user.id,
            email=user.email,
            result="success",
            ip=request.client.host,
            user_agent=request.headers.get("user-agent", ""),
        )
    )
    audit(db, request, f"auth.oauth_{provider}", user_id=user.id)
    db.commit()
    result = issue_session(request, db, user, response, now)
    db.commit()
    return result


# ---------------------------------------------------------------- 授权入口
@router.get("/oauth/{provider}/authorize")
def authorize(
    provider: str, request: Request, response: Response, accepted_terms: bool = False
):
    _require_channel(request, provider)
    settings = request.app.state.settings
    state = secrets.token_urlsafe(32)
    verifier = secrets.token_urlsafe(64)
    request.app.state.transient.set(
        "oauth-state:" + digest(state),
        json.dumps({"provider": provider, "accepted_terms": accepted_terms, "pkce_verifier": verifier}),
        600,
    )
    redirect_uri = _callback_url(request, provider)

    if provider == "github":
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        url = ("https://github.com/login/oauth/authorize"
               f"?client_id={quote(settings.github_client_id,safe='')}&redirect_uri={quote(redirect_uri,safe='')}"
               f"&scope=read%3Auser%20user%3Aemail&state={state}&code_challenge={challenge}&code_challenge_method=S256")
    elif provider == "wechat":
        if not settings.wechat_app_id:
            raise ApiError(503, 50301, "微信登录未配置 AppID")
        url = (
            "https://open.weixin.qq.com/connect/qrconnect"
            f"?appid={settings.wechat_app_id}&redirect_uri={quote(redirect_uri, safe='')}"
            f"&response_type=code&scope=snsapi_login&state={state}#wechat_redirect"
        )
    elif provider == "qq":
        if not settings.qq_app_id:
            raise ApiError(503, 50301, "QQ 登录未配置 AppID")
        url = (
            "https://graph.qq.com/oauth2.0/authorize"
            f"?response_type=code&client_id={settings.qq_app_id}"
            f"&redirect_uri={quote(redirect_uri, safe='')}&state={state}"
        )
    else:
        raise ApiError(400, 40001, "手机号登录请使用短信接口")
    response.set_cookie(
        "yanshi_oauth_state",
        state,
        max_age=600,
        httponly=True,
        secure=settings.environment == "production",
        samesite="lax",
        path="/api/v1/auth/oauth",
    )
    return ok({"url": url, "state": state})


@router.get("/oauth/{provider}/callback")
async def callback(
    request: Request,
    response: Response,
    provider: str,
    code: str = "",
    state: str = "",
    db=Depends(get_db),
):
    _require_channel(request, provider)
    if provider == "phone":
        raise ApiError(400, 40001, "手机号登录请使用短信接口")
    if not code:
        raise ApiError(400, 40001, "缺少授权码")

    store = request.app.state.transient
    if not state or not secrets.compare_digest(
        request.cookies.get("yanshi_oauth_state", ""), state
    ):
        raise ApiError(400, 40001, "授权状态校验失败，请重新发起登录")
    raw_state = store.consume("oauth-state:" + digest(state))
    try:
        expected = json.loads(raw_state or "{}")
    except ValueError:
        expected = {}
    if expected.get("provider") != provider:
        raise ApiError(400, 40001, "授权状态校验失败，请重新发起登录")

    settings = request.app.state.settings
    verified_email = None
    if provider == "github":
        uid, nickname, avatar, verified_email = await _github_profile(settings, code, _callback_url(request,provider), expected.get("pkce_verifier", ""))
    elif provider == "wechat":
        uid, nickname, avatar = await _wechat_profile(settings, code)
    else:
        uid, nickname, avatar = await _qq_profile(
            settings, code, _callback_url(request, provider)
        )

    user, _ = _get_or_create_user(
        db,
        request,
        provider,
        uid,
        nickname,
        avatar,
        accepted_terms=bool(expected.get("accepted_terms")),
        verified_email=verified_email,
    )
    if request.query_params.get("format") == "json":
        return ok(_finish_login(db, request, user, provider, response))
    # 浏览器流程：用一次性 ticket 换 access token，refresh 已写入 httpOnly Cookie
    ticket = secrets.token_urlsafe(24)
    origin = request.app.state.settings.public_origin.rstrip("/")
    redirect = RedirectResponse(f"{origin}/login?oauth_ticket={ticket}")
    redirect.delete_cookie("yanshi_oauth_state", path="/api/v1/auth/oauth")
    result = _finish_login(db, request, user, provider, redirect)
    request.app.state.transient.set(
        "oauth-ticket:" + digest(ticket), json.dumps(result), 120
    )
    return redirect


@router.post("/oauth/exchange")
def exchange_ticket(body: OAuthTicketInput, request: Request):
    if request.app.state.settings.auth_password_only:
        raise ApiError(403, 40301, "内测期间仅支持账号密码登录")
    key = "oauth-ticket:" + digest(body.ticket)
    store = request.app.state.transient
    raw = store.consume(key)
    if not raw:
        raise ApiError(400, 40001, "登录票据无效或已过期")
    try:
        return ok(json.loads(raw))
    except ValueError:
        raise ApiError(400, 40001, "登录票据无效") from None


# ---------------------------------------------------------------- 手机号
@router.post("/phone/send-code")
def phone_send_code(body: PhoneCodeInput, request: Request):
    _require_channel(request, "phone")
    store = request.app.state.transient
    store.limit("phone-minute:" + digest(body.phone), 1, 60)
    store.limit("phone-day:" + digest(body.phone), 10, 86400)
    store.limit("phone-ip:" + request.client.host, 20, 3600)
    code = f"{secrets.randbelow(1000000):06}"
    _send_sms(request.app.state.settings, body.phone, code)
    store.set("phone-code:" + digest(body.phone), digest(code), 300)
    return ok({"sent": True})


@router.post("/phone/verify-code")
def phone_verify_code(
    body: PhoneVerifyInput, request: Request, response: Response, db=Depends(get_db)
):
    _require_channel(request, "phone")
    store = request.app.state.transient
    if not store.verify("phone-code:" + digest(body.phone), digest(body.code), 5):
        raise ApiError(400, 40001, "验证码错误或过期")

    row = db.scalar(
        select(UserAuth).where(
            UserAuth.provider == "phone", UserAuth.provider_uid == body.phone
        )
    )
    if row:
        user = db.get(User, row.user_id)
        if not user or user.status in ("banned", "deleted"):
            raise ApiError(403, 40302, "账号不可用", "请联系管理员")
    else:
        user = db.scalar(
            select(User).where(User.phone == body.phone, User.status != "deleted")
        )
        if user is None:
            user, _ = _get_or_create_user(
                db,
                request,
                "phone",
                body.phone,
                f"研友{body.phone[-4:]}",
                phone=body.phone,
                accepted_terms=body.accepted_terms,
            )
        else:
            db.add(UserAuth(user_id=user.id, provider="phone", provider_uid=body.phone))
    return ok(_finish_login(db, request, user, "phone", response))


# ---------------------------------------------------------------- 提供商适配
async def _wechat_profile(settings, code):
    if not (settings.wechat_app_id and settings.wechat_app_secret):
        raise ApiError(503, 50301, "微信登录未配置 AppID / Secret")
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            token = await client.get(
                "https://api.weixin.qq.com/sns/oauth2/access_token",
                params={
                    "appid": settings.wechat_app_id,
                    "secret": settings.wechat_app_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                },
            )
            data = token.json()
            if data.get("errcode") or not data.get("access_token"):
                raise ApiError(502, 50201, "微信授权失败，请重试")
            info = await client.get(
                "https://api.weixin.qq.com/sns/userinfo",
                params={
                    "access_token": data["access_token"],
                    "openid": data["openid"],
                    "lang": "zh_CN",
                },
            )
            profile = info.json()
            if profile.get("errcode"):
                raise ApiError(502, 50201, "微信用户信息获取失败")
            return (
                data.get("unionid") or data["openid"],
                profile.get("nickname", ""),
                profile.get("headimgurl", ""),
            )
    except httpx.HTTPError:
        raise ApiError(502, 50201, "微信服务连接失败，请稍后重试") from None


async def _qq_profile(settings, code, redirect_uri):
    if not (settings.qq_app_id and settings.qq_app_secret):
        raise ApiError(503, 50301, "QQ 登录未配置 AppID / Secret")
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            token = await client.get(
                "https://graph.qq.com/oauth2.0/token",
                params={
                    "grant_type": "authorization_code",
                    "client_id": settings.qq_app_id,
                    "client_secret": settings.qq_app_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "fmt": "json",
                },
            )
            data = token.json()
            if not data.get("access_token"):
                raise ApiError(502, 50201, "QQ 授权失败，请重试")
            me = await client.get(
                "https://graph.qq.com/oauth2.0/me",
                params={"access_token": data["access_token"], "fmt": "json"},
            )
            openid = (me.json() or {}).get("openid")
            if not openid:
                raise ApiError(502, 50201, "QQ 用户标识获取失败")
            info = await client.get(
                "https://graph.qq.com/user/get_user_info",
                params={
                    "access_token": data["access_token"],
                    "oauth_consumer_key": settings.qq_app_id,
                    "openid": openid,
                },
            )
            profile = info.json()
            if profile.get("ret") not in (0, None):
                raise ApiError(502, 50201, "QQ 用户信息获取失败")
            return (
                openid,
                profile.get("nickname", ""),
                profile.get("figureurl_qq_2", ""),
            )
    except httpx.HTTPError:
        raise ApiError(502, 50201, "QQ 服务连接失败，请稍后重试") from None


def _send_sms(settings, phone, code):
    from ..services.sms import send_sms

    return send_sms(settings, phone, code)


async def _github_profile(settings, code, redirect_uri, verifier):
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post("https://github.com/login/oauth/access_token",
                headers={"Accept":"application/json"}, data={"client_id":settings.github_client_id,
                "client_secret":settings.github_client_secret,"code":code,"redirect_uri":redirect_uri,
                "code_verifier":verifier})
            response.raise_for_status()
            token = response.json().get("access_token")
            if not token: raise ValueError("OAuth token unavailable")
            headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
            response=await client.get("https://api.github.com/user",headers=headers)
            response.raise_for_status(); profile=response.json()
            response=await client.get("https://api.github.com/user/emails",headers=headers)
            response.raise_for_status(); emails=response.json()
            verified=[row for row in emails if row.get("verified") is True and isinstance(row.get("email"),str) and "@" in row["email"]]
            if not verified: raise ApiError(403,40301,"请先在 GitHub 验证邮箱后再登录")
            email=next((row["email"] for row in verified if row.get("primary") is True),verified[0]["email"]).strip().casefold()
            uid=str(int(profile["id"]))
            if int(uid)<=0: raise ValueError("Invalid GitHub user ID")
            return uid,profile.get("name") or profile.get("login") or "GitHub研友",profile.get("avatar_url") or "",email
    except ApiError:
        raise
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        raise ApiError(502,50201,"GitHub 登录暂时不可用，请稍后重试") from None
