import jwt
from fastapi import Depends, Request
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError

from .errors import ApiError
from .models import Audit, User
from .time import utcnow


def get_db(request: Request):
    db = request.app.state.session_factory()
    db.info['settings'] = request.app.state.settings
    try:
        yield db
    finally:
        db.close()


def clock(_request: Request):
    return utcnow()


def decode(request: Request, token: str, kind: str):
    settings = request.app.state.settings
    try:
        data = jwt.decode(
            token, request.app.state.secret,
            audience=settings.jwt_audience, issuer=settings.jwt_issuer, algorithms=['HS256'])
    except ExpiredSignatureError:
        raise ApiError(401, 40102, '登录已过期')
    except InvalidTokenError:
        raise ApiError(401, 40101, '请先登录')
    for key in ('exp', 'iat', 'sub', 'jti', 'kind', 'ver'):
        if key not in data:
            raise ApiError(401, 40101, '请先登录')
    if data.get('kind') != kind:
        raise ApiError(401, 40101, '请先登录')
    return data


def get_current_user(request: Request, db=Depends(get_db)):
    header = request.headers.get('authorization', '')
    if not header.startswith('Bearer '):
        raise ApiError(401, 40101, '请先登录')
    data = decode(request, header[7:], 'access')
    user = db.get(User, int(data['sub']))
    if not user or user.token_version != data.get('ver') or user.status in ('banned', 'deleted'):
        raise ApiError(401, 40101, '请重新登录')
    request.state.actor_id=user.id
    return user


def get_admin(user=Depends(get_current_user)):
    if user.role != 'admin':
        raise ApiError(403, 40301, '需要管理员权限')
    return user


def require_enabled_feature(feature):
    def check(request: Request):
        if feature not in request.app.state.settings.enabled_features:
            raise ApiError(403, 40310, '该功能暂未开放')
    return check


def audit(db, request: Request, action: str, user_id=None, detail=''):
    db.add(Audit(
        actor_id=getattr(request.state,'actor_id',None),
        user_id=user_id,
        action=action,
        ip=request.client.host if request.client else '',
        user_agent=request.headers.get('user-agent', '')[:300],
        detail=detail,
    ))
