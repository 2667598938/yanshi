"""受邀或审批入房并确认共享的成员构成好友小组；不同房间相互隔离。"""

import json
from sqlalchemy import select, func
from ..models import User, LearningRecord, LearningChange
from ..errors import ApiError
from .session_records import display_records


def shared_user_ids(viewer_id, room_id=None):
    """A direct, confirmed membership in a live room is the sole sharing boundary.

    Legacy StudyGroupMember rows never grant access. Room membership is not
    transitive: a friend's other roommates do not become the viewer's friends.
    """
    from ..models import Room, RoomMember

    rooms = (
        select(RoomMember.room_id)
        .join(Room, Room.id == RoomMember.room_id)
        .where(
            RoomMember.user_id == viewer_id,
            RoomMember.sharing_confirmed.is_(True),
            Room.dissolved_at.is_(None),
        )
    )
    if room_id is not None:
        rooms = rooms.where(Room.id == room_id)
    return (
        select(RoomMember.user_id)
        .where(
            RoomMember.room_id.in_(rooms),
            RoomMember.sharing_confirmed.is_(True),
        )
        .distinct()
    )


def same_group(db, viewer_id, owner_id):
    return (
        db.scalar(
            select(User.id)
            .where(
                User.id == owner_id,
                User.id.in_(shared_user_ids(viewer_id)),
            )
            .limit(1)
        )
        is not None
    )


def can_read(db, viewer, owner):
    return bool(
        owner
        and owner.status == "active"
        and (
            viewer.id == owner.id
            or (not owner.is_private_mode and same_group(db, viewer.id, owner.id))
        )
    )


def require_read(db, viewer, owner_id):
    owner = db.get(User, owner_id)
    if not can_read(db, viewer, owner):
        raise ApiError(404, 40401, "学习数据不可见")
    return owner


FIELDS = {
    "subject": {"id", "name", "color", "icon", "tags", "order", "archived"},
    "session": {
        "id",
        "subjectId",
        "mode",
        "activityType",
        "content",
        "learningContent",
        "actualSec",
        "status",
        "date",
        "startedAt",
        "endedAt",
        "plannedMin",
        "conflict_flag",
        "validation_issue",
    },
    "task": {
        "id",
        "title",
        "subjectId",
        "phase",
        "acceptCriteria",
        "dueDate",
        "estimatedMin",
        "done",
        "doneAt",
        "createdAt",
    },
    "mistake": {
        "id",
        "subjectId",
        "content",
        "idea",
        "analysis",
        "reason",
        "tags",
        "images",
        "answerImages",
        "stage",
        "mastered",
        "nextReviewAt",
        "chapter",
        "sessionId",
        "sourceDate",
        "history",
        "createdAt",
        "updatedAt",
    },
}


def project(record):
    kind = record.get("type")
    return {
        "type": kind,
        **{k: v for k, v in record.items() if k in FIELDS.get(kind, set())},
    }


def shared_records(db, viewer, owner_id, after="", kind=None):
    require_read(db, viewer, owner_id)
    query = select(LearningRecord).where(
        LearningRecord.user_id == owner_id,
        LearningRecord.deleted == 0,
        LearningRecord.id > after,
        func.json_extract(LearningRecord.body, "$.type").in_(FIELDS),
    )
    if kind:
        query = query.where(func.json_extract(LearningRecord.body, "$.type") == kind)
    cursor = (
        db.scalar(
            select(func.max(LearningChange.id)).where(
                LearningChange.user_id == owner_id
            )
        )
        or 0
    )
    rows = db.scalars(query.order_by(LearningRecord.id).limit(200)).all()
    return {
        "items": [
            project(record)
            for record in display_records(
                db, owner_id, [json.loads(row.body) for row in rows]
            )
        ],
        "next": rows[-1].id if len(rows) == 200 else None,
        "cursor": cursor,
    }


def shared_changes(db, viewer, owner_id, since):
    """Account-scoped monotonic log, including deletions. Recheck ACL on every page.

    Client retains the FIRST snapshot-page cursor and replays subsequent changes;
    writes/deletions during snapshot pagination are therefore never lost.
    Non-shared changes advance the cursor but never expose record identifiers.
    """
    require_read(db, viewer, owner_id)
    changes = db.scalars(
        select(LearningChange)
        .where(LearningChange.user_id == owner_id, LearningChange.id > since)
        .order_by(LearningChange.id)
        .limit(200)
    ).all()
    public_ids = {c.record_id for c in changes if c.record_type in FIELDS}
    rows = (
        {
            row.id: row
            for row in db.scalars(
                select(LearningRecord).where(
                    LearningRecord.user_id == owner_id,
                    LearningRecord.id.in_(public_ids),
                )
            ).all()
        }
        if public_ids
        else {}
    )
    bodies = [json.loads(row.body) for row in rows.values() if not row.deleted]
    displayed = {r["id"]: r for r in display_records(db, owner_id, bodies) if r}
    items = {}
    for change in changes:
        if change.record_type not in FIELDS:
            continue
        record = displayed.get(change.record_id)
        items[change.record_id] = {
            "id": change.record_id,
            "record": project(record)
            if record and record.get("type") in FIELDS
            else None,
        }
    return {
        "items": list(items.values()),
        "cursor": changes[-1].id if changes else since,
        "has_more": len(changes) == 200,
    }
