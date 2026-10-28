"""Owner-only global timer lease and explicit resolution of overlapping history."""

import json, hashlib
from datetime import timedelta, timezone
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from ..deps import get_current_user, get_db, audit
from ..models import TimerLease, LearningRecord, SessionFact
from ..errors import ApiError, ok
from ..time import utcnow
from ..serializers import iso
from ..schemas.session import MIN_START_MS
from ..services.write_guard import account_write
from ..services.session_records import display_record
from ..services.sync import execute_commands

router = APIRouter(prefix="/api/v1/timer", tags=["timer"])


class LeaseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(min_length=1, max_length=100)
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")
    started_at: int = Field(ge=MIN_START_MS, strict=True)
    label: str = Field(default="", max_length=100)


def lease_payload(row):
    return {
        "session_id": row.session_id,
        "device_id": row.device_id,
        "started_at": row.started_at,
        "label": json.loads(row.detail).get("label", ""),
        "expires_at": iso(row.expires_at),
    }


@router.get("/current")
def current(user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(TimerLease, user.id)
    return ok(lease_payload(row) if row and row.expires_at > utcnow() else None)


@router.post("/start")
def start(
    body: LeaseInput,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    with account_write(db, user.id):
        now = utcnow()
        row = db.scalar(
            select(TimerLease)
            .where(TimerLease.user_id == user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            body.started_at
            > int(now.replace(tzinfo=timezone.utc).timestamp() * 1000) + 300000
        ):
            raise ApiError(422, 42201, "开始时间不能在未来")
        if (
            row
            and row.expires_at > now
            and (row.device_id != body.device_id or row.session_id != body.session_id)
        ):
            raise ApiError(
                409,
                40920,
                "该账号已有主计时设备，当前设备仅可查看",
                data={"current": lease_payload(row)},
            )
        if db.get(LearningRecord, (user.id, body.session_id)):
            raise ApiError(409, 40920, "这轮计时已经结算，不能重新启动")
        if not row:
            row = TimerLease(user_id=user.id)
            db.add(row)
        row.session_id = body.session_id
        row.device_id = body.device_id
        row.started_at = body.started_at
        row.detail = json.dumps({"label": body.label})
        row.expires_at = now + timedelta(seconds=120)
        db.commit()
        return ok(lease_payload(row))


@router.put("/heartbeat")
def heartbeat(body: LeaseInput, user=Depends(get_current_user), db=Depends(get_db)):
    with account_write(db, user.id):
        row = db.scalar(
            select(TimerLease)
            .where(TimerLease.user_id == user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            not row
            or row.expires_at <= utcnow()
            or row.session_id != body.session_id
            or row.device_id != body.device_id
            or row.started_at != body.started_at
        ):
            raise ApiError(409, 40920, "主计时租约已失效，请查看当前设备状态")
        row.expires_at = utcnow() + timedelta(seconds=120)
        db.commit()
        return ok(lease_payload(row))


@router.post("/release")
def release(body: LeaseInput, user=Depends(get_current_user), db=Depends(get_db)):
    with account_write(db, user.id):
        row = db.scalar(
            select(TimerLease)
            .where(TimerLease.user_id == user.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            row
            and row.session_id == body.session_id
            and row.device_id == body.device_id
        ):
            db.delete(row)
        db.commit()
        return ok()


def conflict_groups(db, uid, lock=False):
    query = (
        select(SessionFact)
        .where(SessionFact.user_id == uid, SessionFact.conflict.is_(True))
        .order_by(SessionFact.started_at, SessionFact.record_id)
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    rows = db.scalars(query).all()
    groups = []
    component = []
    end = 0

    def save():
        if component:
            items = []
            for f in component:
                row = db.get(LearningRecord, (uid, f.record_id))
                if row and not row.deleted:
                    items.append(
                        {
                            "id": row.id,
                            "revision": row.revision,
                            "started_at": f.started_at,
                            "ended_at": f.ended_at,
                            "seconds": f.actual_sec,
                        }
                    )
            if len(items) > 1:
                groups.append(
                    {
                        "id": hashlib.sha256(
                            "|".join(sorted(i["id"] for i in items)).encode()
                        ).hexdigest()[:24],
                        "items": items,
                    }
                )

    for f in rows:
        if component and f.started_at >= end:
            save()
            component = []
            end = 0
        component.append(f)
        end = max(end, f.ended_at)
    save()
    return groups


@router.get("/conflicts")
def conflicts(user=Depends(get_current_user), db=Depends(get_db)):
    invalid = []
    for row in db.scalars(
        select(LearningRecord).where(
            LearningRecord.user_id == user.id, LearningRecord.deleted == 0
        )
    ).all():
        record = json.loads(row.body)
        if record.get("type") == "session" and display_record(db, user.id, record).get(
            "validation_issue"
        ):
            invalid.append(
                {
                    "id": row.id,
                    "revision": row.revision,
                    "reason": "历史计时不符合当前时间校验，已排除统计",
                }
            )
    return ok({"groups": conflict_groups(db, user.id), "invalid": invalid})


class ResolveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    group_id: str
    keep_id: str | None = None
    keep_ids: list[str] | None = Field(default=None, max_length=200)
    versions: dict[str, int] = Field(max_length=20000)
    confirmed: bool = Field(strict=True)


@router.post("/resolve")
def resolve(
    body: ResolveInput,
    request: Request,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    if not body.confirmed:
        raise ApiError(400, 40001, "请先确认保留及删除条目")
    keep_ids = body.keep_ids or ([body.keep_id] if body.keep_id else [])
    if not keep_ids:
        raise ApiError(400, 40001, "请选择要保留的记录")
    if len(set(keep_ids)) != len(keep_ids):
        raise ApiError(400, 40001, "保留记录不能重复")
    with account_write(db, user.id):
        group = next(
            (g for g in conflict_groups(db, user.id, True) if g["id"] == body.group_id),
            None,
        )
        if (
            not group
            or body.versions != {i["id"]: i["revision"] for i in group["items"]}
            or any(i not in body.versions for i in keep_ids)
        ):
            raise ApiError(409, 40902, "冲突记录已经变化，请刷新后处理")
        kept = [i for i in group["items"] if i["id"] in keep_ids]
        if len(kept) != len(keep_ids):
            raise ApiError(409, 40902, "保留记录不存在，请刷新后处理")
        kept.sort(key=lambda i: (i["started_at"], i["id"]))
        for prev, current in zip(kept, kept[1:]):
            if prev["ended_at"] > current["started_at"]:
                raise ApiError(400, 40001, "所选保留记录仍互相重叠，请放弃至少一条")
        changes = [
            {"id": i["id"], "expectedRevision": i["revision"], "record": None}
            for i in group["items"]
            if i["id"] not in keep_ids
        ]
        if not changes:
            raise ApiError(400, 40001, "请至少放弃一条冲突记录")

        def log(_):
            audit(
                db,
                request,
                "timer.resolve_overlap",
                user_id=user.id,
                detail=json.dumps(
                    {"keep": keep_ids, "deleted": [c["id"] for c in changes]}
                ),
            )

        execute_commands(
            db,
            user.id,
            {
                "operationId": "overlap-"
                + body.group_id
                + "-"
                + str(max(body.versions.values()))
                + "-"
                + ",".join(sorted(keep_ids)),
                "changes": changes,
            },
            before_commit=log,
        )
        return ok({"deleted": len(changes), "kept": keep_ids})
