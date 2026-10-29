"""Independent single-group invitations; approval grants learning sharing, never room/VIP rights."""

import secrets, json
from datetime import timedelta
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from ..deps import get_current_user, get_db, audit
from ..models import GroupInvite, GroupApply, StudyGroupMember, User
from ..errors import ApiError, ok
from ..time import utcnow
from ..serializers import iso
from ..services.transient import digest
from ..services.group import enroll
from ..services.write_guard import account_write
from ..services.messages import create_message

router = APIRouter(prefix="/api/v1/group-admission", tags=["group-admission"])
GROUP_ID = 1


def manager(db, user):
    if user.role != "admin" or not db.get(StudyGroupMember, (GROUP_ID, user.id)):
        raise ApiError(403, 40301, "需要本学习小组管理员权限")


def payload(row, db, reviewer=False):
    result = {
        "id": row.id,
        "status": row.status,
        "revision": row.revision,
        "reason": row.reason,
        "remark": row.remark,
        "created_at": iso(row.created_at),
        "reviewed_at": iso(row.reviewed_at),
    }
    if reviewer:
        user = db.get(User, row.user_id)
        result["user"] = {"id": user.id, "nickname": user.nickname, "email": user.email}
    return result


class InviteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expires_hours: int = Field(default=24, ge=1, le=168, strict=True)
    target_user_id: int | None = Field(default=None, ge=1)


