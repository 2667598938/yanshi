"""多自习室：列表、创建、凭码加入、房主管理、房内状态与留言。"""

from typing import Literal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select

from ..deps import audit, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import Room, User
from ..schemas.room import (
    ApplyReviewInput,
    GoalInput,
    HeartbeatInput,
    MessageInput,
    RoomApplyInput,
    RoomCreate,
    RoomJoin,
    RoomUpdate,
)
from ..services import room as room_service

router = APIRouter(prefix="/api/v1/rooms", tags=["rooms"])


@router.get("")
def list_rooms(db=Depends(get_db), user: User = Depends(get_current_user)):
    return ok(room_service.list_rooms(db, user))


@router.post("")
def create_room(
    body: RoomCreate,
    request: Request,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    request.app.state.transient.limit(f"room-create:{user.id}", 5, 3600)
    require_sharing(body.accept_sharing)
    room = room_service.create_room(
        db, user, body.name, body.intro, body.visibility, body.room_type
    )
    audit(db, request, "room.create", user_id=user.id, detail=f"{room.id} {room.name}")
    db.commit()
    return ok(room_service.room_summary(db, room, user))


@router.post("/join-by-code")
def join_by_code(
    body: RoomJoin,
    request: Request,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_sharing(body.accept_sharing)
    request.app.state.transient.limit(f"room-code:{user.id}", 30, 60)
    code = body.code.strip().upper()
    if len(code) > 32:
        raise ApiError(400, 40001, "房间码不正确")
    room = db.scalar(select(Room).where(Room.code == code, Room.dissolved_at.is_(None)))
    if room is None:
        raise ApiError(404, 40401, "房间码不存在")
    state = room_service.join_room(db, user, room, code)
    audit(db, request, "room.join_by_code", user_id=user.id, detail=str(room.id))
    db.commit()
    return ok(state)


@router.get("/{room_id}")
def get_room(room_id: int, db=Depends(get_db), user: User = Depends(get_current_user)):
    room = room_service.get_room(db, room_id)
    return ok(room_service.room_state(db, user, room))


@router.post("/{room_id}/join")
def join_room(
    room_id: int,
    body: RoomJoin,
    request: Request,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = room_service.get_room(db, room_id)
    require_sharing(body.accept_sharing)
    request.app.state.transient.limit(f"room-code:{user.id}", 30, 60)
    state = room_service.join_room(db, user, room, body.code)
    audit(db, request, "room.join", user_id=user.id, detail=str(room_id))
    db.commit()
    return ok(state)


@router.post("/{room_id}/leave")
def leave_room(
    room_id: int, db=Depends(get_db), user: User = Depends(get_current_user)
):
    return ok(room_service.leave_room(db, user, room_service.get_room(db, room_id)))


@router.get("/{room_id}/preview")
def preview_room(
    room_id: int, db=Depends(get_db), user: User = Depends(get_current_user)
):
    """私密房间未加入时的公开预览：只给房间信息与本人申请状态。"""
    room = room_service.get_room(db, room_id)
    return ok(room_service.room_preview(db, user, room))


@router.post("/{room_id}/apply")
def apply_room(
    room_id: int,
    body: RoomApplyInput,
    request: Request,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    request.app.state.transient.limit(f"room-apply:{user.id}", 10, 3600)
    room = room_service.get_room(db, room_id)
    require_sharing(body.accept_sharing)
    row = room_service.apply_join(db, user, room, body.message)
    audit(db, request, "room.apply", user_id=user.id, detail=f"{room_id} {row['id']}")
    db.commit()
    return ok(row)


@router.get("/{room_id}/applies")
def list_applies(
    room_id: int,
    status: Literal["pending", "approved", "rejected"] = "pending",
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = room_service.get_room(db, room_id)
    return ok(room_service.list_applies(db, user, room, status))


@router.post("/{room_id}/applies/{apply_id}/review")
def review_apply(
    room_id: int,
    apply_id: int,
    body: ApplyReviewInput,
    request: Request,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = room_service.get_room(db, room_id)
    row = room_service.review_apply(db, user, room, apply_id, body.approve)
    audit(
        db,
        request,
        "room.apply.review",
        user_id=user.id,
        detail=f"{room_id} {apply_id} {row['status']}",
    )
    db.commit()
    return ok(row)


@router.patch("/{room_id}")
def update_room(
    room_id: int,
    body: RoomUpdate,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = room_service.get_room(db, room_id)
    return ok(
        room_service.update_room(db, user, room, body.name, body.intro, body.visibility)
    )


@router.post("/{room_id}/code")
def regenerate_code(
    room_id: int, db=Depends(get_db), user: User = Depends(get_current_user)
):
    room = room_service.get_room(db, room_id)
    return ok(room_service.regenerate_code(db, user, room))


@router.delete("/{room_id}/members/{uid}")
def kick_member(
    room_id: int, uid: int, db=Depends(get_db), user: User = Depends(get_current_user)
):
    room = room_service.get_room(db, room_id)
    return ok(room_service.kick_member(db, user, room, uid))


@router.delete("/{room_id}")
def dissolve_room(
    room_id: int, db=Depends(get_db), user: User = Depends(get_current_user)
):
    room = room_service.get_room(db, room_id)
    return ok(room_service.dissolve_room(db, user, room))


@router.get("/{room_id}/ranking")
def get_ranking(
    room_id: int,
    range: Literal["today", "week", "all"] = "today",
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    state = room_service.room_state(db, user, room_service.get_room(db, room_id))
    return ok(
        {
            "range": range,
            "items": state["ranking"][range],
            "nicknames": {m["user_id"]: m["nickname"] for m in state["members"]},
        }
    )


@router.post("/{room_id}/heartbeat")
def heartbeat(
    room_id: int,
    body: HeartbeatInput,
    request: Request,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    request.app.state.transient.limit(f"room-hb:{user.id}", 60, 60)
    room = room_service.get_room(db, room_id)
    return ok(room_service.heartbeat(db, user, body, room))


@router.post("/{room_id}/messages")
def post_message(
    room_id: int,
    body: MessageInput,
    request: Request,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    request.app.state.transient.limit(f"room-msg:{user.id}", 20, 60)
    room = room_service.get_room(db, room_id)
    content = body.content.strip()
    if not content:
        raise ApiError(400, 40001, "留言不能为空")
    return ok(room_service.add_message(db, user, content, room))


@router.delete("/{room_id}/messages/{message_id}")
def remove_message(
    room_id: int,
    message_id: int,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = room_service.get_room(db, room_id)
    return ok(
        room_service.delete_message(db, user, message_id, user.role == "admin", room)
    )


@router.put("/{room_id}/goal")
def set_goal(
    room_id: int,
    body: GoalInput,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    room = room_service.get_room(db, room_id)
    return ok(room_service.upsert_goal(db, user, body, room))


def require_sharing(accepted):
    if not accepted:
        raise ApiError(
            400,
            40001,
            "请先确认：加入后与本房间成员共享学习数据，随时可开启隐私模式隐藏",
        )


@router.post("/{room_id}/sharing/confirm")
def confirm_sharing(
    room_id: int,
    body: RoomApplyInput,
    request: Request,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    require_sharing(body.accept_sharing)
    room = room_service.get_room(db, room_id)
    data = room_service.confirm_sharing(db, user, room)
    audit(db, request, "room.sharing.confirm", user_id=user.id, detail=str(room_id))
    db.commit()
    return ok(data)
