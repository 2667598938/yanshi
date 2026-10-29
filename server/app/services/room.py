"""多房间自习室领域服务：准入、成员、心跳在线、统计聚合、留言、目标墙。

排行榜从校验后的 session_facts 按人/日期聚合，冲突与非法记录不计入；
在线 / 正在学由心跳维持（room_presence），与学习记录解耦。
"""

from .group import shared_user_ids
from .presence import WINDOW as ONLINE_WINDOW_SEC
import secrets
import string
import time
import threading
from functools import wraps
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from ..errors import ApiError
from ..models import (
    LearningRecord,
    Room,
    RoomGoal,
    RoomJoinApply,
    RoomMember,
    RoomMessage,
    RoomPresence,
    User,
)
from ..serializers import iso
from ..time import utcnow
from . import messages as message_service

# 中国时区固定 UTC+8（无夏令时），用固定偏移避免依赖系统时区库
CN = timezone(timedelta(hours=8))
MAX_FOCUS_SEC = 3 * 3600  # 与学习计时上限一致；心跳只用于展示
MESSAGE_LIMIT = 50
room_write_lock = threading.RLock()


def room_write(fn):
    @wraps(fn)
    def guarded(db, *args, **kwargs):
        with room_write_lock:
            try:
                for value in args:
                    if isinstance(value, Room):
                        db.refresh(value, with_for_update=True)
                        actor = next(
                            (arg for arg in args if isinstance(arg, User)), None
                        )
                        guard_room_type(db, actor, value)
                        if value.dissolved_at is not None:
                            raise ApiError(404, 40401, "自习室已解散")
                return fn(db, *args, **kwargs)
            except Exception:
                db.rollback()
                raise

    return guarded


def guard_room_type(db, user, room):
    settings = db.info.get("settings")
    if not settings and room.room_type == "text_room":
        return
    if not settings or room.room_type not in settings.enabled_features:
        raise ApiError(403, 40310, "该房间类型暂未开放")
    if room.room_type == 'av_room' and room.media_mode == 'sfu' and (not settings.room_sfu_enabled or not settings.room_sfu_url):
        raise ApiError(403,40310,"SFU服务尚未部署")
    if user and room.room_type != "text_room":
        from .features import require_feature

        require_feature(db, user, "room", "该房间类型需要VIP或房间审批授权")


def get_default_room(db, user):
    room = db.scalar(
        select(Room)
        .join(RoomMember, RoomMember.room_id == Room.id)
        .where(
            RoomMember.user_id == user.id,
            ((RoomMember.sharing_confirmed.is_(True)) | (Room.owner_id == user.id)),
            Room.dissolved_at.is_(None),
            Room.room_type == "text_room",
        )
        .order_by(Room.id)
        .limit(1)
    )
    if room is None:
        raise ApiError(404, 40401, "请先创建好友房间或凭邀请加入")
    return room


def get_room(db, room_id):
    room = db.get(Room, room_id)
    if room is None or room.dissolved_at is not None:
        raise ApiError(404, 40401, "自习室不存在或已解散")
    guard_room_type(db, None, room)
    return room


def get_membership(db, room_id, user_id):
    return db.scalar(
        select(RoomMember).where(
            RoomMember.room_id == room_id, RoomMember.user_id == user_id
        )
    )


def require_member(db, user, room):
    guard_room_type(db, user, room)
    member = get_membership(db, room.id, user.id)
    if member is None or (not member.sharing_confirmed and room.owner_id != user.id):
        raise ApiError(403, 40301, "请凭房主的新邀请或申请审批加入自习室")
    return member


def _new_room_code(db):
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(50):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if not db.scalar(select(Room.id).where(Room.code == code)):
            return code
    raise ApiError(500, 50001, "房间码生成失败，请重试")


_UNLOADED = object()


