import secrets as _secrets
from datetime import timedelta

import bcrypt
import jwt

from ..models import RefreshToken
from ..serializers import iso
from ..time import utcnow
from .transient import digest

INVITE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # 去掉易混字符 0/O/1/I


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except ValueError:
        return False


def new_invite_code(n: int = 8) -> str:
    return ''.join(_secrets.choice(INVITE_ALPHABET) for _ in range(n))


def issue_tokens(request, db, user, now=None):
    """签发 access + refresh（同属一个 family，refresh 落库以便旋转/吊销）。"""
    now = now or utcnow()
    settings = request.app.state.settings
    result = {}
    family = _secrets.token_hex(24)
    for kind, duration in (('access', settings.access_seconds), ('refresh', settings.refresh_seconds)):
        token_id = family if kind == 'refresh' else _secrets.token_hex(24)
        payload = {
            'sub': str(user.id), 'ver': user.token_version, 'kind': kind, 'jti': token_id,
            'iat': now, 'exp': now + timedelta(seconds=duration),
            'iss': settings.jwt_issuer, 'aud': settings.jwt_audience, 'fid': digest(family),
        }
        result[kind + '_token'] = jwt.encode(payload, request.app.state.secret, algorithm='HS256')
        if kind == 'refresh':
            db.add(RefreshToken(id=digest(token_id), user_id=user.id,
                                expires_at=now + timedelta(seconds=duration)))
    return result


def user_payload(user):
    return {
        'id': user.id, 'email': user.email, 'nickname': user.nickname,
        'avatar_key': user.avatar_key, 'role': user.role, 'status': user.status,
        'target_school': user.target_school, 'exam_year': user.exam_year,
        'daily_goal_min': user.daily_goal_min, 'exam_date': user.exam_date,
        'notify_enabled': user.notify_enabled,
        'vip_until': iso(user.vip_until),
        'is_vip': bool(user.vip_until and user.vip_until > utcnow()),
    }
