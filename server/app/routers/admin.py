"""后台管理接口（仅管理员）：概览、成员、邀请码、配置、公告、审计、数据导出。"""

from sqlalchemy.exc import IntegrityError
import json
from datetime import timedelta, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import and_, func, or_, select, update as sa_update

from ..deps import audit, get_admin, get_db
from ..errors import ApiError, ok
from ..models import (
    AIConversation,
    Announcement,
    Attachment,
    Audit,
    Config,
    FeatureRequest,
    Invite,
    LearningOperation,
    LearningRecord,
    Room,
    RoomMember,
    RoomMessage,
    RoomPresence,
    User,
    EmailJob,
)
from ..schemas.account import (
    AdminCreateMember,
    AdminMemberUpdate,
    AdminResetPassword,
    AnnouncementInput,
    AnnouncementUpdate,
    FeatureRequestReview,
    InviteCreate,
)
from ..serializers import iso
from ..services import features as feature_service
from ..services import room as room_service
from ..services.group import shared_user_ids
from ..services.presence import WINDOW
from ..services.messages import create_message
from ..services.security import hash_password, new_invite_code
from ..services.transient import digest
from ..services.profile import profile_write
from ..time import utcnow
from .vip import FEATURE_LABELS

router = APIRouter(
    prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(get_admin)]
)


@router.get("/diagnostics")
def diagnostics(request: Request):
    from ..services.readiness import database_ready

    settings = request.app.state.settings
    return ok(
        {
            "environment": settings.environment,
            "database_ready": database_ready(request.app.state.engine),
            "database_kind": "sqlite" if settings.is_sqlite else "sql",
            "features": settings.enabled_features,
            "auth_channels": settings.enabled_auth_channels,
            "account_max_users": settings.account_max_users,
            "ai_daily_limit": settings.ai_daily_limit,
            "image_storage": settings.image_storage,
            "qiniu_configured": bool(
                settings.qiniu_access_key
                and settings.qiniu_secret_key
                and settings.qiniu_bucket
            ),
            "smtp_configured": bool(
                settings.smtp_host and settings.smtp_user and settings.smtp_password
            ),
            "sms_provider": settings.sms_provider,
            "sms_configured": bool(
                settings.sms_provider == "tencent"
                and settings.sms_secret_id
                and settings.sms_secret_key
                and settings.sms_sdk_app_id
                and settings.sms_template_id
                and settings.sms_sign_name
            ),
            "wechat_configured": bool(
                settings.wechat_app_id and settings.wechat_app_secret
            ),
            "qq_configured": bool(settings.qq_app_id and settings.qq_app_secret),
            "github_configured": bool(settings.github_client_id and settings.github_client_secret),
            "server_ai_configured": False,
            "ai_key_policy": "byok_required",
        }
    )


def config_get(db, key, default=None):
    row = db.get(Config, key)
    if row is None:
        return default
    try:
        return json.loads(row.config_value)
    except (ValueError, TypeError):
        return row.config_value


def invite_dict(row):
    return {
        "id": row.id,
        "code": row.hint,
        "kind": row.kind,
        "remark": row.remark,
        "created_by": row.created_by,
        "used_by": row.used_by,
        "vip_days": row.vip_days or 0,
        "used_at": iso(row.used_at),
        "expires_at": iso(row.expires_at),
        "created_at": iso(row.created_at),
        "is_used": bool(row.used_at),
    }


def member_dict(row):
    return {
        "id": row.id,
        "email": row.email,
        "nickname": row.nickname,
        "role": row.role,
        "status": row.status,
        "avatar_key": row.avatar_key or "",
        "vip_until": iso(row.vip_until),
        "vip_permanent": bool(row.vip_permanent),
        "is_vip": feature_service.is_vip(row),
        "created_at": iso(row.created_at),
        "last_login_at": iso(row.last_login_at),
    }


def admin_request_dict(row, user):
    return {
        "id": row.id,
        "feature": row.feature,
        "feature_label": FEATURE_LABELS.get(row.feature, row.feature),
        "reason": row.reason,
        "status": row.status,
        "review_note": row.review_note or "",
        "reviewed_at": iso(row.reviewed_at),
        "created_at": iso(row.created_at),
        "user": {"id": user.id, "nickname": user.nickname, "email": user.email},
    }


