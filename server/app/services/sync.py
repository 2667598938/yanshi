"""学习数据同步领域逻辑（本地优先 + 增量同步）。

设计（ARCHITECTURE.md 附录 A）：
- 服务端校验并归一学习记录，客户端不是时长、日期或权限的权威来源。
- expectedRevision 乐观并发：客户端必须基于它读到的最新版本提交，否则 409 RECORD_CONFLICT。
- operationId + 命令内容 sha256 幂等：同一 operationId 重放返回首次结果；同 ID 不同内容 409。
- 记录类型不可变：避免用一个类型的 id 覆盖成另一类型。
- 写事务使用用户行锁；SQLite显式BEGIN IMMEDIATE。进程内RLock仅用于减少本进程竞争，不作为跨进程正确性保证。
"""

import hashlib
import json
import threading
from datetime import timezone

from sqlalchemy import BLOB, cast, func, select
from pydantic import ValidationError

from ..errors import ApiError
from ..models import (
    LearningOperation,
    LearningRecord,
    LearningChange,
    User,
    SessionFact,
)
from ..schemas.sync import LearningPreferences
from ..schemas.account import ProfileUpdate
from ..time import utcnow
from .session_records import display_record, refresh_facts
from ..database import begin_development_transaction

# 允许的学习记录类型（与前端 v0.2 的分表对应；userSchool 为梦校）
ALLOWED_TYPES = {
    "subject",
    "session",
    "task",
    "mistake",
    "userSchool",
    "preferences",
    "profile",
    "timeNode",
}
PROTECTED_KEYS = {
    "user_id",
    "userId",
    "owner",
    "apiKey",
    "password",
    "token",
    "revision",
}

MAX_RECORD_BYTES = 2 * 1024 * 1024  # 单条记录 2MB（图片走附件，不应进入 body）
MAX_TOTAL_RECORDS = 20000  # 每账号 2 万条
MAX_TOTAL_BYTES = 20 * 1024 * 1024  # 每账号 20MB
MAX_OPERATIONS = 200000  # 每账号操作日志上限

SESSION_MAX_SEC = 180 * 60  # 番茄时长上限 180 分钟
SESSION_MAX_PAUSE_MS = 30 * 60 * 1000  # 单次暂停上限；累计暂停仅用于扣减时长

sync_write_lock = threading.RLock()


def _normalize_session(record: dict) -> dict:
    if record.get("type") != "session":
        return record
    from ..schemas.session import normalize_session

    try:
        return normalize_session(record)
    except (ValueError, TypeError, OverflowError, ValidationError):
        raise ApiError(
            422,
            42201,
            "计时记录无效：需提供2026年起的完整起止时间、合法模式及暂停信息",
            data={"record_id": record.get("id")},
        ) from None