@router.post("/invites")
def invite(
    body: InviteInput,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    manager(db, user)
    if body.target_user_id and not db.get(User, body.target_user_id):
        raise ApiError(404, 40401, "接收账号不存在")
    token = secrets.token_urlsafe(24)
    row = GroupInvite(
        group_id=GROUP_ID,
        token_hash=digest(token),
        created_by=user.id,
        target_user_id=body.target_user_id,
        expires_at=utcnow() + timedelta(hours=body.expires_hours),
    )
    db.add(row)
    db.flush()
    audit(
        db,
        request,
        "group.invite_create",
        user_id=body.target_user_id,
        detail=str(row.id),
    )
    db.commit()
    return ok(
        {
            "id": row.id,
            "kind": "group_invite",
            "code": token,
            "expires_at": iso(row.expires_at),
            "approval_required": True,
        }
    )


@router.get("/invites")
def invites(user=Depends(get_current_user), db=Depends(get_db)):
    manager(db, user)
    rows = db.scalars(
        select(GroupInvite)
        .where(GroupInvite.group_id == GROUP_ID)
        .order_by(GroupInvite.id.desc())
        .limit(100)
    ).all()
    return ok(
        [
            {
                "id": r.id,
                "expires_at": iso(r.expires_at),
                "revoked_at": iso(r.revoked_at),
                "reserved_by": r.consumed_by,
                "target_user_id": r.target_user_id,
            }
            for r in rows
        ]
    )


@router.post("/invites/{iid}/revoke")
def revoke(
    iid: int, request: Request, user=Depends(get_current_user), db=Depends(get_db)
):
    manager(db, user)
    with account_write(db, user.id):
        row = db.scalar(
            select(GroupInvite)
            .where(GroupInvite.id == iid, GroupInvite.group_id == GROUP_ID)
            .with_for_update()
        )
        if not row:
            raise ApiError(404, 40401, "邀请不存在")
        if not row.revoked_at:
            row.revoked_at = utcnow()
            for apply in db.scalars(
                select(GroupApply)
                .where(GroupApply.invite_id == iid, GroupApply.status == "pending")
                .with_for_update()
            ).all():
                apply.status = "rejected"
                apply.pending_key = None
                apply.revision += 1
                apply.remark = "邀请已撤销"
                apply.reviewed_by = user.id
                apply.reviewed_at = utcnow()
                create_message(
                    db,
                    db.get(User, apply.user_id),
                    "apply",
                    "小组邀请已撤销",
                    "入组申请未获通过，邀请已撤销。",
                    link="/group/admission",
                )
            audit(db, request, "group.invite_revoke", detail=str(iid))
        db.commit()
        return ok()


class ApplyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: str = Field(min_length=1, max_length=128)
    reason: str = Field(default="", max_length=300)


@router.post("/applications")
def apply(
    body: ApplyInput,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    request.app.state.transient.limit(f"group-apply:{user.id}", 10, 300)
    with account_write(db, user.id):
        if db.get(StudyGroupMember, (GROUP_ID, user.id)):
            raise ApiError(409, 40901, "你已在学习小组中")
        row = db.scalar(
            select(GroupInvite)
            .where(
                GroupInvite.token_hash == digest(body.code),
                GroupInvite.group_id == GROUP_ID,
            )
            .with_for_update()
        )
        if (
            not row
            or row.revoked_at
            or row.expires_at <= utcnow()
            or (row.target_user_id and row.target_user_id != user.id)
            or (row.consumed_by and row.consumed_by != user.id)
        ):
            raise ApiError(400, 40001, "小组邀请码无效、过期、已撤销或已被其他账号使用")
        old = db.scalar(
            select(GroupApply).where(GroupApply.pending_key == f"{GROUP_ID}:{user.id}")
        )
        if old:
            return ok(payload(old, db))
        row.consumed_by = user.id
        entry = GroupApply(
            group_id=GROUP_ID,
            user_id=user.id,
            invite_id=row.id,
            pending_key=f"{GROUP_ID}:{user.id}",
            reason=body.reason,
            status="pending",
            revision=1,
            remark="",
        )
        db.add(entry)
        db.flush()
        audit(db, request, "group.apply", user_id=user.id, detail=str(entry.id))
        db.commit()
        return ok(payload(entry, db))


@router.get("/mine")
def mine(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(
        select(GroupApply)
        .where(GroupApply.user_id == user.id, GroupApply.group_id == GROUP_ID)
        .order_by(GroupApply.id.desc())
        .limit(50)
    ).all()
    return ok(
        {
            "is_member": bool(db.get(StudyGroupMember, (GROUP_ID, user.id))),
            "applications": [payload(r, db) for r in rows],
        }
    )


class VersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)


@router.post("/applications/{aid}/withdraw")
def withdraw(
    aid: int,
    body: VersionInput,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    with account_write(db, user.id):
        row = db.scalar(
            select(GroupApply)
            .where(GroupApply.id == aid, GroupApply.user_id == user.id)
            .with_for_update()
        )
        if not row:
            raise ApiError(404, 40401, "申请不存在")
        if row.status != "pending" or row.revision != body.expected_revision:
            raise ApiError(409, 40902, "申请已处理或已变化")
        row.status = "cancelled"
        row.pending_key = None
        row.revision += 1
        audit(db, request, "group.withdraw", user_id=user.id, detail=str(aid))
        db.commit()
        return ok(payload(row, db))


@router.get("/applications")
def queue(user=Depends(get_current_user), db=Depends(get_db)):
    manager(db, user)
    rows = db.scalars(
        select(GroupApply)
        .where(GroupApply.group_id == GROUP_ID, GroupApply.status == "pending")
        .order_by(GroupApply.id)
        .limit(100)
    ).all()
    return ok([payload(r, db, True) for r in rows])


class ReviewInput(VersionInput):
    approve: bool = Field(strict=True)
    remark: str = Field(default="", max_length=300)


@router.post("/applications/{aid}/review")
def review(
    aid: int,
    body: ReviewInput,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    manager(db, user)
    with account_write(db, user.id):
        row = db.scalar(
            select(GroupApply)
            .where(GroupApply.id == aid, GroupApply.group_id == GROUP_ID)
            .with_for_update()
        )
        if not row:
            raise ApiError(404, 40401, "申请不存在")
        if row.status != "pending" or row.revision != body.expected_revision:
            raise ApiError(409, 40902, "申请已处理或已变化")
        invitation = db.scalar(
            select(GroupInvite).where(GroupInvite.id == row.invite_id).with_for_update()
        )
        target = db.get(User, row.user_id)
        if body.approve:
            if (
                target.status != "active"
                or invitation.revoked_at
                or invitation.expires_at <= utcnow()
                or invitation.consumed_by != target.id
            ):
                raise ApiError(409, 40902, "账号或邀请已失效，不能批准")
            enroll(db, target.id)
        elif not body.remark.strip():
            raise ApiError(400, 40001, "驳回必须填写原因")
        before = {"status": row.status, "revision": row.revision}
        row.status = "approved" if body.approve else "rejected"
        row.pending_key = None
        row.revision += 1
        row.reviewed_by = user.id
        row.reviewed_at = utcnow()
        row.remark = body.remark.strip()
        create_message(
            db,
            target,
            "apply",
            "学习小组申请已处理",
            "已通过，学习数据按隐私设置共享；房间准入仍独立。"
            if body.approve
            else "未通过：" + row.remark,
            link="/group/admission",
            email=True,
            settings=request.app.state.settings,
        )
        audit(
            db,
            request,
            "group.review",
            user_id=target.id,
            detail=json.dumps(
                {
                    "apply_id": aid,
                    "before": before,
                    "after": {"status": row.status, "revision": row.revision},
                    "reason": row.remark,
                },
                ensure_ascii=False,
            ),
        )
        db.commit()
        return ok(payload(row, db, True))