def room_summary(
    db,
    room,
    user,
    member_count=None,
    online_count=None,
    membership=_UNLOADED,
    owner=_UNLOADED,
):
    if membership is _UNLOADED:
        membership = get_membership(db, room.id, user.id)
    legacy_member = bool(
        membership and not membership.sharing_confirmed and room.owner_id != user.id
    )
    if legacy_member:
        membership = None
    if member_count is None:
        member_count = (
            db.scalar(
                select(func.count())
                .select_from(RoomMember)
                .join(Room, Room.id == RoomMember.room_id)
                .where(
                    RoomMember.room_id == room.id,
                    RoomMember.sharing_confirmed.is_(True)
                    | (Room.owner_id == RoomMember.user_id),
                )
            )
            or 0
        )
    if online_count is None:
        cutoff = utcnow() - timedelta(seconds=ONLINE_WINDOW_SEC)
        online_count = (
            db.scalar(
                select(func.count())
                .select_from(RoomPresence)
                .join(User, User.id == RoomPresence.user_id)
                .where(
                    (
                        (User.id == user.id)
                        | (
                            (User.is_private_mode == False)
                            & User.id.in_(shared_user_ids(user.id, room.id))
                        )
                    ),
                    RoomPresence.room_id == room.id,
                    RoomPresence.status != "offline",
                    RoomPresence.last_heartbeat_at >= cutoff,
                )
            )
            or 0
        )
    if owner is _UNLOADED:
        owner = db.get(User, room.owner_id) if room.owner_id else None
    data = {
        "id": room.id,
        "name": room.name,
        "intro": room.intro or "",
        "visibility": room.visibility,
        "capacity": room.capacity,
        "sharing_confirmed": bool(membership and membership.sharing_confirmed),
        "legacy_member": legacy_member,
        "room_type": room.room_type,
        "media_mode": room.media_mode or "",
        "member_count": int(member_count),
        "online_count": int(online_count) if membership else 0,
        "joined": membership is not None,
        "my_role": ("owner" if room.owner_id == user.id else "member")
        if membership
        else "",
        "owner": {"id": owner.id, "nickname": owner.nickname} if owner else None,
        "created_at": iso(room.created_at),
    }
    # 房间码只给成员看；私密房间未加入者走预览接口，仅返回公开信息
    data["code"] = room.code if membership and room.owner_id == user.id else ""
    return data


def list_rooms(db, user):
    memberships = {
        m.room_id: m
        for m in db.scalars(
            select(RoomMember).where(RoomMember.user_id == user.id)
        ).all()
    }
    member_room_ids = set(memberships)
    rooms = db.scalars(
        select(Room).where(Room.dissolved_at.is_(None)).order_by(Room.id)
    ).all()
    settings = db.info.get("settings")
    enabled = settings.enabled_features if settings else ["text_room"]
    visible = [
        r
        for r in rooms
        if r.room_type in enabled
        and (r.visibility == "public" or r.id in member_room_ids)
    ]
    if not visible:
        return []
    ids = [r.id for r in visible]
    counts = dict(
        db.execute(
            select(RoomMember.room_id, func.count())
            .join(Room, Room.id == RoomMember.room_id)
            .where(
                RoomMember.room_id.in_(ids),
                RoomMember.sharing_confirmed.is_(True)
                | (Room.owner_id == RoomMember.user_id),
            )
            .group_by(RoomMember.room_id)
        ).all()
    )
    cutoff = utcnow() - timedelta(seconds=ONLINE_WINDOW_SEC)
    viewer_member = aliased(RoomMember)
    online = dict(
        db.execute(
            select(RoomPresence.room_id, func.count())
            .join(User, User.id == RoomPresence.user_id)
            .join(
                RoomMember,
                (RoomMember.room_id == RoomPresence.room_id)
                & (RoomMember.user_id == User.id),
            )
            .join(
                viewer_member,
                (viewer_member.room_id == RoomPresence.room_id)
                & (viewer_member.user_id == user.id),
            )
            .where(
                User.status == "active",
                (
                    (User.id == user.id)
                    | (
                        User.is_private_mode.is_(False)
                        & RoomMember.sharing_confirmed.is_(True)
                        & viewer_member.sharing_confirmed.is_(True)
                    )
                ),
                RoomPresence.room_id.in_(ids),
                RoomPresence.status != "offline",
                RoomPresence.last_heartbeat_at >= cutoff,
            )
            .group_by(RoomPresence.room_id)
        ).all()
    )
    owners = {
        u.id: u
        for u in db.scalars(
            select(User).where(User.id.in_({r.owner_id for r in visible}))
        ).all()
    }
    return [
        room_summary(
            db,
            r,
            user,
            counts.get(r.id, 0),
            online.get(r.id, 0),
            memberships.get(r.id),
            owners.get(r.owner_id),
        )
        for r in visible
    ]


