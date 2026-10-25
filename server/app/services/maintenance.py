"""持久化邮件任务与VIP到期通知；业务事务提交后才有任务可被领取。"""
import secrets
from datetime import timedelta
from sqlalchemy import or_, select, update, case

from ..models import EmailJob, User, FeatureRequest
from ..time import utcnow
from .messages import create_message
from .transient import deliver


def enqueue_expiry_notifications(session_factory, settings):
    with session_factory() as db:
        users = db.scalars(select(User).where(User.status == 'active', User.vip_permanent.is_(False),
            User.vip_until.is_not(None), User.vip_until <= utcnow(),
            or_(User.vip_expiry_notified_until.is_(None), User.vip_expiry_notified_until != User.vip_until)).limit(100)).all()
        for user in users:
            db.execute(update(FeatureRequest).where(FeatureRequest.user_id == user.id,
                FeatureRequest.approval_source == 'vip', FeatureRequest.status == 'approved')
                .values(status='revoked', active_key=None))
            create_message(db, user, 'vip', 'VIP 已到期', 'VIP已到期；单独审批授权仍按其有效状态保留。', '/vip',
                dedupe_key=f'vip-expired:{user.id}:{user.vip_until.isoformat()}', email=True, settings=settings)
            user.vip_expiry_notified_until = user.vip_until
        db.commit()


def deliver_email_jobs(session_factory, settings, limit=20):
    now = utcnow()
    with session_factory() as db:
        # 进程中断的租约到期后重试，不让sending任务永久卡住。
        db.execute(update(EmailJob).where(EmailJob.status == 'sending',
            EmailJob.locked_at < now - timedelta(minutes=3)).values(
                status=case((EmailJob.attempts >= 5, 'failed'), else_='pending'), lease_token=None,
                last_error='发送进程中断，已按重试规则恢复'))
        ids = db.scalars(select(EmailJob.id).where(EmailJob.status.in_(['pending', 'retry']),
            EmailJob.next_attempt_at <= now, EmailJob.attempts < 5).order_by(EmailJob.id).limit(limit)).all()
        db.commit()
    for job_id in ids:
        lease = secrets.token_hex(16)
        with session_factory() as db:
            claimed = db.execute(update(EmailJob).where(EmailJob.id == job_id,
                EmailJob.status.in_(['pending', 'retry']), EmailJob.next_attempt_at <= now,
                EmailJob.attempts < 5).values(status='sending', lease_token=lease,
                    locked_at=now, attempts=EmailJob.attempts + 1)).rowcount
            db.commit()
            if claimed != 1: continue
            job = db.get(EmailJob, job_id)
            user = db.get(User, job.user_id)
            if not user or user.status == 'deleted':
                job.status = 'cancelled'; db.commit(); continue
            recipient, subject, content = job.recipient, job.subject, job.content
        error = None
        try: deliver(settings, recipient, subject, content)
        except Exception as exc: error = (getattr(exc, 'message', '') or type(exc).__name__)[:300]
        with session_factory() as db:
            job = db.scalar(select(EmailJob).where(EmailJob.id == job_id, EmailJob.lease_token == lease,
                EmailJob.status == 'sending').with_for_update())
            if not job: continue
            if error:
                job.status = 'failed' if job.attempts >= 5 else 'retry'
                job.last_error = error
                job.next_attempt_at = utcnow() + timedelta(seconds=min(3600, 60 * 2 ** (job.attempts - 1)))
            else:
                job.status, job.last_error, job.sent_at = 'sent', '', utcnow()
            job.lease_token = None
            db.commit()


def refresh_model_catalogs(session_factory, settings, secret):
    """每周领取一次目录刷新任务；失败保留旧目录，用户仍可24小时后按需拉取。"""
    import asyncio
    import hashlib
    import json
    from sqlalchemy.exc import IntegrityError
    from ..models import AIModelCache, UserAIKey, Config
    from . import ai, ai_key
    from .features import has_feature
    now = utcnow()
    with session_factory() as db:
        state = db.get(Config, 'ai:model-catalog-weekly')
        if state and state.updated_at > now - timedelta(days=7): return
        if state:
            previous = state.config_value
            claimed = db.execute(update(Config).where(Config.config_key == state.config_key,
                Config.config_value == previous).values(config_value=now.isoformat(), updated_at=now)).rowcount
            if not claimed: return
        else:
            db.add(Config(config_key='ai:model-catalog-weekly', config_value=now.isoformat(), updated_at=now))
        try: db.commit()
        except IntegrityError: db.rollback(); return
        ids = db.scalars(select(UserAIKey.user_id).order_by(UserAIKey.user_id)).all()
    for user_id in ids:
        with session_factory() as db:
            user, key = db.get(User, user_id), db.get(UserAIKey, user_id)
            if not user or user.status != 'active' or not key or not has_feature(db, user, 'ai'): continue
            try:
                plaintext = ai_key.decrypt(settings.ai_key_enc_secret or secret, key.key_cipher, str(user_id))
                base = key.base_url or ai.resolve_base_url(key.provider)
                cache_key = hashlib.sha256(f'{user_id}|{key.provider}|{base}|{plaintext}'.encode()).hexdigest()
                cached = db.get(AIModelCache, cache_key)
                if cached and cached.fetched_at > now - timedelta(days=7): continue
                items = asyncio.run(ai.fetch_models(base, plaintext))
                if not items: continue
                if cached: cached.models_json, cached.fetched_at = json.dumps(items), now
                else: db.add(AIModelCache(cache_key=cache_key, user_id=user_id,
                    models_json=json.dumps(items), fetched_at=now))
                db.commit()
            except Exception:
                db.rollback()  # Key或上游故障不能阻断邮件与其他用户的目录刷新。


def run_maintenance(session_factory, settings, secret=None):
    enqueue_expiry_notifications(session_factory, settings)
    deliver_email_jobs(session_factory, settings)
    if secret: refresh_model_catalogs(session_factory, settings, secret)
