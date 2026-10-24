"""学习数据同步领域逻辑（本地优先 + 增量同步）。

设计（ARCHITECTURE.md 附录 A）：
- 服务端只做"中立存储 + 冲突仲裁"，不做业务计时；记录为通用 JSON，业务校验在前端。
- expectedRevision 乐观并发：客户端必须基于它读到的最新版本提交，否则 409 RECORD_CONFLICT。
- operationId + 命令内容 sha256 幂等：同一 operationId 重放返回首次结果；同 ID 不同内容 409。
- 记录类型不可变：避免用一个类型的 id 覆盖成另一类型。
- 写事务在单进程内用线程锁串行化（SQLite 单写者、4 人并发极低），消除 deferred 事务升级死锁。
"""
import hashlib
import json
import threading

from sqlalchemy import BLOB, cast, func, select

from ..errors import ApiError
from ..models import LearningOperation, LearningRecord
from ..time import utcnow

# 允许的学习记录类型（与前端 v0.2 的分表对应；userSchool 为梦校）
ALLOWED_TYPES = {'subject', 'session', 'task', 'mistake', 'userSchool'}
PROTECTED_KEYS = {'user_id', 'userId', 'owner', 'apiKey', 'password', 'token', 'revision'}

MAX_RECORD_BYTES = 2 * 1024 * 1024   # 单条记录 2MB（图片走附件，不应进入 body）
MAX_TOTAL_RECORDS = 20000            # 每账号 2 万条
MAX_TOTAL_BYTES = 20 * 1024 * 1024   # 每账号 20MB
MAX_OPERATIONS = 200000              # 每账号操作日志上限

sync_write_lock = threading.Lock()


def canonical_signature(command_dict: dict) -> str:
    """对解析后的命令做规范化哈希：语义相同即视为同一命令（不受字段顺序/空白影响）。"""
    canonical = json.dumps(command_dict, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def list_records(db, user_id: int) -> list[dict]:
    rows = db.scalars(
        select(LearningRecord)
        .where(LearningRecord.user_id == user_id)
        .order_by(LearningRecord.id)
    ).all()
    return [
        {'id': r.id, 'record': None if r.deleted else json.loads(r.body), 'revision': r.revision}
        for r in rows
    ]


def _validate_record(record_id: str, record):
    if not isinstance(record, dict):
        raise ApiError(400, 40004, '记录内容无效')
    if str(record.get('id')) != record_id:
        raise ApiError(400, 40004, '记录 ID 不一致')
    if record.get('type') not in ALLOWED_TYPES:
        raise ApiError(400, 40004, '不支持的记录类型')
    if any(k in record for k in PROTECTED_KEYS):
        raise ApiError(400, 40004, '记录包含受保护字段')
    return record['type']


def _used_bytes(db, user_id: int) -> int:
    dialect = db.bind.dialect.name
    # SQLite: length(CAST(body AS BLOB)) 为字节数；MySQL: OCTET_LENGTH 为字节数
    size_expr = func.length(cast(LearningRecord.body, BLOB)) if dialect == 'sqlite' \
        else func.octet_length(LearningRecord.body)
    return int(db.scalar(
        select(func.coalesce(func.sum(size_expr), 0)).where(LearningRecord.user_id == user_id)
    ) or 0)


def execute_commands(db, user_id: int, command_dict: dict) -> dict:
    changes = command_dict['changes']
    if len({c['id'] for c in changes}) != len(changes):
        raise ApiError(400, 40004, '一次命令中记录 ID 不可重复')

    signature = canonical_signature(command_dict)

    with sync_write_lock:
        try:
            # 幂等：相同 operationId 已处理过
            previous = db.scalar(
                select(LearningOperation).where(
                    LearningOperation.user_id == user_id,
                    LearningOperation.operation_id == command_dict['operationId'],
                )
            )
            if previous is not None:
                if previous.signature != signature:
                    raise ApiError(409, 40903, '同一操作 ID 不能提交不同内容')
                return json.loads(previous.result)

            changed = []
            for change in changes:
                record_id = change['id']
                record = change['record']
                expected = change['expectedRevision']

                old = db.scalar(
                    select(LearningRecord).where(
                        LearningRecord.user_id == user_id,
                        LearningRecord.id == record_id,
                    )
                )
                old_revision = old.revision if old else 0
                if old_revision != expected:
                    conflict_record = None
                    if old and not old.deleted:
                        conflict_record = json.loads(old.body)
                    raise ApiError(
                        409, 40902, '记录已在其他设备更新，请先处理冲突',
                        data={'conflicts': [{
                            'id': record_id, 'revision': old_revision, 'record': conflict_record,
                        }]},
                    )

                if record is None:
                    body_text, deleted = 'null', 1
                else:
                    record_type = _validate_record(record_id, record)
                    # 类型不可变
                    if old and not old.deleted:
                        old_type = json.loads(old.body).get('type')
                        if old_type != record_type:
                            raise ApiError(400, 40003, '不能修改记录类型')
                    body_text = json.dumps(record, ensure_ascii=False, separators=(',', ':'))
                    if len(body_text.encode('utf-8')) > MAX_RECORD_BYTES:
                        raise ApiError(413, 41301, '单条学习记录过大，请把图片改为附件上传')
                    deleted = 0

                new_revision = old_revision + 1
                if old:
                    old.body = body_text
                    old.revision = new_revision
                    old.deleted = deleted
                    old.updated_at = utcnow()
                else:
                    db.add(LearningRecord(
                        user_id=user_id, id=record_id, body=body_text,
                        revision=new_revision, deleted=deleted, updated_at=utcnow(),
                    ))
                changed.append({'id': record_id, 'record': record, 'revision': new_revision})

            # 配额（超了则整体回滚，不写入）
            total = db.scalar(
                select(func.count()).select_from(LearningRecord)
                .where(LearningRecord.user_id == user_id)
            )
            if total > MAX_TOTAL_RECORDS or _used_bytes(db, user_id) > MAX_TOTAL_BYTES:
                raise ApiError(413, 41301, '学习数据超出账号限额（2 万条 / 20MB）')
            op_count = db.scalar(
                select(func.count()).select_from(LearningOperation)
                .where(LearningOperation.user_id == user_id)
            )
            if op_count >= MAX_OPERATIONS:
                raise ApiError(413, 41302, '操作记录达到账号限额，请联系管理员')

            result = {'operationId': command_dict['operationId'], 'changed': changed}
            db.add(LearningOperation(
                user_id=user_id, operation_id=command_dict['operationId'],
                signature=signature, result=json.dumps(result, ensure_ascii=False),
                created_at=utcnow(),
            ))
            db.commit()
            return result
        except Exception:
            db.rollback()
            raise