@room_write
def create_room(db, user, name, intro, visibility, room_type="text_room", capacity=None, media_mode="mesh"):
    settings = db.info.get("settings")
    if room_type == "text_room":
        capacity = 50 if capacity is None else capacity
        if capacity not in (20, 50, 100):
            raise ApiError(400,40001,"文字房容量只能选择20、50或100人")
        media_mode = ""
    elif room_type == "av_room":
        if media_mode == "sfu":
            if not settings or not settings.room_sfu_enabled or not settings.room_sfu_url:
                raise ApiError(403,40310,"SFU服务尚未部署")
            expected_capacity=25
        else:
            expected_capacity=6
        if capacity not in (None,expected_capacity):
            raise ApiError(400,40001,"音视频房容量与传输模式不匹配")
        capacity=expected_capacity
    else:
        raise ApiError(400,40001,"未知房间类型")
    room = Room(
        name=name.strip(),
        intro=(intro or "").strip(),
        code=_new_room_code(db),
        owner_id=user.id,
        capacity=capacity,
        media_mode=media_mode,
        visibility=visibility,
        room_type=room_type,
    )
    guard_room_type(db, user, room)
    db.add(room)
    db.flush()
    db.add(
        RoomMember(
            room_id=room.id, user_id=user.id, role="owner", sharing_confirmed=True
        )
    )
    db.commit()
    db.refresh(room)
    return room


@room_write
def join_room(db, user, room, code=""):
    existing = get_membership(db, room.id, user.id)
    normalized = code.strip().upper()
    # compare_digest(str, str) rejects non-ASCII input with TypeError. A pasted
    # Chinese/full-width/emoji code must be a normal refusal, never HTTP 500.
    invited = (
        bool(normalized)
        and normalized.isascii()
        and room.code.isascii()
        and secrets.compare_digest(normalized, room.code.upper())
    )
    if (
        not (existing and (existing.sharing_confirmed or room.owner_id == user.id))
        and not invited
    ):
        raise ApiError(403, 40301, "请凭有效房间码加入，或先提交入房申请")
    ensure_member(db, user, room, sharing_confirmed=True)
    db.commit()
    return room_state(db, user, room)


def _apply_dict(row, user=None):
    data = {
        "id": row.id,
        "room_id": row.room_id,
        "user_id": row.user_id,
        "status": row.status,
        "message": row.message or "",
        "created_at": iso(row.created_at),
        "handled_at": iso(row.handled_at),
        "accept_sharing": bool(row.accept_sharing),
    }
    if user is not None:
        data.update(
            {
                "nickname": user.nickname,
                "avatar_key": user.avatar_key or "",
            }
        )
    return data


def latest_apply(db, room_id, user_id):
    return db.scalar(
        select(RoomJoinApply)
        .where(
            RoomJoinApply.room_id == room_id,
            RoomJoinApply.user_id == user_id,
        )
        .order_by(RoomJoinApply.id.desc())
        .limit(1)
    )


def room_preview(db, user, room):
    guard_room_type(db, user, room)
    """未加入只给房间说明与本人申请状态，不给成员身份、状态或学习明细。"""
    membership = get_membership(db, room.id, user.id)
    if membership and not membership.sharing_confirmed and room.owner_id != user.id:
        membership = None
    apply_row = latest_apply(db, room.id, user.id)
    return {
        "room": room_summary(db, room, user),
        "joined": membership is not None,
        "my_role": ("owner" if room.owner_id == user.id else "member")
        if membership
        else "",
        "join_required": membership is None,
        "apply": _apply_dict(apply_row) if apply_row else None,
    }


