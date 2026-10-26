"""受邀小组是共享边界；加入公开自习室不能获得学习数据权限。"""

import json
from sqlalchemy import select, func
from ..models import User, StudyGroup, StudyGroupMember, LearningRecord
from ..errors import ApiError
from .session_records import display_record


def enroll(db, user_id):
    if not db.get(StudyGroup, 1):
        db.add(StudyGroup(id=1, name="研时学习小组"))
        db.flush()
    if not db.get(StudyGroupMember, (1, user_id)):
        db.add(StudyGroupMember(group_id=1, user_id=user_id))


def same_group(db, viewer_id, owner_id):
    mine = select(StudyGroupMember.group_id).where(
        StudyGroupMember.user_id == viewer_id
    )
    return (
        db.scalar(
            select(StudyGroupMember.group_id)
            .where(
                StudyGroupMember.user_id == owner_id,
                StudyGroupMember.group_id.in_(mine),
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
    rows = db.scalars(query.order_by(LearningRecord.id).limit(200)).all()
    return {
        "items": [
            project(display_record(db, owner_id, json.loads(row.body))) for row in rows
        ],
        "next": rows[-1].id if len(rows) == 200 else None,
    }


def shared_user_ids(viewer_id):
    groups = select(StudyGroupMember.group_id).where(
        StudyGroupMember.user_id == viewer_id
    )
    return select(StudyGroupMember.user_id).where(StudyGroupMember.group_id.in_(groups))