# ---------------------------------------------------------------- 概览大盘
@router.get("/overview")
def overview(request: Request, db=Depends(get_db), admin=Depends(get_admin)):
    users = db.scalars(select(User).where(User.status != "deleted")).all()
    # Memberships are occupied seats, so one person in two rooms counts twice.
    room_member_count = (
        db.scalar(
            select(func.count())
            .select_from(RoomMember)
            .join(Room, Room.id == RoomMember.room_id)
            .where(
                Room.dissolved_at.is_(None),
                or_(
                    RoomMember.sharing_confirmed.is_(True),
                    Room.owner_id == RoomMember.user_id,
                ),
            )
        )
        or 0
    )
    # Online accounts are distinct, restricted to current memberships and visible data.
    online_count = (
        db.scalar(
            select(func.count(func.distinct(RoomPresence.user_id)))
            .select_from(RoomPresence)
            .join(Room, Room.id == RoomPresence.room_id)
            .join(
                RoomMember,
                and_(
                    RoomMember.room_id == RoomPresence.room_id,
                    RoomMember.user_id == RoomPresence.user_id,
                ),
            )
            .join(User, User.id == RoomPresence.user_id)
            .where(
                Room.dissolved_at.is_(None),
                User.status == "active",
                RoomPresence.status != "offline",
                RoomPresence.last_heartbeat_at >= utcnow() - timedelta(seconds=WINDOW),
                or_(
                    User.id == admin.id,
                    and_(
                        User.is_private_mode.is_(False),
                        User.id.in_(shared_user_ids(admin.id)),
                    ),
                ),
            )
        )
        or 0
    )

    today_str, _ = room_service._cn_bounds()
    record_count = db.scalar(select(func.count()).select_from(LearningRecord))
    operation_count = db.scalar(select(func.count()).select_from(LearningOperation))
    conversation_count = db.scalar(select(func.count()).select_from(AIConversation))
    message_count = db.scalar(
        select(func.count())
        .select_from(RoomMessage)
        .where(RoomMessage.deleted_at.is_(None))
    )
    attachment_bytes = db.scalar(
        select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
            Attachment.deleted_at.is_(None)
        )
    )

    return ok(
        {
            "member_count": len(users),
            "vip_count": sum(1 for u in users if feature_service.is_vip(u)),
            "room_member_count": room_member_count,
            "online_count": online_count,
            "today": today_str,
            "record_count": record_count,
            "operation_count": operation_count,
            "conversation_count": conversation_count,
            "message_count": message_count,
            "attachment_bytes": attachment_bytes or 0,
            "registration_open": not request.app.state.settings.auth_password_only
            and config_get(db, "registration_open", False),
            "site_name": config_get(db, "site_name", "研时"),
            "exam_date": config_get(db, "exam_date", "2027-12-25"),
            "exam_year": config_get(db, "exam_year", 2028),
        }
    )


# ---------------------------------------------------------------- 成员管理
@router.get("/members")
def list_members(db=Depends(get_db)):
    rows = db.scalars(
        select(User).where(User.status != "deleted").order_by(User.id)
    ).all()
    return ok([member_dict(u) for u in rows])