@room_write
def apply_join(db, user, room, message=""):
    """好友凭码免审；公开/私密房间的无码申请均由房主审核。"""
    existing = get_membership(db, room.id, user.id)
    if existing and (existing.sharing_confirmed or room.owner_id == user.id):
        raise ApiError(400, 40001, "你已经在这个自习室")
    member_count = (
        db.scalar(
            select(func.count())
            .select_from(RoomMember)
            .where(RoomMember.room_id == room.id)
        )
        or 0
    )
    if room.capacity > 0 and member_count >= room.capacity:
        raise ApiError(403, 40302, "自习室已满，暂时无法申请")
    pending = db.scalar(
        select(RoomJoinApply)
        .where(
            RoomJoinApply.room_id == room.id,
            RoomJoinApply.user_id == user.id,
            RoomJoinApply.status == "pending",
        )
        .with_for_update()
    )
    if pending is not None:
        if not pending.accept_sharing:
            pending.message = (message or "")[:200]
        pending.accept_sharing = True
        db.commit()
        return _apply_dict(pending)
    row = RoomJoinApply(
        room_id=room.id,
        user_id=user.id,
        status="pending",
        message=(message or "")[:200],
        pending_key=f"{room.id}-{user.id}",
        accept_sharing=True,
    )
    db.add(row)
    db.flush()
    owner = db.get(User, room.owner_id) if room.owner_id else None
    if owner is not None and owner.id != user.id:
        message_service.create_message(
            db,
            owner,
            kind="apply",
            title="新的入房申请",
            content=f"{user.nickname} 申请加入「{room.name}」：{row.message or '未填写申请说明'}",
            link=f"/rooms/{room.id}",
            dedupe_key=f"room-apply:{row.id}",
        )
    db.commit()
    db.refresh(row)
    return _apply_dict(row)


def list_applies(db, user, room, status="pending"):
    if room.owner_id != user.id:
        raise ApiError(403, 40301, "只有房主可以查看入房申请")
    rows = db.scalars(
        select(RoomJoinApply)
        .where(
            RoomJoinApply.room_id == room.id,
            RoomJoinApply.status == status,
        )
        .order_by(RoomJoinApply.created_at.asc(), RoomJoinApply.id.asc())
    ).all()
    users = {}
    if rows:
        users = {
            u.id: u
            for u in db.scalars(
                select(User).where(User.id.in_([r.user_id for r in rows]))
            ).all()
        }
    return {
        "status": status,
        "items": [_apply_dict(r, users.get(r.user_id)) for r in rows],
    }


@room_write
def review_apply(db, user, room, apply_id, approve):
    """房主通过/驳回；通过时立即写入成员，权限即时生效。"""
    if room.owner_id != user.id:
        raise ApiError(403, 40301, "只有房主可以审批入房申请")
    if approve and room.visibility == 'private':
        raise ApiError(410,41001,'私密房间请凭房间码加入')
    row = db.scalar(
        select(RoomJoinApply).where(RoomJoinApply.id == apply_id).with_for_update()
    )
    if row is None or row.room_id != room.id:
        raise ApiError(404, 40401, "申请不存在")
    if row.status != "pending":
        raise ApiError(400, 40001, "该申请已处理")
    applicant = db.get(User, row.user_id)
    if applicant is None:
        raise ApiError(404, 40401, "申请人不存在")
    if approve and not row.accept_sharing:
        raise ApiError(409, 40901, "旧申请尚未确认共享，请申请人重新确认并提交")
    existing = get_membership(db, room.id, row.user_id)
    if approve and (existing is None or not existing.sharing_confirmed):
        # 满员直接抛 403，pending 状态保持，房主可稍后再处理
        ensure_member(db, applicant, room, sharing_confirmed=True)
    row.status = "approved" if approve else "rejected"
    row.pending_key = None
    row.handled_at = utcnow()
    row.handled_by = user.id
    message_service.create_message(
        db,
        applicant,
        kind="apply",
        title="入房申请已通过" if approve else "入房申请未通过",
        content=(
            f"你已加入「{room.name}」，一起加油。"
            if approve
            else f"房主暂未通过你加入「{room.name}」的申请，可以稍后再申请。"
        ),
        link=f"/rooms/{room.id}",
        dedupe_key=f"room-apply-review:{row.id}",
    )
    db.commit()
    return _apply_dict(row, applicant)


@room_write
def leave_room(db, user, room):
    member = get_membership(db, room.id, user.id)
    if member is None:
        raise ApiError(400, 40001, "你还不在这个自习室")
    if room.owner_id == user.id:
        raise ApiError(400, 40001, "房主不能直接退出，请先解散房间")
    db.delete(member)
    presence = db.scalar(
        select(RoomPresence).where(
            RoomPresence.room_id == room.id, RoomPresence.user_id == user.id
        )
    )
    if presence:
        db.delete(presence)
    db.commit()
    return {"left": True}


@room_write
def update_room(db, user, room, name=None, intro=None, visibility=None):
    if room.owner_id != user.id:
        raise ApiError(403, 40301, "只有房主可以修改房间")
    if name is not None:
        room.name = name.strip()
    if intro is not None:
        room.intro = intro.strip()
    if visibility is not None:
        room.visibility = visibility
    db.commit()
    db.refresh(room)
    return room_summary(db, room, user)


