"""清理本地开发库 dev.sqlite 中的 e2e 冒烟残留（已注销成员及其数据、e2e 邀请码/记录）。

仅用于本地开发库；生产库不需要。执行前请先停掉 uvicorn，避免 SQLite 写锁。
用法：.venv\\Scripts\\python.exe scripts\\cleanup_dev.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select

from app.config import Settings
from app.database import make_database
from app.models import (
    AIConversation, AIMessage, Attachment, Invite, LearningOperation, LearningRecord,
    RefreshToken, RoomGoal, RoomMember, RoomMessage, RoomPresence, User,
)

settings = Settings()
engine, Session = make_database(settings.database_url)
db = Session()
n = {}


def cascade(uid):
    for model, col in (
        (RefreshToken, "user_id"), (RoomMember, "user_id"), (RoomPresence, "user_id"),
        (RoomGoal, "user_id"), (RoomMessage, "user_id"), (LearningRecord, "user_id"),
        (LearningOperation, "user_id"), (Attachment, "uploader_id"),
    ):
        n[model.__name__] = n.get(model.__name__, 0) + db.execute(
            delete(model).where(getattr(model, col) == uid)).rowcount
    convos = db.scalars(select(AIConversation.id).where(AIConversation.user_id == uid)).all()
    if convos:
        n["AIMessage"] = n.get("AIMessage", 0) + db.execute(
            delete(AIMessage).where(AIMessage.conversation_id.in_(convos))).rowcount
    n["AIConversation"] = n.get("AIConversation", 0) + db.execute(
        delete(AIConversation).where(AIConversation.user_id == uid)).rowcount


# 1) 已注销成员的业务数据残留（users 行按产品逻辑保留为软删，审计/登录日志仍引用，故不物理删除）
deleted_users = db.scalars(select(User).where(User.status == "deleted")).all()
for u in deleted_users:
    cascade(u.id)
n["已注销成员(软删行保留)"] = len(deleted_users)

# 2) 兜底：id 形如 e2e-* 的同步记录/操作
n["LearningRecord(e2e)"] = db.execute(
    delete(LearningRecord).where(LearningRecord.id.like("e2e-%"))).rowcount
n["LearningOperation(e2e)"] = db.execute(
    delete(LearningOperation).where(LearningOperation.operation_id.like("e2e-op-%"))).rowcount

# 3) e2e 留言
n["RoomMessage(e2e)"] = db.execute(
    delete(RoomMessage).where(RoomMessage.content == "e2e 加油")).rowcount

# 4) e2e 冒烟邀请码（含已使用）
n["Invite(e2e)"] = db.execute(
    delete(Invite).where(Invite.remark == "e2e冒烟")).rowcount

db.commit()
print("清理完成：")
for k, v in n.items():
    if v:
        print(f"  {k}: {v}")
if not any(n.values()):
    print("  （无残留，库已是干净的）")
db.close()
engine.dispose()
