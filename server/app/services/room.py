"""多房间自习室领域服务：准入、成员、心跳在线、统计聚合、留言、目标墙。

排行榜数据直接从 learning_records 中 type=session 的记录实时聚合（不做日聚合表、不允许前端自报）；
在线 / 正在学由心跳维持（room_presence），与学习记录解耦。
"""

import json
from .group import shared_user_ids, same_group
from .presence import WINDOW as ONLINE_WINDOW_SEC
from .session_records import display_record
import secrets
import string
import time
import threading
from functools import wraps
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

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
MAX_FOCUS_SEC = 6 * 3600  # 单次进行中专注展示上限
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
    if not settings and room.room_type == "checkin_room":
        return
    if not settings or room.room_type not in settings.enabled_features:
        raise ApiError(403, 40310, "该房间类型暂未开放")
    if user and room.room_type != "checkin_room":
        from .features import require_feature

        require_feature(db, user, "room", "该房间类型需要VIP或房间审批授权")


def get_default_room(db):
    room = db.scalar(
        select(Room)
        .where(Room.dissolved_at.is_(None), Room.room_type == "checkin_room")
        .order_by(Room.id)
        .limit(1)
    )
    if room is None:
        raise ApiError(500, 50001, "自习室尚未初始化，请联系管理员")
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
    if member is None:
        raise ApiError(403, 40301, "请先加入自习室")
    return member


def _new_room_code(db):
    alphabet = string.ascii_uppercase + string.digits
    for _ in range(50):
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if not db.scalar(select(Room.id).where(Room.code == code)):
            return code
    raise ApiError(500, 50001, "房间码生成失败，请重试")


def room_summary(db, room, user, member_count=None, online_count=None):
    membership = get_membership(db, room.id, user.id)
    if member_count is None:
        member_count = (
            db.scalar(
                select(func.count())
                .select_from(RoomMember)
                .where(RoomMember.room_id == room.id)
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
                            & User.id.in_(shared_user_ids(user.id))
                        )
                    ),
                    RoomPresence.room_id == room.id,
                    RoomPresence.status != "offline",
                    RoomPresence.last_heartbeat_at >= cutoff,
                )
            )
            or 0
        )
    owner = db.get(User, room.owner_id) if room.owner_id else None
    data = {
        "id": room.id,
        "name": room.name,
        "intro": room.intro or "",
        "visibility": room.visibility,
        "capacity": room.capacity,
        "room_type": room.room_type,
        "member_count": int(member_count),
        "online_count": int(online_count),
        "joined": membership is not None,
        "my_role": membership.role if membership else "",
        "owner": {"id": owner.id, "nickname": owner.nickname} if owner else None,
        "created_at": iso(room.created_at),
    }
    # 房间码只给成员看；私密房间未加入者走预览接口，仅返回公开信息
    data["code"] = room.code if membership else ""
    return data


def list_rooms(db, user):
    member_room_ids = set(
        db.scalars(
            select(RoomMember.room_id).where(RoomMember.user_id == user.id)
        ).all()
    )
    rooms = db.scalars(
        select(Room).where(Room.dissolved_at.is_(None)).order_by(Room.id)
    ).all()
    settings = db.info.get("settings")
    enabled = settings.enabled_features if settings else ["checkin_room"]
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
            .where(RoomMember.room_id.in_(ids))
            .group_by(RoomMember.room_id)
        ).all()
    )
    cutoff = utcnow() - timedelta(seconds=ONLINE_WINDOW_SEC)
    online = dict(
        db.execute(
            select(RoomPresence.room_id, func.count())
            .join(User, User.id == RoomPresence.user_id)
            .where(
                (
                    (User.id == user.id)
                    | (
                        (User.is_private_mode == False)
                        & User.id.in_(shared_user_ids(user.id))
                    )
                ),
                RoomPresence.room_id.in_(ids),
                RoomPresence.status != "offline",
                RoomPresence.last_heartbeat_at >= cutoff,
            )
            .group_by(RoomPresence.room_id)
        ).all()
    )
    return [
        room_summary(db, r, user, counts.get(r.id, 0), online.get(r.id, 0))
        for r in visible
    ]