@router.post("/members")
def create_member(body: AdminCreateMember, request: Request, db=Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise ApiError(409, 40901, "该邮箱已被使用")
    from ..services.admission import check_capacity

    check_capacity(db, request.app.state.settings)
    user = User(
        email=body.email,
        nickname=body.nickname,
        password_hash=hash_password(body.password),
        role="member",
        exam_year=config_get(db, "exam_year", 2028),
        exam_date=config_get(db, "exam_date", "2027-12-25"),
    )
    db.add(user)
    db.flush()
    audit(db, request, "admin.create_member", user_id=user.id, detail=body.email)
    db.commit()
    db.refresh(user)
    return ok(member_dict(user))


def _get_member(db, uid):
    user = db.get(User, uid)
    if not user or user.status == "deleted":
        raise ApiError(404, 40401, "成员不存在")
    return user


@router.put("/members/{uid}")
@profile_write
def update_member(
    uid: int, body: AdminMemberUpdate, request: Request, db=Depends(get_db)
):
    user = _get_member(db, uid)
    db.refresh(user, with_for_update=True)
    if body.target_school is not None or body.daily_goal_min is not None:
        raise ApiError(403, 40301, "管理员不能修改成员学习偏好")
    before = {
        "status": user.status,
        "nickname": user.nickname,
        "vip_until": iso(user.vip_until),
        "vip_permanent": bool(user.vip_permanent),
    }
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.target_school is not None:
        user.target_school = body.target_school
    if body.daily_goal_min is not None:
        user.daily_goal_min = body.daily_goal_min
    if body.status is not None:
        if user.role == "admin":
            raise ApiError(400, 40001, "不能封禁管理员")
        if user.status != body.status:
            user.status = body.status
            if body.status == "banned":
                user.token_version += 1  # 强制下线
    if body.vip_action:
        note = (body.note or "").strip()
        if len(note) < 5:
            raise ApiError(400, 40001, "请填写至少 5 个字的操作备注")
        now = utcnow()
        days = body.vip_days or 30
        if body.vip_action == "grant":
            user.vip_permanent = False
            user.vip_until = now + timedelta(days=days)
        elif body.vip_action == "renew":
            if user.vip_permanent:
                raise ApiError(400, 40001, "永久VIP无需续期")
            base = user.vip_until if (user.vip_until and user.vip_until > now) else now
            user.vip_until = base + timedelta(days=days)
        elif body.vip_action == "permanent":
            user.vip_permanent, user.vip_until = True, None
        elif body.vip_action == "set_expiry":
            if body.vip_until is None:
                raise ApiError(400, 40001, "请指定到期时间")
            until = body.vip_until
            if until.tzinfo:
                until = until.astimezone(timezone.utc).replace(tzinfo=None)
            if until <= now:
                raise ApiError(400, 40001, "到期时间必须晚于当前时间")
            user.vip_permanent, user.vip_until = False, until
        else:
            user.vip_permanent = False
            user.vip_until = None
        user.vip_expiry_notified_until = None
        if body.vip_action != "revoke":
            until = user.vip_until.date().isoformat() if user.vip_until else "永久"
            title = "VIP 已开通" if body.vip_action == "grant" else "VIP 已续期"
            content = f"管理员已为你{'开通' if body.vip_action == 'grant' else '续期'} VIP，有效期至 {until}。"
        else:
            title = "VIP 已降级"
            content = (
                "管理员已将你的 VIP 降级，相关权益已停止；已保存的 AI Key 会保留。"
            )
        create_message(
            db,
            user,
            "vip",
            title,
            content,
            link="/vip",
            email=body.vip_action != "revoke",
            settings=request.app.state.settings,
        )
    audit(
        db,
        request,
        "admin.update_member",
        user_id=uid,
        detail=json.dumps(
            {
                "before": before,
                "after": {
                    "status": user.status,
                    "nickname": user.nickname,
                    "vip_until": iso(user.vip_until),
                    "vip_permanent": bool(user.vip_permanent),
                },
                "changes": body.model_dump(mode="json", exclude_none=True),
            },
            ensure_ascii=False,
        ),
    )
    if any(
        getattr(body, field) is not None
        for field in ("nickname", "target_school", "daily_goal_min")
    ):
        from ..services.profile import snapshot_profile

        snapshot_profile(db, user)
    db.commit()
    db.refresh(user)
    return ok(member_dict(user))


@router.post("/members/{uid}/reset-password")
def reset_member_password(
    uid: int, body: AdminResetPassword, request: Request, db=Depends(get_db)
):
    user = _get_member(db, uid)
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1  # 旧 token 全部失效
    audit(db, request, "admin.reset_password", user_id=uid)
    db.commit()
    return ok()


@router.delete("/members/{uid}")
def delete_member(uid: int, request: Request, db=Depends(get_db)):
    _get_member(db, uid)
    raise ApiError(403, 40301, "账号只能封禁，必须保留原有学习数据")


# ---------------------------------------------------------------- 邀请码
@router.get("/invites")
def list_invites(db=Depends(get_db)):
    rows = db.scalars(select(Invite).order_by(Invite.id.desc())).all()
    return ok([invite_dict(r) for r in rows])


@router.post("/invites")
def create_invite(
    body: InviteCreate, request: Request, db=Depends(get_db), admin=Depends(get_admin)
):
    code = new_invite_code()
    expires_at = None
    if body.expires_days:
        expires_at = utcnow() + timedelta(days=body.expires_days)
    # 注册码/VIP码按哈希匹配，既有hint用于管理员复制；独立小组令牌只返回一次且不保存明文
    row = Invite(
        code_hash=digest(code.upper()),
        hint=code,
        remark=body.remark,
        vip_days=body.vip_days or 0,
        kind=body.kind,
        created_by=admin.id,
        expires_at=expires_at,
    )
    db.add(row)
    audit(db, request, "admin.create_invite", detail="生成1个邀请码")
    db.commit()
    db.refresh(row)
    return ok(invite_dict(row))


@router.delete("/invites/{invite_id}")
def delete_invite(invite_id: int, request: Request, db=Depends(get_db)):
    row = db.get(Invite, invite_id)
    if not row:
        raise ApiError(404, 40401, "邀请码不存在")
    if row.used_at:
        raise ApiError(400, 40001, "已使用的邀请码不能删除")
    db.delete(row)
    audit(db, request, "admin.delete_invite", detail=str(invite_id))
    db.commit()
    return ok()


# ---------------------------------------------------------------- 功能申请审批
@router.get("/requests")
def list_requests(status: str = "pending", db=Depends(get_db)):
    query = select(FeatureRequest, User).join(User, FeatureRequest.user_id == User.id)
    if status != "all":
        if status not in ("pending", "approved", "rejected", "revoked", "withdrawn"):
            raise ApiError(400, 40001, "未知的申请状态")
        query = query.where(FeatureRequest.status == status)
    rows = db.execute(query.order_by(FeatureRequest.id.desc()).limit(200)).all()
    return ok([admin_request_dict(r, u) for r, u in rows])


@router.post("/requests/{rid}/review")
def review_request(
    rid: int,
    body: FeatureRequestReview,
    request: Request,
    db=Depends(get_db),
    admin=Depends(get_admin),
):
    row = db.get(FeatureRequest, rid)
    if not row:
        raise ApiError(404, 40401, "申请不存在")
    if row.status != "pending":
        raise ApiError(400, 40001, "该申请已处理")
    if body.action == "reject" and len(body.note.strip()) < 5:
        raise ApiError(400, 40001, "驳回原因至少5个字")
    claimed = db.execute(
        sa_update(FeatureRequest)
        .where(FeatureRequest.id == rid, FeatureRequest.status == "pending")
        .values(
            status="approved" if body.action == "approve" else "rejected",
            active_key=row.active_key if body.action == "approve" else None,
        )
    ).rowcount
    if claimed != 1:
        raise ApiError(400, 40001, "该申请已被其他管理员处理")
    row.status = "approved" if body.action == "approve" else "rejected"
    row.review_note = body.note.strip()
    row.reviewed_by = admin.id
    row.reviewed_at = utcnow()
    row.approval_source = "manual"
    if body.action == "reject":
        row.active_key = None
    user = db.get(User, row.user_id)
    label = FEATURE_LABELS.get(row.feature, row.feature)
    if row.status == "approved":
        # 审批同事务写入授权表：鉴权只读 grant，撤销后立即失效
        feature_service.grant_feature(
            db, user.id, row.feature, admin_id=admin.id, request_id=row.id
        )
        title = "功能申请已通过"
        content = f"你申请的「{label}」已通过。" + (
            f"备注：{row.review_note}" if row.review_note else ""
        )
    else:
        title = "功能申请被驳回"
        content = f"你申请的「{label}」被驳回。原因：{row.review_note or '未填写'}"
    create_message(
        db,
        user,
        "apply",
        title,
        content,
        link="/requests",
        dedupe_key=f"apply:{rid}",
        email=True,
        settings=request.app.state.settings,
    )
    audit(
        db,
        request,
        "admin.review_request",
        user_id=row.user_id,
        detail=f"{rid} {row.status} {row.review_note}".strip(),
    )
    db.commit()
    return ok(admin_request_dict(row, user))


@router.get("/email-jobs")
def email_jobs(status: str = "all", db=Depends(get_db)):
    if status not in {
        "all",
        "pending",
        "retry",
        "sending",
        "sent",
        "failed",
        "cancelled",
    }:
        raise ApiError(400, 40001, "邮件状态无效")
    query = select(EmailJob)
    if status != "all":
        query = query.where(EmailJob.status == status)
    rows = db.scalars(query.order_by(EmailJob.id.desc()).limit(200)).all()
    return ok(
        [
            {
                "id": row.id,
                "user_id": row.user_id,
                "recipient": row.recipient,
                "subject": row.subject,
                "status": row.status,
                "attempts": row.attempts,
                "last_error": row.last_error or "",
                "next_attempt_at": iso(row.next_attempt_at),
                "sent_at": iso(row.sent_at),
                "created_at": iso(row.created_at),
            }
            for row in rows
        ]
    )


@router.post("/email-jobs/{job_id}/retry")
def retry_email_job(
    job_id: int, request: Request, db=Depends(get_db), admin=Depends(get_admin)
):
    row = db.get(EmailJob, job_id)
    if not row:
        raise ApiError(404, 40401, "邮件任务不存在")
    if row.status not in {"failed", "retry"}:
        raise ApiError(409, 40901, "该任务不处于可重试状态")
    user = db.get(User, row.user_id)
    if not user or user.status == "deleted":
        raise ApiError(400, 40001, "账号已注销，不能重发")
    row.status, row.attempts, row.lease_token = "pending", 0, None
    row.next_attempt_at, row.last_error = utcnow(), ""
    audit(db, request, "email.retry", user_id=row.user_id, detail=str(job_id))
    db.commit()
    return ok({"queued": True})


@router.post("/requests/{rid}/revoke")
def revoke_request(
    rid: int, request: Request, db=Depends(get_db), admin=Depends(get_admin)
):
    row = db.get(FeatureRequest, rid)
    if not row:
        raise ApiError(404, 40401, "申请不存在")
    if row.status != "approved":
        raise ApiError(400, 40001, "只有已通过的申请可以撤销")
    claimed = db.execute(
        sa_update(FeatureRequest)
        .where(FeatureRequest.id == rid, FeatureRequest.status == "approved")
        .values(status="revoked", active_key=None)
    ).rowcount
    if claimed != 1:
        raise ApiError(400, 40001, "申请状态已变化，请刷新")
    row.status = "revoked"
    row.active_key = None
    row.review_note = (row.review_note + " / 管理员撤销").strip(" /")
    row.reviewed_by = admin.id
    row.reviewed_at = utcnow()
    feature_service.revoke_feature(db, row.user_id, row.feature, request_id=rid)
    user = db.get(User, row.user_id)
    label = FEATURE_LABELS.get(row.feature, row.feature)
    create_message(
        db,
        user,
        "apply",
        "功能授权已撤销",
        f"你申请的「{label}」审批授权已撤销；其他有效VIP或授权仍保留。",
        link="/requests",
        dedupe_key=f"apply-revoke:{rid}",
        email=True,
        settings=request.app.state.settings,
    )
    audit(db, request, "admin.revoke_request", user_id=row.user_id, detail=str(rid))
    db.commit()
    return ok(admin_request_dict(row, user))


# ---------------------------------------------------------------- 公告
@router.post("/announcements")
def create_announcement(
    body: AnnouncementInput,
    request: Request,
    db=Depends(get_db),
    admin=Depends(get_admin),
):
    row = Announcement(content=body.content, created_by=admin.id)
    db.add(row)
    audit(db, request, "admin.create_announcement", user_id=admin.id)
    db.commit()
    db.refresh(row)
    return ok(
        {
            "id": row.id,
            "content": row.content,
            "is_active": row.is_active,
            "revision": row.revision,
            "created_at": iso(row.created_at),
        }
    )


@router.put("/announcements/{ann_id}")
def update_announcement(
    ann_id: int, body: AnnouncementUpdate, request: Request, db=Depends(get_db)
):
    row = db.get(Announcement, ann_id)
    if not row:
        raise ApiError(404, 40401, "公告不存在")
    expected = body.expected_revision or row.revision
    if row.revision != expected:
        raise ApiError(409, 40902, "公告已修改，请刷新后重试")
    before = {
        "content": row.content,
        "is_active": row.is_active,
        "revision": row.revision,
    }
    values = body.model_dump(exclude_none=True, exclude={"expected_revision"})
    if not values:
        raise ApiError(400, 40001, "没有变更内容")
    values["revision"] = expected + 1
    changed = db.execute(
        sa_update(Announcement)
        .where(Announcement.id == ann_id, Announcement.revision == expected)
        .values(**values)
    ).rowcount
    if not changed:
        db.rollback()
        raise ApiError(409, 40902, "公告已被其他请求修改")
    audit(
        db,
        request,
        "admin.update_announcement",
        detail=json.dumps(
            {"id": ann_id, "before": before, "after": values}, ensure_ascii=False
        ),
    )
    db.commit()
    db.refresh(row)
    return ok(
        {
            "id": row.id,
            "content": row.content,
            "is_active": row.is_active,
            "revision": row.revision,
        }
    )


@router.delete("/announcements/{ann_id}")
def delete_announcement(ann_id: int, request: Request, db=Depends(get_db)):
    row = db.get(Announcement, ann_id)
    if not row:
        raise ApiError(404, 40401, "公告不存在")
    db.delete(row)
    audit(db, request, "admin.delete_announcement", detail=str(ann_id))
    db.commit()
    return ok()


@router.get("/announcements")
def list_announcements(db=Depends(get_db)):
    rows = db.scalars(
        select(Announcement).order_by(Announcement.id.desc()).limit(50)
    ).all()
    return ok(
        [
            {
                "id": r.id,
                "content": r.content,
                "is_active": r.is_active,
                "revision": r.revision,
                "created_at": iso(r.created_at),
            }
            for r in rows
        ]
    )


# ---------------------------------------------------------------- 审计日志
@router.get("/audit-logs")
def audit_logs(
    limit: int = 100,
    before_id: int = 0,
    action: str = "",
    actor_id: int | None = None,
    db=Depends(get_db),
):
    limit = min(max(limit, 1), 200)
    query = select(Audit)
    if before_id:
        query = query.where(Audit.id < before_id)
    if action:
        query = query.where(Audit.action.contains(action[:100], autoescape=True))
    if actor_id is not None:
        query = query.where(Audit.actor_id == actor_id)
    rows = db.scalars(query.order_by(Audit.id.desc()).limit(limit)).all()
    return ok(
        [
            {
                "id": r.id,
                "user_id": r.user_id,
                "actor_id": r.actor_id,
                "action": r.action,
                "ip": r.ip,
                "detail": r.detail,
                "created_at": iso(r.created_at),
            }
            for r in rows
        ]
    )


# ---------------------------------------------------------------- 站点配置
from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import date
from ..services.sync import sync_write_lock

CONFIG_WHITELIST = {"site_name", "exam_date", "exam_year", "registration_open"}


class ConfigInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)
    expected_revision: int | None = Field(default=None, ge=0)
    site_name: str | None = Field(default=None, min_length=1, max_length=60)
    exam_date: str | None = None
    exam_year: int | None = Field(default=None, ge=2000, le=2100)
    registration_open: bool | None = None

    @field_validator("exam_date")
    @classmethod
    def valid_date(cls, value):
        if value is not None and date.fromisoformat(value).isoformat() != value:
            raise ValueError("invalid date")
        return value