@room_write
def kick_member(db, user, room, target_user_id):
    if room.owner_id != user.id:
        raise ApiError(403, 40301, "只有房主可以移除成员")
    target = get_membership(db, room.id, target_user_id)
    if target is None:
        raise ApiError(404, 40401, "该成员不在房间内")
    if target_user_id == room.owner_id:
        raise ApiError(400, 40001, "不能移除房主")
    db.delete(target)
    room.code = _new_room_code(
        db
    )  # Removed members cannot reuse a previously known invitation.
    presence = db.scalar(
        select(RoomPresence).where(
            RoomPresence.room_id == room.id, RoomPresence.user_id == target_user_id
        )
    )
    if presence:
        db.delete(presence)
    db.commit()
    return {"removed": target_user_id}


@room_write
def regenerate_code(db, user, room):
    if room.owner_id != user.id:
        raise ApiError(403, 40301, "只有房主可以更换房间码")
    room.code = _new_room_code(db)
    db.commit()
    return room_summary(db, room, user)


@room_write
def dissolve_room(db, user, room):
    if room.owner_id != user.id:
        raise ApiError(403, 40301, "只有房主可以解散房间")
    room.dissolved_at = utcnow()
    db.execute(delete_room_members(room.id))
    db.commit()
    return {"dissolved": True}


def delete_room_members(room_id):
    from sqlalchemy import delete

    return delete(RoomMember).where(RoomMember.room_id == room_id)


def ensure_member(
    db, user, room=None, role="member", ignore_capacity=False, sharing_confirmed=False
):
    room = room or get_default_room(db, user)
    guard_room_type(db, user, room)
    db.refresh(room, with_for_update=True)
    existing = db.scalar(
        select(RoomMember)
        .where(RoomMember.room_id == room.id, RoomMember.user_id == user.id)
        .with_for_update()
    )
    if existing:
        if sharing_confirmed:
            existing.sharing_confirmed = True
        return existing
    if not ignore_capacity and room.capacity > 0:
        count = len(
            db.scalars(
                select(RoomMember.id)
                .where(RoomMember.room_id == room.id)
                .with_for_update()
            ).all()
        )
        if room.capacity > 0 and count >= room.capacity:
            raise ApiError(403, 40301, "房间成员名额已满")
    member = RoomMember(
        room_id=room.id, user_id=user.id, role=role, sharing_confirmed=sharing_confirmed
    )
    db.add(member)
    db.flush()
    return member


def _cn_bounds():
    """返回中国时区的今天、本周一（YYYY-MM-DD 字符串）。"""
    now = datetime.now(CN)
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    return today.isoformat(), monday.isoformat()


def _aggregate_sessions(db, member_ids):
    """Aggregate validated facts by user/date; no per-record queries on polling."""
    from ..models import SessionFact

    today_str, monday_str = _cn_bounds()
    result = {
        uid: {"today_sec": 0, "week_sec": 0, "total_sec": 0, "dates": set()}
        for uid in member_ids
    }
    if not member_ids:
        return result
    rows = db.execute(
        select(
            SessionFact.user_id,
            SessionFact.study_date,
            func.sum(SessionFact.actual_sec),
        )
        .join(
            LearningRecord,
            (LearningRecord.user_id == SessionFact.user_id)
            & (LearningRecord.id == SessionFact.record_id),
        )
        .where(
            SessionFact.user_id.in_(member_ids),
            SessionFact.conflict.is_(False),
            LearningRecord.deleted == 0,
        )
        .group_by(SessionFact.user_id, SessionFact.study_date)
    ).all()
    for uid, day, seconds in rows:
        agg = result[uid]
        agg["total_sec"] += seconds
        if monday_str <= day <= today_str:
            agg["week_sec"] += seconds
        if day == today_str:
            agg["today_sec"] += seconds
        agg["dates"].add(day)
    return result


