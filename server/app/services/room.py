"""四人自习室领域服务：固定房间、成员、心跳在线、统计聚合、留言、目标墙。

排行榜数据直接从 learning_records 中 type=session 的记录实时聚合（不做日聚合表、不允许前端自报）；
在线 / 正在学由心跳维持（room_presence），与学习记录解耦。
"""
import json
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from ..errors import ApiError
from ..models import (
    LearningRecord, Room, RoomGoal, RoomMember, RoomMessage, RoomPresence, User,
)
from ..serializers import iso
from ..time import utcnow

# 中国时区固定 UTC+8（无夏令时），用固定偏移避免依赖系统时区库
CN = timezone(timedelta(hours=8))
ONLINE_WINDOW_SEC = 45          # 超过 45 秒无心跳视为离线
MAX_FOCUS_SEC = 6 * 3600        # 单次进行中专注展示上限
MESSAGE_LIMIT = 50


def get_default_room(db):
    room = db.scalar(select(Room).order_by(Room.id).limit(1))
    if room is None:
        raise ApiError(500, 50001, '自习室尚未初始化，请联系管理员')
    return room


def ensure_member(db, user, room=None, role='member', ignore_capacity=False):
    room = room or get_default_room(db)
    existing = db.scalar(select(RoomMember).where(
        RoomMember.room_id == room.id, RoomMember.user_id == user.id))
    if existing:
        return existing
    if not ignore_capacity:
        count = db.scalar(select(func.count()).select_from(RoomMember)
                          .where(RoomMember.room_id == room.id))
        if count >= room.capacity:
            raise ApiError(403, 40301, '自习室已满（固定 4 人）')
    member = RoomMember(room_id=room.id, user_id=user.id, role=role)
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
    """按成员聚合 session 时长：今日 / 本周 / 累计 / 连续打卡天数。"""
    today_str, monday_str = _cn_bounds()
    result = {
        uid: {'today_sec': 0, 'week_sec': 0, 'total_sec': 0, 'dates': set()}
        for uid in member_ids
    }
    if not member_ids:
        return result
    rows = db.scalars(select(LearningRecord).where(
        LearningRecord.user_id.in_(member_ids),
        LearningRecord.deleted == 0,
        func.json_extract(LearningRecord.body, '$.type') == 'session',
    )).all()
    for row in rows:
        try:
            body = json.loads(row.body)
        except ValueError:
            continue
        agg = result.get(row.user_id)
        if agg is None:
            continue
        sec = int(body.get('actualSec') or 0)
        day = body.get('date')
        agg['total_sec'] += sec
        if isinstance(day, str):
            if day >= monday_str:
                agg['week_sec'] += sec
            if day == today_str:
                agg['today_sec'] += sec
            agg['dates'].add(day)
    return result


def _streak(dates: set, today_str: str) -> int:
    today = datetime.strptime(today_str, '%Y-%m-%d').date()
    # 今天还没学则从昨天往前数，保持连续天数不中断
    cursor = today if today_str in dates else today - timedelta(days=1)
    streak = 0
    while cursor.isoformat() in dates:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def heartbeat(db, user, payload):
    room = get_default_room(db)
    ensure_member(db, user, room)
    presence = db.scalar(select(RoomPresence).where(
        RoomPresence.room_id == room.id, RoomPresence.user_id == user.id))
    now = utcnow()
    if presence is None:
        presence = RoomPresence(room_id=room.id, user_id=user.id)
        db.add(presence)
    presence.status = payload.status
    presence.subject_client_id = payload.subject_client_id or ''
    presence.subject_name = payload.subject_name or ''
    presence.activity_type = payload.activity_type or ''
    presence.mode = payload.mode or ''
    presence.focus_started_at = payload.focus_started_at if payload.status == 'focusing' else None
    presence.last_heartbeat_at = now
    db.commit()
    return {'status': presence.status, 'server_time': int(time.time() * 1000)}


def _message_dict(row, user_map, current_id):
    return {
        'id': row.id, 'user_id': row.user_id,
        'nickname': user_map.get(row.user_id, '研友'),
        'content': row.content, 'mine': row.user_id == current_id,
        'created_at': iso(row.created_at),
    }