def config_payload(db):
    return {
        "revision": config_get(db, "admin_config_revision", 0),
        "values": {
            k: config_get(
                db,
                k,
                {
                    "site_name": "研时",
                    "exam_date": "2027-12-25",
                    "exam_year": 2028,
                    "registration_open": False,
                }[k],
            )
            for k in CONFIG_WHITELIST
        },
    }


@router.get("/config")
def get_config(request: Request, db=Depends(get_db)):
    return ok(
        {
            **config_payload(db),
            "auth_password_only": request.app.state.settings.auth_password_only,
        }
    )


@router.put("/config")
def update_config(
    body: ConfigInput, request: Request, db=Depends(get_db), admin=Depends(get_admin)
):
    if request.app.state.settings.auth_password_only and body.registration_open is True:
        raise ApiError(403, 40301, "内测期间仅支持账号密码登录，账号请由管理员创建")
    settings=request.app.state.settings
    if settings.environment=='production' and body.registration_open is True and not (settings.smtp_host and settings.smtp_user and settings.smtp_password):
        raise ApiError(400,40001,'请先配置SMTP再开放注册')
    with sync_write_lock:
        db.scalar(select(User).where(User.id == admin.id).with_for_update())
        current = config_payload(db)
        revision = current["revision"]
        if body.expected_revision is not None and body.expected_revision != revision:
            raise ApiError(
                409,
                40902,
                "配置已修改，请比较当前配置后重试",
                data={"current": current},
            )
        changed = body.model_dump(exclude_none=True, exclude={"expected_revision"})
        if not changed:
            raise ApiError(400, 40001, "没有可更新的配置项")
        token = db.get(Config, "admin_config_revision")
        if token:
            updated = db.execute(
                sa_update(Config)
                .where(
                    Config.config_key == "admin_config_revision",
                    Config.config_value == token.config_value,
                )
                .values(config_value=json.dumps(revision + 1))
            ).rowcount
            if not updated:
                db.rollback()
                raise ApiError(409, 40902, "配置已变化，请重试")
        else:
            db.add(
                Config(
                    config_key="admin_config_revision",
                    config_value=json.dumps(revision + 1),
                    updated_by=admin.id,
                )
            )
        for key, value in changed.items():
            row = db.get(Config, key)
            if not row:
                row = Config(config_key=key, config_value="null")
                db.add(row)
            row.config_value = json.dumps(value, ensure_ascii=False)
            row.updated_by = admin.id
            row.updated_at = utcnow()
        audit(
            db,
            request,
            "admin.update_config",
            detail=json.dumps(
                {
                    "before": current["values"],
                    "changes": changed,
                    "revision": revision + 1,
                },
                ensure_ascii=False,
            ),
        )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ApiError(409, 40902, "配置已被其他请求修改，请刷新比较") from None
        return ok({**changed, "revision": revision + 1})