def _streak(dates: set, today_str: str) -> int:
    today = datetime.strptime(today_str, "%Y-%m-%d").date()
    # 今天还没学则从昨天往前数，保持连续天数不中断
    cursor = today if today_str in dates else today - timedelta(days=1)
    streak = 0
    while cursor.isoformat() in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def heartbeat(db, user, payload, room=None):
    room = room or get_default_room(db, user)
    require_member(db, user, room)
    from ..models import DevicePresence

    if db.scalar(
        select(DevicePresence.user_id).where(DevicePresence.user_id == user.id).limit(1)
    ):
        return {"status": payload.status, "server_time": int(time.time() * 1000)}
    presence = db.scalar(
        select(RoomPresence).where(
            RoomPresence.room_id == room.id, RoomPresence.user_id == user.id
        )
    )
    now = utcnow()
    if presence is None:
        presence = RoomPresence(room_id=room.id, user_id=user.id)
        db.add(presence)
    presence.status = payload.status
    presence.subject_client_id = payload.subject_client_id or ""
    presence.subject_name = payload.subject_name or ""
    presence.activity_type = payload.activity_type or ""
    presence.mode = payload.mode or ""
    presence.focus_started_at = (
        payload.focus_started_at if payload.status == "focusing" else None
    )
    if payload.status == "focusing" and payload.focus_elapsed_sec is not None:
        presence.focus_started_at = (
            int(time.time() * 1000) - payload.focus_elapsed_sec * 1000
        )
    presence.last_heartbeat_at = now
    db.commit()
    return {"status": presence.status, "server_time": int(time.time() * 1000)}


def _message_dict(row, user_map, current_id):
    return {
        "id": row.id,
        "user_id": row.user_id,
        "nickname": user_map.get(row.user_id, "研友"),
        "content": row.content,
        "mine": row.user_id == current_id,
        "created_at": iso(row.created_at),
    }


