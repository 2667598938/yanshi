"""站内消息服务：落库 + 可选邮件双通道，dedupe_key 防重复通知。"""
from sqlalchemy import select

from ..models import Message
from ..services.transient import deliver


def create_message(db, user, kind, title, content, link='', dedupe_key=None,
                   email=False, settings=None):
    if dedupe_key:
        exists = db.scalar(select(Message.id).where(
            Message.user_id == user.id, Message.dedupe_key == dedupe_key))
        if exists:
            return None
    row = Message(user_id=user.id, kind=kind, title=title[:80],
                  content=(content or '')[:500], link=(link or '')[:200],
                  dedupe_key=dedupe_key)
    db.add(row)
    if email and settings and user.email:
        try:
            deliver(settings, user.email, '研时 · ' + title, content)
        except Exception:
            # 邮件失败不应阻断业务事务，站内消息已落库
            pass
    return row


def message_dict(row):
    from ..serializers import iso
    return {
        'id': row.id, 'kind': row.kind, 'title': row.title, 'content': row.content,
        'link': row.link or '', 'is_read': bool(row.is_read),
        'created_at': iso(row.created_at),
    }