def room_state(db, current_user, limit_messages=MESSAGE_LIMIT):
    room = get_default_room(db)
    ensure_member(db, current_user, room)

    members = db.scalars(
        select(RoomMember).where(RoomMember.room_id == room.id).order_by(RoomMember.id)
    ).all()
    member_ids = [m.user_id for m in members]
    users = {u.id: u for u in db.scalars(
        select(User).where(User.id.in_(member_ids), User.status != 'deleted')).all()}
    presences = {p.user_id: p for p in db.scalars(
        select(RoomPresence).where(RoomPresence.room_id == room.id)).all()}
    goals = {g.user_id: g for g in db.scalars(
        select(RoomGoal).where(RoomGoal.room_id == room.id)).all()}

    stats = _aggregate_sessions(db, member_ids)
    today_str, _ = _cn_bounds()
    now = utcnow()
    now_ms = int(time.time() * 1000)

    member_payload = []
    online_count = 0
    for m in members:
        u = users.get(m.user_id)
        if u is None:
            continue
        p = presences.get(m.user_id)
        online = bool(
            p and p.status != 'offline'
            and (now - p.last_heartbeat_at).total_seconds() <= ONLINE_WINDOW_SEC
        )
        if online:
            online_count += 1
        display_status = p.status if online else 'offline'
        focus_sec = None
        if online and p and p.status == 'focusing' and p.focus_started_at:
            focus_sec = min(max(now_ms - p.focus_started_at, 0) // 1000, MAX_FOCUS_SEC)
        agg = stats.get(m.user_id, {'today_sec': 0, 'week_sec': 0, 'total_sec': 0, 'dates': set()})
        g = goals.get(m.user_id)
        member_payload.append({
            'user_id': u.id, 'nickname': u.nickname, 'avatar_key': u.avatar_key or '',
            'role': m.role, 'target_school': u.target_school or '', 'exam_year': u.exam_year,
            'online': online,
            'presence': {
                'status': display_status,
                'subject_name': p.subject_name if online else '',
                'activity_type': p.activity_type if online else '',
                'mode': p.mode if online else '',
                'focus_started_at': p.focus_started_at if online and p.status == 'focusing' else None,
                'focus_sec': focus_sec,
            },
            'today_sec': agg['today_sec'], 'week_sec': agg['week_sec'],
            'total_sec': agg['total_sec'], 'streak': _streak(agg['dates'], today_str),
            'goal': None if not g else {
                'target_school': g.target_school, 'target_score': g.target_score, 'words': g.words,
            },
        })

    ranking = {
        'today': sorted(({'user_id': m['user_id'], 'sec': m['today_sec']} for m in member_payload),
                        key=lambda x: x['sec'], reverse=True),
        'week': sorted(({'user_id': m['user_id'], 'sec': m['week_sec']} for m in member_payload),
                       key=lambda x: x['sec'], reverse=True),
        'all': sorted(({'user_id': m['user_id'], 'sec': m['total_sec']} for m in member_payload),
                      key=lambda x: x['sec'], reverse=True),
    }

    messages = db.scalars(
        select(RoomMessage).where(
            RoomMessage.room_id == room.id, RoomMessage.deleted_at.is_(None))
        .order_by(RoomMessage.created_at.desc()).limit(limit_messages)
    ).all()
    user_map = {uid: u.nickname for uid, u in users.items()}
    message_payload = [_message_dict(row, user_map, current_user.id) for row in reversed(messages)]

    return {
        'room': {
            'id': room.id, 'name': room.name, 'intro': room.intro, 'code': room.code,
            'capacity': room.capacity, 'member_count': len(member_payload),
            'online_count': online_count,
        },
        'members': member_payload,
        'ranking': ranking,
        'messages': message_payload,
    }


def add_message(db, user, content: str):
    room = get_default_room(db)
    ensure_member(db, user, room)
    row = RoomMessage(room_id=room.id, user_id=user.id, content=content[:500])
    db.add(row)
    db.commit()
    db.refresh(row)
    return {'id': row.id, 'user_id': row.user_id, 'nickname': user.nickname,
            'content': row.content, 'mine': True, 'created_at': iso(row.created_at)}


def delete_message(db, user, message_id: int, is_admin: bool):
    room = get_default_room(db)
    row = db.get(RoomMessage, message_id)
    if not row or row.room_id != room.id or row.deleted_at:
        raise ApiError(404, 40401, '留言不存在')
    if row.user_id != user.id and not is_admin:
        raise ApiError(403, 40301, '只能删除自己的留言')
    row.deleted_at = utcnow()
    db.commit()
    return {'id': message_id}


def upsert_goal(db, user, payload):
    room = get_default_room(db)
    ensure_member(db, user, room)
    goal = db.scalar(select(RoomGoal).where(
        RoomGoal.room_id == room.id, RoomGoal.user_id == user.id))
    if goal is None:
        goal = RoomGoal(room_id=room.id, user_id=user.id)
        db.add(goal)
    goal.target_school = payload.target_school or ''
    goal.target_score = payload.target_score or ''
    goal.words = payload.words or ''
    goal.updated_at = utcnow()
    db.commit()
    return {'target_school': goal.target_school, 'target_score': goal.target_score,
            'words': goal.words}
