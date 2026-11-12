"""Persistent, per-login revocation across refresh rotation and WebSocket connections."""
import re
import time
from sqlalchemy import update
from ..errors import ApiError
from ..models import TransientState
from . import ai_key

SID=re.compile(r'[a-f0-9]{48}')

def require_active_session(request, db, claims, *, allow_legacy=False):
    sid=claims.get('sid')
    if sid is None and allow_legacy:return  # Existing refresh cookies upgrade without a password prompt.
    if not isinstance(sid,str) or not SID.fullmatch(sid):
        raise ApiError(401,40101,'请刷新登录会话')
    row=db.get(TransientState,'session-revoked:'+sid)
    if row and row.expires_at>time.time():
        raise ApiError(401,40101,'本次登录已退出，请重新登录')

def revoke_session(request, db, claims):
    sid=claims.get('sid')
    if not isinstance(sid,str) or not SID.fullmatch(sid):return
    settings=request.app.state.settings
    key='session-revoked:'+sid
    value=ai_key.encrypt(settings.ai_key_enc_secret or request.app.state.secret,'1',key)
    expires=max(float(claims['exp'])+60,time.time()+settings.refresh_seconds+settings.access_seconds+60)
    changed=db.execute(update(TransientState).where(TransientState.state_key==key).values(value_cipher=value,expires_at=expires)).rowcount
    if not changed:db.add(TransientState(state_key=key,value_cipher=value,expires_at=expires));db.flush()