def canonical_signature(command_dict: dict) -> str:
    """对解析后的命令做规范化哈希：语义相同即视为同一命令（不受字段顺序/空白影响）。"""
    canonical = json.dumps(
        command_dict, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def list_records(db, user_id: int) -> list[dict]:
    rows = db.scalars(
        select(LearningRecord)
        .where(LearningRecord.user_id == user_id)
        .order_by(LearningRecord.id)
    ).all()
    return [
        {
            "id": r.id,
            "record": None
            if r.deleted
            else display_record(db, user_id, json.loads(r.body)),
            "revision": r.revision,
        }
        for r in rows
    ]


def pull_records(db, user_id: int, since: int | None = None):
    latest = (
        db.scalar(
            select(func.coalesce(func.max(LearningChange.id), 0)).where(
                LearningChange.user_id == user_id
            )
        )
        or 0
    )
    if since is None or since > latest:
        return {
            "records": list_records(db, user_id),
            "cursor": latest,
            "hasMore": False,
            "serverTime": int(utcnow().replace(tzinfo=timezone.utc).timestamp() * 1000),
        }
    changes = db.scalars(
        select(LearningChange)
        .where(
            LearningChange.user_id == user_id,
            LearningChange.id > since,
        )
        .order_by(LearningChange.id)
        .limit(200)
    ).all()
    ids = {row.record_id for row in changes}
    rows = (
        db.scalars(
            select(LearningRecord).where(
                LearningRecord.user_id == user_id, LearningRecord.id.in_(ids)
            )
        ).all()
        if ids
        else []
    )
    cursor = changes[-1].id if changes else latest
    return {
        "records": [
            {
                "id": row.id,
                "revision": row.revision,
                "record": None
                if row.deleted
                else display_record(db, user_id, json.loads(row.body)),
            }
            for row in rows
        ],
        "cursor": cursor,
        "hasMore": cursor < latest,
        "serverTime": int(utcnow().replace(tzinfo=timezone.utc).timestamp() * 1000),
    }


def _validate_record(record_id: str, record):
    if not isinstance(record, dict):
        raise ApiError(400, 40004, "记录内容无效")
    if str(record.get("id")) != record_id:
        raise ApiError(400, 40004, "记录 ID 不一致")
    if record.get("type") not in ALLOWED_TYPES:
        raise ApiError(400, 40004, "不支持的记录类型")
    if any(k in record for k in PROTECTED_KEYS):
        raise ApiError(400, 40004, "记录包含受保护字段")
    if record.get("type") == "task":
        from ..schemas.task import TaskValue

        try:
            TaskValue.model_validate(record)
        except ValidationError:
            raise ApiError(
                400, 40004, "任务字段无效，请检查标题、日期和预估分钟"
            ) from None
    if record.get("type") == "timeNode":
        from ..schemas.time_node import TimeNodeValue

        try:
            record["value"] = TimeNodeValue.model_validate(
                record.get("value")
            ).model_dump()
        except ValidationError:
            raise ApiError(400, 40004, "时间节点内容无效") from None
        if len(record_id) > 100:
            raise ApiError(400, 40004, "时间节点标识过长")
    if record.get("type") in {"preferences", "profile"}:
        expected_id = (
            "learning-settings" if record["type"] == "preferences" else "profile"
        )
        if record_id != expected_id or record.get("key") != expected_id:
            raise ApiError(400, 40004, "个人设置记录标识无效")
        try:
            schema = (
                LearningPreferences
                if record["type"] == "preferences"
                else ProfileUpdate
            )
            parsed = schema.model_validate(record.get("value"))
            record["value"] = {
                k: v
                for k, v in parsed.model_dump(
                    exclude_unset=record["type"] == "profile"
                ).items()
                if v is not None and k not in {"privacy_mode", "is_private_mode"}
            }
        except ValidationError:
            raise ApiError(400, 40004, "个人设置内容无效") from None
    return record["type"]


def _used_bytes(db, user_id: int) -> int:
    dialect = db.bind.dialect.name
    # SQLite: length(CAST(body AS BLOB)) 为字节数；MySQL: OCTET_LENGTH 为字节数
    size_expr = (
        func.length(cast(LearningRecord.body, BLOB))
        if dialect == "sqlite"
        else func.octet_length(LearningRecord.body)
    )
    return int(
        db.scalar(
            select(func.coalesce(func.sum(size_expr), 0)).where(
                LearningRecord.user_id == user_id
            )
        )
        or 0
    )


def execute_commands(db, user_id: int, command_dict: dict, before_commit=None) -> dict:
    changes = command_dict["changes"]
    if len({c["id"] for c in changes}) != len(changes):
        raise ApiError(400, 40004, "一次命令中记录 ID 不可重复")

    signature = canonical_signature(command_dict)

    with sync_write_lock:
        try:
            if (
                db.get_bind().dialect.name == "sqlite"
                and not db.connection().connection.driver_connection.in_transaction
            ):
                begin_development_transaction(db)
            db.scalar(select(User).where(User.id == user_id).with_for_update())
            # 幂等：相同 operationId 已处理过
            previous = db.scalar(
                select(LearningOperation).where(
                    LearningOperation.user_id == user_id,
                    LearningOperation.operation_id == command_dict["operationId"],
                )
            )
            if previous is not None:
                if previous.signature != signature:
                    raise ApiError(409, 40903, "同一操作 ID 不能提交不同内容")
                return json.loads(previous.result)

            changed = []
            for change in changes:
                record_id = change["id"]
                record = change["record"]
                expected = change["expectedRevision"]

                old = db.scalar(
                    select(LearningRecord)
                    .where(
                        LearningRecord.user_id == user_id,
                        LearningRecord.id == record_id,
                    )
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
                old_revision = old.revision if old else 0
                if old_revision != expected:
                    conflict_record = None
                    if old and not old.deleted:
                        conflict_record = json.loads(old.body)
                    raise ApiError(
                        409,
                        40902,
                        "记录已在其他设备更新，请先处理冲突",
                        data={
                            "conflicts": [
                                {
                                    "id": record_id,
                                    "revision": old_revision,
                                    "record": conflict_record,
                                }
                            ]
                        },
                    )

                if record is None:
                    body_text, deleted = "null", 1
                else:
                    record_type = _validate_record(record_id, record)
                    # 番茄记录由服务端重算时长与状态，避免客户端伪造/挂起误差
                    record = _normalize_session(record)
                    if record_type == "profile":
                        user = db.get(User, user_id)
                        for key, value in record["value"].items():
                            setattr(user, key, value)
                    # 类型不可变
                    if old and not old.deleted:
                        old_type = json.loads(old.body).get("type")
                        if old_type != record_type:
                            raise ApiError(400, 40003, "不能修改记录类型")
                    body_text = json.dumps(
                        record, ensure_ascii=False, separators=(",", ":")
                    )
                    if len(body_text.encode("utf-8")) > MAX_RECORD_BYTES:
                        raise ApiError(
                            413, 41301, "单条学习记录过大，请把图片改为附件上传"
                        )
                    deleted = 0

                from ..models import TimeNode

                previous_type = (
                    json.loads(old.body).get("type")
                    if old and not old.deleted
                    else None
                )
                if (
                    record and record.get("type") == "timeNode"
                ) or previous_type == "timeNode":
                    node = db.get(TimeNode, (user_id, record_id))
                    if record is None or record.get("type") != "timeNode":
                        if node:
                            db.delete(node)
                    else:
                        if not node:
                            node = TimeNode(user_id=user_id, id=record_id)
                            db.add(node)
                        for key, value in record["value"].items():
                            setattr(node, key, value)
                new_revision = old_revision + 1
                if old:
                    old.body = body_text
                    old.revision = new_revision
                    old.deleted = deleted
                    old.updated_at = utcnow()
                else:
                    db.add(
                        LearningRecord(
                            user_id=user_id,
                            id=record_id,
                            body=body_text,
                            revision=new_revision,
                            deleted=deleted,
                            updated_at=utcnow(),
                        )
                    )
                changed.append(
                    {"id": record_id, "record": record, "revision": new_revision}
                )
                db.add(
                    LearningChange(
                        user_id=user_id,
                        record_id=record_id,
                        revision=new_revision,
                        record_type=record.get("type") if record else previous_type,
                    )
                )

            if any(
                (c["record"] and c["record"].get("type") == "session")
                or db.get(SessionFact, (user_id, c["id"]))
                for c in changes
            ):
                refresh_facts(db, user_id, {c["id"] for c in changes})
                for item in changed:
                    item["record"] = display_record(db, user_id, item["record"])

            # 配额（超了则整体回滚，不写入）
            total = db.scalar(
                select(func.count())
                .select_from(LearningRecord)
                .where(LearningRecord.user_id == user_id)
            )
            if total > MAX_TOTAL_RECORDS or _used_bytes(db, user_id) > MAX_TOTAL_BYTES:
                raise ApiError(413, 41301, "学习数据超出账号限额（2 万条 / 20MB）")
            op_count = db.scalar(
                select(func.count())
                .select_from(LearningOperation)
                .where(LearningOperation.user_id == user_id)
            )
            if op_count >= MAX_OPERATIONS:
                raise ApiError(413, 41302, "操作记录达到账号限额，请联系管理员")

            result = {"operationId": command_dict["operationId"], "changed": changed}
            db.add(
                LearningOperation(
                    user_id=user_id,
                    operation_id=command_dict["operationId"],
                    signature=signature,
                    result=json.dumps(result, ensure_ascii=False),
                    created_at=utcnow(),
                )
            )
            if before_commit:
                before_commit(result)
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
