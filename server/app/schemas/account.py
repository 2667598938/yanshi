import re
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_RE = re.compile(r'^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$')
PHONE_RE = re.compile(r'^1[3-9]\d{9}$')


def phone_value(v: str) -> str:
    if not PHONE_RE.fullmatch(v):
        raise ValueError('手机号格式不正确')
    return v


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


def email_value(v: str) -> str:
    v = v.lower()
    if not EMAIL_RE.fullmatch(v):
        raise ValueError('邮箱格式不正确')
    return v


def password_value(v: str) -> str:
    if len(v.encode()) > 72 or not re.search(r'[a-zA-Z]', v) or not re.search(r'[0-9]', v) or not (8 <= len(v) <= 64):
        raise ValueError('密码需 8-64 位且包含字母和数字')
    return v


class EmailCodeInput(Strict):
    email: str = Field(max_length=254)
    scene: Literal['register', 'reset', 'login'] = 'register'

    _email = field_validator('email')(email_value)


class RegisterInput(Strict):
    email: str = Field(max_length=254)
    code: str = Field(pattern=r'^\d{6}$')
    password: str = Field(min_length=8, max_length=64)
    nickname: str = Field(min_length=2, max_length=40)
    invite_code: str = Field(default='', max_length=32)
    accepted_terms: bool = False

    _email = field_validator('email')(email_value)
    _password = field_validator('password')(password_value)


class EmailLoginInput(Strict):
    email: str = Field(max_length=254)
    code: str = Field(pattern=r'^\d{6}$')
    nickname: str = Field(default='', max_length=40)
    accepted_terms: bool = False

    _email = field_validator('email')(email_value)


class LoginInput(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=72)

    _email = field_validator('email')(email_value)


class TokenInput(Strict):
    refresh_token: str = Field(max_length=4000)


class ProfileUpdate(Strict):
    nickname: Optional[str] = Field(default=None, min_length=2, max_length=40)
    target_school: Optional[str] = Field(default=None, max_length=32)
    signature: Optional[str] = Field(default=None, max_length=80)
    figure_id: Optional[str] = Field(default=None, max_length=24)
    daily_goal_min: Optional[int] = Field(default=None, ge=1, le=1440)
    exam_date: Optional[str] = Field(default=None, max_length=10)
    notify_enabled: Optional[bool] = None


class ErrorTypeInput(Strict):
    name: str = Field(min_length=1, max_length=20)


class PhoneCodeInput(Strict):
    phone: str = Field(max_length=20)

    _phone = field_validator('phone')(phone_value)


class PhoneVerifyInput(Strict):
    phone: str = Field(max_length=20)
    code: str = Field(pattern=r'^\d{6}$')

    _phone = field_validator('phone')(phone_value)


class OAuthTicketInput(Strict):
    ticket: str = Field(min_length=8, max_length=128)


class ChangePasswordInput(Strict):
    old_password: str = Field(max_length=72)
    new_password: str = Field(min_length=8, max_length=64)

    _new = field_validator('new_password')(password_value)


class ResetVerifyInput(Strict):
    email: str = Field(max_length=254)
    code: str = Field(pattern=r'^\d{6}$')
    password: str = Field(min_length=8, max_length=64)

    _email = field_validator('email')(email_value)
    _password = field_validator('password')(password_value)


class AdminCreateMember(Strict):
    email: str = Field(max_length=254)
    nickname: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=8, max_length=64)

    _email = field_validator('email')(email_value)
    _password = field_validator('password')(password_value)


class InviteCreate(Strict):
    remark: str = Field(default='', max_length=200)
    expires_days: Optional[int] = Field(default=None, ge=1, le=365)
    vip_days: Optional[int] = Field(default=None, ge=0, le=3650)


class VipRedeemInput(Strict):
    code: str = Field(min_length=1, max_length=32)


class FeatureRequestInput(Strict):
    feature: Literal['ai', 'materials', 'room', 'other']
    reason: str = Field(min_length=5, max_length=500)


class FeatureRequestReview(Strict):
    action: Literal['approve', 'reject']
    note: str = Field(default='', max_length=300)


class AdminMemberUpdate(Strict):
    nickname: Optional[str] = Field(default=None, min_length=2, max_length=40)
    target_school: Optional[str] = Field(default=None, max_length=32)
    daily_goal_min: Optional[int] = Field(default=None, ge=1, le=1440)
    status: Optional[Literal['active', 'banned']] = None
    vip_action: Optional[Literal['grant', 'renew', 'revoke']] = None
    vip_days: Optional[int] = Field(default=None, ge=1, le=3650)
    note: Optional[str] = Field(default=None, max_length=300)


class AdminResetPassword(Strict):
    new_password: str = Field(min_length=8, max_length=64)

    _new = field_validator('new_password')(password_value)


class AnnouncementInput(Strict):
    content: str = Field(min_length=1, max_length=1000)


class AnnouncementUpdate(Strict):
    content: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    is_active: Optional[bool] = None
