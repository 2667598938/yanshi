import re
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

EMAIL_RE = re.compile(r'^[^\s@<>]+@[^\s@<>]+\.[a-z]{2,}$')


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
    scene: Literal['register', 'reset'] = 'register'

    _email = field_validator('email')(email_value)


class RegisterInput(Strict):
    email: str = Field(max_length=254)
    code: str = Field(pattern=r'^\d{6}$')
    password: str = Field(min_length=8, max_length=64)
    nickname: str = Field(min_length=2, max_length=40)
    invite_code: str = Field(min_length=1, max_length=32)
    accepted_terms: bool = False

    _email = field_validator('email')(email_value)
    _password = field_validator('password')(password_value)


class LoginInput(Strict):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=72)

    _email = field_validator('email')(email_value)


class TokenInput(Strict):
    refresh_token: str = Field(max_length=4000)


class ProfileUpdate(Strict):
    nickname: Optional[str] = Field(default=None, min_length=2, max_length=40)
    target_school: Optional[str] = Field(default=None, max_length=32)
    daily_goal_min: Optional[int] = Field(default=None, ge=1, le=1440)
    exam_date: Optional[str] = Field(default=None, max_length=10)
    notify_enabled: Optional[bool] = None


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


class AdminMemberUpdate(Strict):
    nickname: Optional[str] = Field(default=None, min_length=2, max_length=40)
    target_school: Optional[str] = Field(default=None, max_length=32)
    daily_goal_min: Optional[int] = Field(default=None, ge=1, le=1440)
    status: Optional[Literal['active', 'banned']] = None


class AdminResetPassword(Strict):
    new_password: str = Field(min_length=8, max_length=64)

    _new = field_validator('new_password')(password_value)


class AnnouncementInput(Strict):
    content: str = Field(min_length=1, max_length=1000)


class AnnouncementUpdate(Strict):
    content: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    is_active: Optional[bool] = None
