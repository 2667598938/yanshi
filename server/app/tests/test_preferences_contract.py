"""覆盖完整前端格式、历史失败批次重试和严格边界，防止设置阻断任务同步。"""
import uuid

import pytest
from sqlalchemy import select

from app.models import LearningRecord
from app.tests.test_sync import headers, send, task


def preferences(text):
    return {"id": "learning-settings", "expectedRevision": 0, "record": {
        "id": "learning-settings", "key": "learning-settings", "type": "preferences",
        "value": {"bulletEnabled": True, "bulletText": text, "focusMin": 25,
                  "shortBreakMin": 5, "longBreakMin": 15, "longBreakEvery": 4}}}


@pytest.mark.parametrize("text", ["", "写给自己的寄语", "字" * 80])
def test_complete_frontend_preferences_mixed_batch_and_replay(client, text):
    h, op = headers(client), uuid.uuid4().hex
    changes = [{"id": "mixed-task", "expectedRevision": 0, "record": task("mixed-task")},
               preferences(text)]
    result = send(client, h, op, changes)
    assert result.status_code == 200, result.text
    # 同一个历史待确认批次可以直接重放；不能重复写任务或增加修订。
    replay = send(client, h, op, changes)
    assert replay.status_code == 200, replay.text
    assert replay.json()["data"] == result.json()["data"]
    with client.app.state.session_factory() as db:
        rows = db.scalars(select(LearningRecord).where(LearningRecord.id.in_(
            ["mixed-task", "learning-settings"]))).all()
        assert len(rows) == 2
    pulled = client.get("/api/v1/sync/records", headers=h)
    assert pulled.status_code == 200, pulled.text
    pulled_preferences = next(row for row in pulled.json()["data"]["records"]
                              if row["id"] == "learning-settings")
    assert pulled_preferences["record"]["value"]["bulletText"] == text
    changed = result.json()["data"]["changed"]
    saved = next(row for row in changed if row["id"] == "learning-settings")
    assert saved["record"]["value"]["bulletText"] == text


@pytest.mark.parametrize("text", ["字" * 81, None, 123])
def test_invalid_bullet_text_rejects_atomically(client, text):
    h = headers(client)
    result = send(client, h, uuid.uuid4().hex, [
        {"id": "invalid-task", "expectedRevision": 0, "record": task("invalid-task")},
        preferences(text)])
    assert result.status_code == 400, result.text
    with client.app.state.session_factory() as db:
        assert db.scalar(select(LearningRecord).where(LearningRecord.id == "invalid-task")) is None


def test_personal_bullet_never_shared_with_group_or_other_sync_accounts(client):
    from app.tests.test_room import register_friend

    admin = headers(client)
    owner = register_friend(client, admin, "private-bullet@test.com", "弹幕同学")
    owner_id = client.get("/api/v1/auth/me", headers=owner).json()["data"]["id"]
    secret = "仅本人设备可见的私人寄语"
    assert send(client, owner, uuid.uuid4().hex, [preferences(secret)]).status_code == 200
    assert secret not in client.get("/api/v1/sync/records", headers=admin).text
    shared = client.get(f"/api/v1/group/members/{owner_id}/learning", headers=admin)
    assert shared.status_code == 200, shared.text
    assert secret not in shared.text