# ---------------------------------------------------------------- 全量数据导出（备份）
@router.get("/export")
def export_data(db=Depends(get_db)):
    users = [
        {
            "id": u.id,
            "email": u.email,
            "nickname": u.nickname,
            "role": u.role,
            "status": u.status,
            "vip_until": iso(u.vip_until),
            "created_at": iso(u.created_at),
        }
        for u in db.scalars(select(User).order_by(User.id)).all()
    ]
    records = []  # 账号运维导出永不导出成员学习明细，管理员也没有隐私绕过。
    payload = {"exported_at": iso(utcnow()), "users": users, "records": records}
    return JSONResponse({"code": 0, "message": "ok", "data": payload})


class BatchInvites(InviteCreate):
    count: int = Field(default=5, ge=1, le=100, strict=True)


@router.post("/invites/batch")
def batch_invites(
    body: BatchInvites, request: Request, user=Depends(get_admin), db=Depends(get_db)
):
    rows = []
    for _ in range(body.count):
        code = new_invite_code()
        row = Invite(
            code_hash=digest(code.upper()),
            hint=code,
            remark=body.remark,
            vip_days=body.vip_days or 0,
            kind=body.kind,
            created_by=user.id,
            expires_at=utcnow() + timedelta(days=body.expires_days)
            if body.expires_days
            else None,
        )
        db.add(row)
        rows.append(row)
    audit(db, request, "admin.batch_invites", detail=str(body.count))
    db.commit()
    return ok([invite_dict(row) for row in rows])