@room_write
def create_room(db, user, name, intro, visibility, room_type="checkin_room"):
    room = Room(
        name=name.strip(),
        intro=(intro or "").strip(),
        code=_new_room_code(db),
        owner_id=user.id,
        capacity=4,
        visibility=visibility,
        room_type=room_type,
    )
    guard_room_type(db, user, room)
    db.add(room)
    db.flush()
    db.add(RoomMember(room_id=room.id, user_id=user.id, role="owner"))
    db.commit()
    db.refresh(room)
    return room


@room_write
def join_room(db, user, room, code=""):
    if room.visibility == "private":
        if code.strip().upper() != room.code.upper():
            raise ApiError(403, 40301, "房间码不正确")
    ensure_member(db, user, room)
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
    """私密房间未加入也可看房间公开信息与自己的申请状态，成员数据仍不可见。"""
    membership = get_membership(db, room.id, user.id)
    apply_row = latest_apply(db, room.id, user.id)
    return {
        "room": room_summary(db, room, user),
        "joined": membership is not None,
        "my_role": membership.role if membership else "",
        "join_required": room.visibility == "private" and membership is None,
        "apply": _apply_dict(apply_row) if apply_row else None,
    }


@room_write
def apply_join(db, user, room, message=""):
    """私密房间凭码免审；无码陌生人提交申请，同一人只保留一条待审。"""
    if get_membership(db, room.id, user.id):
        raise ApiError(400, 40001, "你已经在这个自习室")
    if room.visibility != "private":
        raise ApiError(400, 40001, "公开自习室可以直接加入")
    member_count = (
        db.scalar(
            select(func.count())
            .select_from(RoomMember)
            .where(RoomMember.room_id == room.id)
        )
        or 0
    )
    if member_count >= room.capacity:
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
        return _apply_dict(pending)
    row = RoomJoinApply(
        room_id=room.id,
        user_id=user.id,
        status="pending",
        message=(message or "")[:200],
        pending_key=f"{room.id}-{user.id}",
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
    if room.owner_id != user.id and user.role != "admin":
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
    if room.owner_id != user.id and user.role != "admin":
        raise ApiError(403, 40301, "只有房主可以审批入房申请")
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
    if approve and get_membership(db, room.id, row.user_id) is None:
        # 满员直接抛 403，pending 状态保持，房主可稍后再处理
        ensure_member(db, applicant, room)
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
    if member.role == "owner":
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
    if room.owner_id != user.id and user.role != "admin":
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
    if room.owner_id != user.id and user.role != "admin":
        raise ApiError(403, 40301, "只有房主可以移除成员")
    target = get_membership(db, room.id, target_user_id)
    if target is None:
        raise ApiError(404, 40401, "该成员不在房间内")
    if target_user_id == room.owner_id:
        raise ApiError(400, 40001, "不能移除房主")
    db.delete(target)
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
    if room.owner_id != user.id and user.role != "admin":
        raise ApiError(403, 40301, "只有房主可以更换房间码")
    room.code = _new_room_code(db)
    db.commit()
    return room_summary(db, room, user)


@room_write
def dissolve_room(db, user, room):
    if room.owner_id != user.id and user.role != "admin":
        raise ApiError(403, 40301, "只有房主可以解散房间")
    if room.id == get_default_room(db).id:
        raise ApiError(400, 40001, "默认自习室不能解散")
    room.dissolved_at = utcnow()
    db.execute(delete_room_members(room.id))
    db.commit()
    return {"dissolved": True}


def delete_room_members(room_id):
    from sqlalchemy import delete

    return delete(RoomMember).where(RoomMember.room_id == room_id)


def ensure_member(db, user, room=None, role="member", ignore_capacity=False):
    room = room or get_default_room(db)
    guard_room_type(db, user, room)
    db.refresh(room, with_for_update=True)
    existing = db.scalar(
        select(RoomMember)
        .where(RoomMember.room_id == room.id, RoomMember.user_id == user.id)
        .with_for_update()
    )
    if existing:
        return existing
    if not ignore_capacity:
        count = len(
            db.scalars(
                select(RoomMember.id)
                .where(RoomMember.room_id == room.id)
                .with_for_update()
            ).all()
        )
        if count >= room.capacity:
            raise ApiError(403, 40301, "自习室已满（固定 4 人）")
    member = RoomMember(room_id=room.id, user_id=user.id, role=role)
    db.add(member)
    db.flush()
    return member


def join_room_quietly(db, user):
    """开放注册后房间可能已满：账号照常创建，但不强制占位。"""
    try:
        ensure_member(db, user)
    except ApiError:
        pass


def _cn_bounds():
    """返回中国时区的今天、本周一（YYYY-MM-DD 字符串）。"""
    now = datetime.now(CN)
    today = now.date()
    monday = today - timedelta(days=today.weekday())
    return today.isoformat(), monday.isoformat()


def _aggregate_sessions(db, member_ids):
    """按成员聚合 session 时长：今日 / 本周 / 累计 / 连续打卡天数。"""
    today_str, monday_str = _cn_bounds()
    result = {
        uid: {"today_sec": 0, "week_sec": 0, "total_sec": 0, "dates": set()}
        for uid in member_ids
    }
    if not member_ids:
        return result
    rows = db.scalars(
        select(LearningRecord).where(
            LearningRecord.user_id.in_(member_ids),
            LearningRecord.deleted == 0,
            func.json_extract(LearningRecord.body, "$.type") == "session",
        )
    ).all()
    for row in rows:
        try:
            body = display_record(db, row.user_id, json.loads(row.body))
        except ValueError:
            continue
        agg = result.get(row.user_id)
        if agg is None:
            continue
        if body.get("conflict_flag") or body.get("validation_issue"):
            continue
        sec = int(body.get("actualSec") or 0)
        day = body.get("date")
        agg["total_sec"] += sec
        if isinstance(day, str):
            if monday_str <= day <= today_str:
                agg["week_sec"] += sec
            if day == today_str:
                agg["today_sec"] += sec
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
    room = room or get_default_room(db)
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
    room = room or get_default_room(db)
    guard_room_type(db, current_user, room)
    membership = db.scalar(
        select(RoomMember).where(
            RoomMember.room_id == room.id, RoomMember.user_id == current_user.id
        )
    )
    joined = membership is not None
    if room.visibility == "private" and not joined:
        raise ApiError(403, 40301, "私密自习室，请输入房间码加入")

    members = db.scalars(
        select(RoomMember).where(RoomMember.room_id == room.id).order_by(RoomMember.id)
    ).all()
    member_ids = [m.user_id for m in members]
    users = {
        u.id: u
        for u in db.scalars(
            select(User).where(User.id.in_(member_ids), User.status != "deleted")
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

    stats = _aggregate_sessions(db, member_ids)
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
        if online and (
            u.id == current_user.id
            or (not u.is_private_mode and same_group(db, current_user.id, u.id))
        ):
            online_count += 1
        private = bool(u.is_private_mode)
        hide = u.id != current_user.id and (
            private or not same_group(db, current_user.id, u.id)
        )
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
            "role": m.role,
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
        "room": room_summary(db, room, current_user, len(member_payload), online_count),
        "joined": joined,
        "my_role": membership.role if membership else "",
        "members": member_payload,
        "ranking": ranking,
        "messages": message_payload,
    }


def add_message(db, user, content: str, room=None):
    room = room or get_default_room(db)
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
    room = room or get_default_room(db)
    row = db.get(RoomMessage, message_id)
    if not row or row.room_id != room.id or row.deleted_at:
        raise ApiError(404, 40401, "留言不存在")
    if row.user_id != user.id and not is_admin:
        raise ApiError(403, 40301, "只能删除自己的留言")
    row.deleted_at = utcnow()
    db.commit()
    return {"id": message_id}


def upsert_goal(db, user, payload, room=None):
    room = room or get_default_room(db)
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
