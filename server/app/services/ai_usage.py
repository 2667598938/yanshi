"""跨进程持久化每日请求预算；失败尝试也占预算，避免失败重试绕过限额。"""

from datetime import timedelta
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from ..errors import ApiError
from ..models.ai import AIUsageDaily
from ..time import utcnow


def day_key():
    return (utcnow() + timedelta(hours=8)).date().isoformat()


def reserve(db, user_id, limit):
    day = day_key()
    if not db.get(AIUsageDaily, (user_id, day)):
        try:
            with db.begin_nested():
                db.add(AIUsageDaily(user_id=user_id, day=day))
                db.flush()
        except IntegrityError:
            pass
    changed = db.execute(
        update(AIUsageDaily)
        .where(
            AIUsageDaily.user_id == user_id,
            AIUsageDaily.day == day,
            AIUsageDaily.requests < limit,
        )
        .values(requests=AIUsageDaily.requests + 1)
    ).rowcount
    if changed != 1:
        db.rollback()
        raise ApiError(429, 42901, "今日 AI 请求额度已用完，次日北京时间零点重置")
    db.commit()
    return day


def finish(db, user_id, day, result=None):
    values = (
        {"failed": AIUsageDaily.failed + 1}
        if result is None
        else {
            "succeeded": AIUsageDaily.succeeded + 1,
            "prompt_tokens": AIUsageDaily.prompt_tokens
            + max(0, int(result.get("prompt_tokens") or 0)),
            "completion_tokens": AIUsageDaily.completion_tokens
            + max(0, int(result.get("completion_tokens") or 0)),
        }
    )
    db.execute(
        update(AIUsageDaily)
        .where(AIUsageDaily.user_id == user_id, AIUsageDaily.day == day)
        .values(**values)
    )
    db.commit()


def summary(db, user_id, limit):
    day = day_key()
    row = db.get(AIUsageDaily, (user_id, day))
    return {
        "day": day,
        "timezone": "Asia/Shanghai",
        "daily_limit": limit,
        "remaining": max(0, limit - (row.requests if row else 0)),
        **{
            key: getattr(row, key) if row else 0
            for key in (
                "requests",
                "succeeded",
                "failed",
                "prompt_tokens",
                "completion_tokens",
            )
        },
    }
