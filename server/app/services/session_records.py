"""Validated session projection and conservative interval conflict detection."""

import json
from sqlalchemy import select
from ..models import SessionFact, LearningRecord, LearningChange
from ..schemas.session import normalize_session


def display_record(db, uid, record):
    if not record or record.get("type") != "session":
        return record
    try:
        clean = normalize_session(record)
    except (ValueError, TypeError, OverflowError):
        return {
            **record,
            "actualSec": 0,
            "validation_issue": "历史计时缺少合法起止时间，暂不计入统计",
            "conflict_flag": True,
        }
    fact = db.get(SessionFact, (uid, record["id"]))
    if fact and fact.conflict:
        clean.update(
            conflict_flag=True, conflict_duration_sec=clean["actualSec"], actualSec=0
        )
    else:
        clean["conflict_flag"] = False
    return clean


def refresh_facts(db, uid, primary_ids=()):
    rows = db.scalars(
        select(LearningRecord)
        .where(LearningRecord.user_id == uid, LearningRecord.deleted == 0)
        .with_for_update()
        .execution_options(populate_existing=True)
    ).all()
    sessions = {r.id: r for r in rows if json.loads(r.body).get("type") == "session"}
    facts = {
        f.record_id: f
        for f in db.scalars(
            select(SessionFact)
            .where(SessionFact.user_id == uid)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
    }
    previous = {key: bool(f.conflict) for key, f in facts.items()}
    valid = []
    for key, row in sessions.items():
        try:
            record = normalize_session(json.loads(row.body))
        except (ValueError, TypeError, OverflowError):
            continue
        f = facts.get(key)
        if not f:
            f = SessionFact(user_id=uid, record_id=key)
            db.add(f)
        f.started_at = record["startedAt"]
        f.ended_at = record["endedAt"]
        f.actual_sec = record["actualSec"]
        f.study_date = record["date"]
        f.conflict = False
        valid.append(f)
    ids = {f.record_id for f in valid}
    for key, f in facts.items():
        if key not in ids:
            db.delete(f)
    # Half-open intervals; adjacent intervals and zero effective durations do not conflict.
    component = []
    end = 0

    def flag():
        if len(component) > 1:
            for item in component:
                item.conflict = True

    for f in sorted(
        (f for f in valid if f.actual_sec > 0 and f.ended_at > f.started_at),
        key=lambda f: (f.started_at, f.record_id),
    ):
        if component and f.started_at >= end:
            flag()
            component = []
            end = 0
        component.append(f)
        end = max(end, f.ended_at)
    flag()
    for f in valid:
        if (
            bool(f.conflict) != previous.get(f.record_id, False)
            and f.record_id not in primary_ids
        ):
            row = sessions[f.record_id]
            row.revision += 1
            db.add(
                LearningChange(
                    user_id=uid,
                    record_id=row.id,
                    revision=row.revision,
                    record_type="session",
                )
            )
    db.flush()
