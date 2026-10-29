"""站内消息服务：落库 + 可选邮件双通道，dedupe_key 防重复通知。"""
from sqlalchemy import select

from ..models import Message, EmailJob
from ..time import utcnow


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
        db.flush()
        db.add(EmailJob(user_id=user.id, message_id=row.id, recipient=user.email,
                        subject=('研时 · ' + title)[:160], content=content or '',
                        status='pending', next_attempt_at=utcnow()))
    return row


def message_dict(row):
    from ..serializers import iso
    return {
        'id': row.id, 'kind': row.kind, 'title': row.title, 'content': row.content,
        'link': row.link or '', 'is_read': bool(row.is_read),
        'created_at': iso(row.created_at),
    }
