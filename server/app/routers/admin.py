"""后台管理接口（仅管理员）：概览、成员、邀请码、配置、公告、审计、数据导出。"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy import delete as sa_delete

from ..deps import audit, get_admin, get_db
from ..errors import ApiError, ok
from ..models import (
    AIConversation, AIMessage, Announcement, Attachment, Audit, Config, Invite,
    LearningOperation, LearningRecord, RefreshToken, Room, RoomGoal, RoomMember,
    RoomMessage, RoomPresence, User,
)
from ..schemas.account import (
    AdminCreateMember, AdminMemberUpdate, AdminResetPassword, AnnouncementInput,
    AnnouncementUpdate, InviteCreate,
)
from ..serializers import iso
from ..services import room as room_service
from ..services.security import hash_password, new_invite_code
from ..services.transient import digest
from ..time import utcnow

router = APIRouter(prefix='/api/v1/admin', tags=['admin'], dependencies=[Depends(get_admin)])


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
        'id': row.id, 'code': row.hint, 'remark': row.remark,
        'created_by': row.created_by, 'used_by': row.used_by,
        'used_at': iso(row.used_at), 'expires_at': iso(row.expires_at),
        'created_at': iso(row.created_at),
        'is_used': bool(row.used_at),
    }


def member_dict(row):
    return {
        'id': row.id, 'email': row.email, 'nickname': row.nickname, 'role': row.role,
        'status': row.status, 'target_school': row.target_school, 'exam_year': row.exam_year,
        'avatar_key': row.avatar_key or '', 'daily_goal_min': row.daily_goal_min,
        'created_at': iso(row.created_at), 'last_login_at': iso(row.last_login_at),
    }


# ---------------------------------------------------------------- 概览大盘
@router.get('/overview')
def overview(request: Request, db=Depends(get_db)):
    users = db.scalars(select(User).where(User.status != 'deleted')).all()
    member_ids = [u.id for u in users]
    room = db.scalar(select(Room).order_by(Room.id).limit(1))
    room_member_count = db.scalar(select(func.count()).select_from(RoomMember)) if room else 0

    # 在线（45 秒心跳）
    online_count = 0
    now = utcnow()
    if room:
        for p in db.scalars(select(RoomPresence).where(RoomPresence.room_id == room.id)).all():
            if p.status != 'offline' and (now - p.last_heartbeat_at).total_seconds() <= 45:
                online_count += 1

    # 学习时长聚合（实时从同步记录计算）
    stats = room_service._aggregate_sessions(db, member_ids)
    today_str, _ = room_service._cn_bounds()
    total_sec = sum(s['total_sec'] for s in stats.values())
    today_active = sum(1 for s in stats.values() if s['today_sec'] > 0)

    record_count = db.scalar(select(func.count()).select_from(LearningRecord))
    operation_count = db.scalar(select(func.count()).select_from(LearningOperation))
    conversation_count = db.scalar(select(func.count()).select_from(AIConversation))
    message_count = db.scalar(select(func.count()).select_from(RoomMessage).where(
        RoomMessage.deleted_at.is_(None)))
    attachment_bytes = db.scalar(select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
        Attachment.deleted_at.is_(None)))

    return ok({
        'member_count': len(users),
        'room_capacity': room.capacity if room else 0,
        'room_member_count': room_member_count,
        'online_count': online_count,
        'today_active': today_active,
        'total_focus_sec': total_sec,
        'today': today_str,
        'record_count': record_count,
        'operation_count': operation_count,
        'conversation_count': conversation_count,
        'message_count': message_count,
        'attachment_bytes': attachment_bytes or 0,
        'registration_open': config_get(db, 'registration_open', False),
        'site_name': config_get(db, 'site_name', '研时'),
        'exam_date': config_get(db, 'exam_date', '2027-12-25'),
        'exam_year': config_get(db, 'exam_year', 2028),
    })


# ---------------------------------------------------------------- 成员管理
@router.get('/members')
def list_members(db=Depends(get_db)):
    rows = db.scalars(select(User).where(User.status != 'deleted').order_by(User.id)).all()
    return ok([member_dict(u) for u in rows])


@router.post('/members')
def create_member(body: AdminCreateMember, request: Request, db=Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email)):
        raise ApiError(409, 40901, '该邮箱已被使用')
    room = room_service.get_default_room(db)
    count = db.scalar(select(func.count()).select_from(RoomMember).where(
        RoomMember.room_id == room.id))
    if count >= room.capacity:
        raise ApiError(403, 40301, '自习室已满（固定 4 人），不能再建号')
    user = User(email=body.email, nickname=body.nickname,
                password_hash=hash_password(body.password), role='member')
    db.add(user)
    db.flush()
    room_service.ensure_member(db, user, room)
    audit(db, request, 'admin.create_member', user_id=user.id, detail=body.email)
    db.commit()
    db.refresh(user)
    return ok(member_dict(user))


def _get_member(db, uid):
    user = db.get(User, uid)
    if not user or user.status == 'deleted':
        raise ApiError(404, 40401, '成员不存在')
    return user


@router.put('/members/{uid}')
def update_member(uid: int, body: AdminMemberUpdate, request: Request, db=Depends(get_db)):
    user = _get_member(db, uid)
    if body.nickname is not None:
        user.nickname = body.nickname
    if body.target_school is not None:
        user.target_school = body.target_school
    if body.daily_goal_min is not None:
        user.daily_goal_min = body.daily_goal_min
    if body.status is not None:
        if user.role == 'admin':
            raise ApiError(400, 40001, '不能封禁管理员')
        if user.status != body.status:
            user.status = body.status
            if body.status == 'banned':
                user.token_version += 1     # 强制下线
    audit(db, request, 'admin.update_member', user_id=uid, detail=body.model_dump_json())
    db.commit()
    db.refresh(user)
    return ok(member_dict(user))


@router.post('/members/{uid}/reset-password')
def reset_member_password(uid: int, body: AdminResetPassword, request: Request, db=Depends(get_db)):
    user = _get_member(db, uid)
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1                 # 旧 token 全部失效
    audit(db, request, 'admin.reset_password', user_id=uid)
    db.commit()
    return ok()


@router.delete('/members/{uid}')
def delete_member(uid: int, request: Request, db=Depends(get_db)):
    user = _get_member(db, uid)
    if user.role == 'admin':
        raise ApiError(400, 40001, '不能删除管理员')
    user.status = 'deleted'
    user.token_version += 1
    user.nickname = f'已注销用户{uid}'
    # 账号凭据 + 固定房间席位
    db.execute(sa_delete(RefreshToken).where(RefreshToken.user_id == uid))
    db.execute(sa_delete(RoomMember).where(RoomMember.user_id == uid))
    # 自习室痕迹：在线状态、目标墙、留言
    db.execute(sa_delete(RoomPresence).where(RoomPresence.user_id == uid))
    db.execute(sa_delete(RoomGoal).where(RoomGoal.user_id == uid))
    db.execute(sa_delete(RoomMessage).where(RoomMessage.user_id == uid))
    # 学习数据（同步记录 / 操作幂等表）
    db.execute(sa_delete(LearningRecord).where(LearningRecord.user_id == uid))
    db.execute(sa_delete(LearningOperation).where(LearningOperation.user_id == uid))
    # AI 会话与消息
    convo_ids = db.scalars(select(AIConversation.id).where(AIConversation.user_id == uid)).all()
    if convo_ids:
        db.execute(sa_delete(AIMessage).where(AIMessage.conversation_id.in_(convo_ids)))
    db.execute(sa_delete(AIConversation).where(AIConversation.user_id == uid))
    # 上传的附件记录（本地文件孤儿由备份/清理流程处理）
    db.execute(sa_delete(Attachment).where(Attachment.uploader_id == uid))
    audit(db, request, 'admin.delete_member', user_id=uid, detail=user.email)
    db.commit()
    return ok()


# ---------------------------------------------------------------- 邀请码
@router.get('/invites')
def list_invites(db=Depends(get_db)):
    rows = db.scalars(select(Invite).order_by(Invite.id.desc())).all()
    return ok([invite_dict(r) for r in rows])


@router.post('/invites')
def create_invite(body: InviteCreate, request: Request, db=Depends(get_db),
                  admin=Depends(get_admin)):
    code = new_invite_code()
    expires_at = None
    if body.expires_days:
        from datetime import timedelta
        expires_at = utcnow() + timedelta(days=body.expires_days)
    # 数据库只存哈希；hint 存明文便于管理员复制发给研友（邀请码非密码，本就是分享凭证）
    row = Invite(code_hash=digest(code.upper()), hint=code, remark=body.remark,
                 created_by=admin.id, expires_at=expires_at)
    db.add(row)
    audit(db, request, 'admin.create_invite', detail=code)
    db.commit()
    db.refresh(row)
    return ok(invite_dict(row))


@router.delete('/invites/{invite_id}')
def delete_invite(invite_id: int, request: Request, db=Depends(get_db)):
    row = db.get(Invite, invite_id)
    if not row:
        raise ApiError(404, 40401, '邀请码不存在')
    if row.used_at:
        raise ApiError(400, 40001, '已使用的邀请码不能删除')
    db.delete(row)
    audit(db, request, 'admin.delete_invite', detail=str(invite_id))
    db.commit()
    return ok()


# ---------------------------------------------------------------- 公告
@router.post('/announcements')
def create_announcement(body: AnnouncementInput, request: Request, db=Depends(get_db),
                        admin=Depends(get_admin)):
    row = Announcement(content=body.content, created_by=admin.id)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ok({'id': row.id, 'content': row.content, 'is_active': row.is_active,
               'created_at': iso(row.created_at)})


@router.put('/announcements/{ann_id}')
def update_announcement(ann_id: int, body: AnnouncementUpdate, request: Request,
                        db=Depends(get_db)):
    row = db.get(Announcement, ann_id)
    if not row:
        raise ApiError(404, 40401, '公告不存在')
    if body.content is not None:
        row.content = body.content
    if body.is_active is not None:
        row.is_active = body.is_active
    audit(db, request, 'admin.update_announcement', detail=str(ann_id))
    db.commit()
    return ok({'id': row.id, 'content': row.content, 'is_active': row.is_active})


@router.delete('/announcements/{ann_id}')
def delete_announcement(ann_id: int, request: Request, db=Depends(get_db)):
    row = db.get(Announcement, ann_id)
    if not row:
        raise ApiError(404, 40401, '公告不存在')
    db.delete(row)
    audit(db, request, 'admin.delete_announcement', detail=str(ann_id))
    db.commit()
    return ok()


@router.get('/announcements')
def list_announcements(db=Depends(get_db)):
    rows = db.scalars(select(Announcement).order_by(Announcement.id.desc()).limit(50)).all()
    return ok([{'id': r.id, 'content': r.content, 'is_active': r.is_active,
                'created_at': iso(r.created_at)} for r in rows])


# ---------------------------------------------------------------- 审计日志
@router.get('/audit-logs')
def audit_logs(limit: int = 100, db=Depends(get_db)):
    limit = min(max(limit, 1), 200)
    rows = db.scalars(select(Audit).order_by(Audit.id.desc()).limit(limit)).all()
    return ok([{'id': r.id, 'user_id': r.user_id, 'action': r.action, 'ip': r.ip,
                'detail': r.detail, 'created_at': iso(r.created_at)} for r in rows])


# ---------------------------------------------------------------- 站点配置
CONFIG_WHITELIST = {'site_name', 'exam_date', 'exam_year', 'registration_open'}


@router.put('/config')
def update_config(body: dict, request: Request, db=Depends(get_db), admin=Depends(get_admin)):
    changed = {}
    for key, value in body.items():
        if key not in CONFIG_WHITELIST:
            continue
        row = db.get(Config, key)
        if row is None:
            row = Config(config_key=key, config_value=json.dumps(value, ensure_ascii=False),
                         updated_by=admin.id)
            db.add(row)
        else:
            row.config_value = json.dumps(value, ensure_ascii=False)
            row.updated_by = admin.id
            row.updated_at = utcnow()
        changed[key] = value
    if not changed:
        raise ApiError(400, 40001, '没有可更新的配置项')
    audit(db, request, 'admin.update_config', detail=json.dumps(changed, ensure_ascii=False))
    db.commit()
    return ok(changed)


# ---------------------------------------------------------------- 全量数据导出（备份）
@router.get('/export')
def export_data(db=Depends(get_db)):
    users = [{'id': u.id, 'email': u.email, 'nickname': u.nickname, 'role': u.role,
              'status': u.status, 'target_school': u.target_school, 'exam_year': u.exam_year,
              'created_at': iso(u.created_at)}
             for u in db.scalars(select(User).order_by(User.id)).all()]
    records = [{'user_id': r.user_id, 'id': r.id, 'body': json.loads(r.body) if isinstance(r.body, str) else r.body,
                'revision': r.revision, 'deleted': r.deleted,
                'updated_at': iso(r.updated_at)}
               for r in db.scalars(select(LearningRecord)).all()]
    payload = {'exported_at': iso(utcnow()), 'users': users, 'records': records}
    return JSONResponse({'code': 0, 'message': 'ok', 'data': payload})