def room_state(db, current_user, room=None, limit_messages=MESSAGE_LIMIT):
    room = room or get_default_room(db, current_user)
    guard_room_type(db, current_user, room)
    membership = db.scalar(
        select(RoomMember).where(
            RoomMember.room_id == room.id, RoomMember.user_id == current_user.id
        )
    )
    joined = membership is not None and (
        membership.sharing_confirmed or room.owner_id == current_user.id
    )
    if not joined:
        raise ApiError(403, 40301, "请凭房间邀请或房主审批加入；预览不包含成员学习数据")

    members = db.scalars(
        select(RoomMember)
        .where(
            RoomMember.room_id == room.id,
            RoomMember.sharing_confirmed.is_(True)
            | (RoomMember.user_id == room.owner_id),
        )
        .order_by(RoomMember.id)
    ).all()
    member_ids = [m.user_id for m in members]
    users = {
        u.id: u
        for u in db.scalars(
            select(User).where(User.id.in_(member_ids), User.status == "active")
        ).all()
    }
    presences = {
        p.user_id: p
        for p in db.scalars(
            select(RoomPresence).where(RoomPresence.room_id == room.id)
        ).all()
    }
    goals = {
        g.user_id: g
        for g in db.scalars(select(RoomGoal).where(RoomGoal.room_id == room.id)).all()
    }

    peer_ids = set(db.scalars(shared_user_ids(current_user.id, room.id)).all())
    readable_ids = [
        u.id
        for u in users.values()
        if u.id == current_user.id or (not u.is_private_mode and u.id in peer_ids)
    ]
    stats = _aggregate_sessions(db, readable_ids)
    today_str, _ = _cn_bounds()
    now = utcnow()
    now_ms = int(time.time() * 1000)

    member_payload = []
    rankable = []
    online_count = 0
    for m in members:
        u = users.get(m.user_id)
        if u is None:
            continue
        p = presences.get(m.user_id)
        online = bool(
            p
            and p.status != "offline"
            and (now - p.last_heartbeat_at).total_seconds() <= ONLINE_WINDOW_SEC
        )
        private = bool(u.is_private_mode)
        shared = u.id == current_user.id or u.id in peer_ids
        if online and (u.id == current_user.id or (not private and shared)):
            online_count += 1
        hide = u.id != current_user.id and (private or not shared)
        display_status = p.status if online else "offline"
        focus_sec = None
        if online and p and p.status == "focusing" and p.focus_started_at:
            focus_sec = min(max(now_ms - p.focus_started_at, 0) // 1000, MAX_FOCUS_SEC)
        agg = stats.get(
            m.user_id, {"today_sec": 0, "week_sec": 0, "total_sec": 0, "dates": set()}
        )
        g = goals.get(m.user_id)
        item = {
            "user_id": u.id,
            "nickname": u.nickname,
            "avatar_key": "" if hide else (u.avatar_key or ""),
            "figure_id": "figure-1" if hide else (u.figure_id or "figure-1"),
            "role": "owner" if u.id == room.owner_id else "member",
            "target_school": "" if hide else (u.target_school or ""),
            "exam_year": 0 if hide else u.exam_year,
            "online": False if hide else online,
            "privacy": private,
            "presence": {
                "status": "private" if hide else display_status,
                "subject_name": "" if hide else (p.subject_name if online else ""),
                "activity_type": "" if hide else (p.activity_type if online else ""),
                "mode": "" if hide else (p.mode if online else ""),
                "focus_started_at": None
                if hide
                else (
                    p.focus_started_at if online and p.status == "focusing" else None
                ),
                "focus_sec": None if hide else focus_sec,
            },
            "today_sec": None if hide else agg["today_sec"],
            "week_sec": None if hide else agg["week_sec"],
            "total_sec": None if hide else agg["total_sec"],
            "streak": None if hide else _streak(agg["dates"], today_str),
            "goal": None
            if hide or not g
            else {
                "target_school": g.target_school,
                "target_score": g.target_score,
                "words": g.words,
            },
        }
        if hide:
            for key in (
                "target_school",
                "exam_year",
                "today_sec",
                "week_sec",
                "total_sec",
                "streak",
                "goal",
            ):
                item.pop(key, None)
            item["presence"] = {"status": "private" if private else "unshared"}
        member_payload.append(item)
        if not hide and not private:
            rankable.append(item)

    ranking = {
        "today": sorted(
            ({"user_id": m["user_id"], "sec": m["today_sec"]} for m in rankable),
            key=lambda x: x["sec"],
            reverse=True,
        ),
        "week": sorted(
            ({"user_id": m["user_id"], "sec": m["week_sec"]} for m in rankable),
            key=lambda x: x["sec"],
            reverse=True,
        ),
        "all": sorted(
            ({"user_id": m["user_id"], "sec": m["total_sec"]} for m in rankable),
            key=lambda x: x["sec"],
            reverse=True,
        ),
    }

    messages = []
    if joined:
        messages = db.scalars(
            select(RoomMessage)
            .where(RoomMessage.room_id == room.id, RoomMessage.deleted_at.is_(None))
            .order_by(RoomMessage.created_at.desc())
            .limit(limit_messages)
        ).all()
    user_map = {uid: u.nickname for uid, u in users.items()}
    message_payload = [
        _message_dict(row, user_map, current_user.id) for row in reversed(messages)
    ]

    return {
        "room": room_summary(db, room, current_user, len(members), online_count),
        "joined": joined,
        "my_role": ("owner" if room.owner_id == current_user.id else "member")
        if membership
        else "",
        "members": member_payload,
        "ranking": ranking,
        "messages": message_payload,
    }


def add_message(db, user, content: str, room=None):
    room = room or get_default_room(db, user)
    require_member(db, user, room)
    row = RoomMessage(room_id=room.id, user_id=user.id, content=content[:500])
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "id": row.id,
        "user_id": row.user_id,
        "nickname": user.nickname,
        "content": row.content,
        "mine": True,
        "created_at": iso(row.created_at),
    }


def delete_message(db, user, message_id: int, is_admin: bool, room=None):
    room = room or get_default_room(db, user)
    row = db.get(RoomMessage, message_id)
    if not row or row.room_id != room.id or row.deleted_at:
        raise ApiError(404, 40401, "留言不存在")
    if row.user_id != user.id and not is_admin:
        raise ApiError(403, 40301, "只能删除自己的留言")
    row.deleted_at = utcnow()
    db.commit()
    return {"id": message_id}


def upsert_goal(db, user, payload, room=None):
    room = room or get_default_room(db, user)
    require_member(db, user, room)
    goal = db.scalar(
        select(RoomGoal).where(RoomGoal.room_id == room.id, RoomGoal.user_id == user.id)
    )
    if goal is None:
        goal = RoomGoal(room_id=room.id, user_id=user.id)
        db.add(goal)
    goal.target_school = payload.target_school or ""
    goal.target_score = payload.target_score or ""
    goal.words = payload.words or ""
    goal.updated_at = utcnow()
    db.commit()
    return {
        "target_school": goal.target_school,
        "target_score": goal.target_score,
        "words": goal.words,
    }


@room_write
def confirm_sharing(db, user, room):
    member = require_member(db, user, room)
    member.sharing_confirmed = True
    db.commit()
    return room_summary(db, room, user)
