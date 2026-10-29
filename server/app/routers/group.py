from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from ..deps import get_current_user, get_db, get_admin
from ..models import User, RoomMember, Room
from ..schemas.room import HeartbeatInput
from ..services.presence import member_states, update_presence
from pydantic import Field
from ..errors import ok, ApiError
from ..services.group import shared_user_ids, shared_records, shared_changes

router = APIRouter(prefix="/api/v1", tags=["study-group"])


@router.get("/group/members")
def members(
    room_id: int | None = Query(default=None, gt=0),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if room_id is not None:
        member = db.scalar(
            select(RoomMember)
            .join(Room)
            .where(
                RoomMember.room_id == room_id,
                RoomMember.user_id == user.id,
                RoomMember.sharing_confirmed.is_(True),
                Room.dissolved_at.is_(None),
            )
        )
        if member is None:
            raise ApiError(404, 40401, "请先加入该房间并确认共享")
    rows = db.scalars(
        select(User)
        .where(
            User.status == "active",
            User.id.in_(shared_user_ids(user.id, room_id)),
        )
        .order_by(User.id)
    ).all()
    states = member_states(db, user, rows)
    return ok(
        [
            {
                "id": row.id,
                "nickname": row.nickname,
                "avatar_key": row.avatar_key or "",
                "is_private_mode": bool(row.is_private_mode),
                **states[row.id],
            }
            for row in rows
        ]
    )


@router.get("/group/members/{uid}/learning")
def learning(
    uid: int,
    after: str = "",
    kind: Literal["subject", "session", "task", "mistake"] | None = None,
    room_id: int | None = Query(default=None, gt=0),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    require_room_scope(db, user, uid, room_id)
    return ok(shared_records(db, user, uid, after, kind))


@router.get("/group/members/{uid}/learning/changes")
def learning_changes(
    uid: int,
    since: int = Query(default=0, ge=0, le=9223372036854775807),
    room_id: int | None = Query(default=None, gt=0),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    require_room_scope(db, user, uid, room_id)
    return ok(shared_changes(db, user, uid, since))


@router.post("/admin/group-members/{uid}")
@router.delete("/admin/group-members/{uid}")
def retired_membership(uid: int, user=Depends(get_admin)):
    raise ApiError(
        410, 41001, "旧全站共享小组已停用，请由用户凭房间邀请或申请加入好友房间"
    )


class SiteHeartbeat(HeartbeatInput):
    device_id: str = Field(
        default="legacy", min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$"
    )
    room_id: int | None = Field(default=None, gt=0)


@router.post("/group/presence")
def presence(body: SiteHeartbeat, user=Depends(get_current_user), db=Depends(get_db)):
    return ok(update_presence(db, user, body))


def require_room_scope(db, user, uid, room_id):
    if (
        room_id is not None
        and db.scalar(
            select(User.id).where(
                User.id == uid,
                User.id.in_(shared_user_ids(user.id, room_id)),
            )
        )
        is None
    ):
        raise ApiError(404, 40401, "该房间中没有可共享的成员")
