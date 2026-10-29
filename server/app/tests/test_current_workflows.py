import json, uuid
from datetime import timedelta
from sqlalchemy import select
from app.tests.test_ai import friend as friend
from app.tests.conftest import login
from app.tests.test_group_v1 import push
from app.models import LearningRecord, Audit, RoomPresence, DevicePresence
from app.time import utcnow


def admin(client):
    return {
        "Authorization": "Bearer "
        + login(client, "admin@test.com", "Admin2028")["access_token"]
    }


def me(client, h):
    return client.get("/api/v1/auth/me", headers=h).json()["data"]["id"]


def member(client, h, uid):
    return next(
        m
        for m in client.get("/api/v1/group/members", headers=h).json()["data"]
        if m["id"] == uid
    )


def beat(client, h, device, status="idle", room=None):
    r = client.post(
        "/api/v1/group/presence",
        headers=h,
        json={"device_id": device, "status": status, "room_id": room},
    )
    assert r.status_code == 200, r.text


def test_device_presence_location_and_private_room(client, friend):
    ah = admin(client)
    uid = me(client, friend)
    beat(client, friend, "desktop", "focusing", 1)
    beat(client, friend, "phone")
    row = member(client, ah, uid)
    assert row["isOnline"] and row["status"] == "focusing" and row["roomId"] == 1
    beat(client, friend, "phone", "offline")
    assert member(client, ah, uid)["isOnline"] is True
    room = client.post(
        "/api/v1/rooms",
        headers=friend,
        json={
            "accept_sharing": True,
            "name": "不可泄露的房名",
            "visibility": "private",
        },
    ).json()["data"]["id"]
    beat(client, friend, "desktop", "focusing", room)
    row = member(client, ah, uid)
    assert row["roomId"] is None and row["roomName"] == "私密自习室"
    assert member(client, friend, uid)["roomId"] == room
    with client.app.state.session_factory() as db:
        assert (
            db.scalar(
                select(RoomPresence).where(
                    RoomPresence.user_id == uid, RoomPresence.room_id == 1
                )
            ).status
            == "offline"
        )
    public = client.post(
        "/api/v1/rooms",
        headers=friend,
        json={"name": "公开学习房", "visibility": "public", "accept_sharing": True},
    ).json()["data"]
    beat(client, friend, "desktop", "focusing", public["id"])
    row = member(client, ah, uid)
    assert row["roomId"] == public["id"] and row["roomName"] == "公开学习房"
    # A friend's public location does not grant room membership or reveal peers.
    assert client.get(f"/api/v1/rooms/{public['id']}", headers=ah).status_code == 403
    beat(client, friend, "desktop")
    assert (
        member(client, ah, uid)["roomName"] is None
        and "未在自习室" in member(client, ah, uid)["statusText"]
    )


def test_presence_privacy_and_expiry(client, friend):
    ah = admin(client)
    uid = me(client, friend)
    beat(client, friend, "desktop", "focusing", 1)
    client.put("/api/v1/users/me", headers=friend, json={"is_private_mode": True})
    row = member(client, ah, uid)
    assert (
        row["statusText"] == "隐私中"
        and row["isOnline"] is None
        and row["roomId"] is None
        and row["roomName"] is None
    )
    assert member(client, friend, uid)["isOnline"] is True
    client.put("/api/v1/users/me", headers=friend, json={"is_private_mode": False})
    with client.app.state.session_factory() as db:
        db.get(DevicePresence, (uid, "desktop")).heartbeat_at = utcnow() - timedelta(
            seconds=91
        )
        db.commit()
    assert member(client, ah, uid)["isOnline"] is False


def message(client, friend, monkeypatch):
    async def fake(settings, messages):
        return (
            "```json\n"
            + json.dumps(
                {
                    "tasks": [
                        {
                            "title": f"任务{i}",
                            "estimate_min": 30,
                            "acceptance": "完成练习",
                        }
                        for i in range(4)
                    ]
                },
                ensure_ascii=False,
            )
            + "\n```"
        )

    monkeypatch.setattr("app.services.ai.call_ark", fake)
    cid = client.post("/api/v1/ai/conversations", headers=friend, json={}).json()[
        "data"
    ]["id"]
    data = client.post(
        "/api/v1/ai/chat",
        headers=friend,
        json={"conversation_id": cid, "content": "生成明日任务"},
    ).json()["data"]
    assert len(data["suggested_tasks"]) == 4
    return data["message_id"], cid


def test_ai_selected_import_receipt_and_safe_undo(client, friend, monkeypatch):
    mid, cid = message(client, friend, monkeypatch)
    path = f"/api/v1/ai/messages/{mid}"
    result = client.post(
        path + "/import-tasks",
        headers=friend,
        json={"confirmed": True, "selected": [0, 1, 2]},
    ).json()["data"]
    assert result["imported_count"] == 3
    again = client.post(
        path + "/import-tasks",
        headers=friend,
        json={"confirmed": True, "selected": [0, 1, 2]},
    )
    assert again.json()["data"] == result
    assert (
        client.post(
            path + "/import-tasks",
            headers=friend,
            json={"confirmed": True, "selected": [3]},
        ).status_code
        == 409
    )
    uid = me(client, friend)
    for i, patch in [(1, {"title": "人工修改"}), (2, {"done": 1})]:
        records = client.get("/api/v1/sync/records", headers=friend).json()["data"][
            "records"
        ]
        row = next(x for x in records if x["id"] == f"ai-task-{mid}-{i}")
        body = {**row["record"], **patch}
        r = client.post(
            "/api/v1/sync/commands",
            headers=friend,
            json={
                "operationId": str(uuid.uuid4()),
                "changes": [
                    {
                        "id": row["id"],
                        "expectedRevision": row["revision"],
                        "record": body,
                    }
                ],
            },
        )
        assert r.status_code == 200, r.text
    undo = client.post(path + "/undo-tasks", headers=friend, json={"confirmed": True})
    assert undo.status_code == 200, undo.text
    result = undo.json()["data"]
    assert result["undo"]["deleted"] == 1 and len(result["undo"]["kept"]) == 2
    assert (
        client.post(
            path + "/undo-tasks", headers=friend, json={"confirmed": True}
        ).json()["data"]
        == result
    )
    detail = client.get(f"/api/v1/ai/conversations/{cid}", headers=friend).json()[
        "data"
    ]["messages"][-1]
    assert detail["task_import"]["state"] == "undone"
    assert (
        client.post(
            path + "/undo-tasks", headers=admin(client), json={"confirmed": True}
        ).status_code
        == 404
    )
    with client.app.state.session_factory() as db:
        assert db.get(LearningRecord, (uid, f"ai-task-{mid}-0")).deleted == 1
        assert db.get(LearningRecord, (uid, f"ai-task-{mid}-1")).deleted == 0


def test_resource_review_snapshot_note_and_cas(client, friend):
    ah = admin(client)
    body = {
        "title": "原版资料",
        "url": "https://pan.quark.cn/s/approved",
        "intro": "原版简介",
        "personal_note": "个人私有备注",
    }
    created = client.post("/api/v1/resources", headers=friend, json=body)
    assert created.status_code == 200, created.text
    row = created.json()["data"]
    rid = row["id"]
    assert client.get(f"/api/v1/resources/{rid}", headers=ah).status_code == 404
    assert client.post(f"/api/v1/resources/{rid}/like", headers=ah).status_code == 404
    queued = client.get("/api/v1/admin/resources", headers=ah).json()["data"]["items"]
    assert "personal_note" not in queued[0]
    assert (
        client.post(
            f"/api/v1/admin/resources/{rid}/review",
            headers=friend,
            json={"action": "approve", "expected_revision": 1},
        ).status_code
        == 403
    )
    approved = client.post(
        f"/api/v1/admin/resources/{rid}/review",
        headers=ah,
        json={"action": "approve", "expected_revision": 1},
    )
    assert approved.status_code == 200, approved.text
    visible = client.get(f"/api/v1/resources/{rid}", headers=ah).json()["data"]
    assert visible["title"] == "原版资料" and "personal_note" not in visible
    assert (
        client.post(
            f"/api/v1/admin/resources/{rid}/review",
            headers=ah,
            json={"action": "approve", "expected_revision": 1},
        ).status_code
        == 409
    )
    edited = client.put(
        f"/api/v1/resources/{rid}",
        headers=friend,
        json={
            "title": "未审新版资料",
            "url": "https://pan.quark.cn/s/unreviewed",
            "expected_revision": 2,
        },
    )
    assert edited.status_code == 200, edited.text
    assert (
        client.get(f"/api/v1/resources/{rid}", headers=ah).json()["data"]["url"]
        == visible["url"]
    )
    assert client.get("/api/v1/resources?q=未审新版", headers=ah).json()["data"] == []
    assert (
        client.post(
            f"/api/v1/admin/resources/{rid}/review",
            headers=ah,
            json={"action": "approve", "expected_revision": 2},
        ).status_code
        == 409
    )
    rejected = client.post(
        f"/api/v1/admin/resources/{rid}/review",
        headers=ah,
        json={"action": "reject", "expected_revision": 3, "note": "链接需要核实"},
    )
    assert rejected.status_code == 200, rejected.text
    assert (
        client.get(f"/api/v1/resources/{rid}", headers=ah).json()["data"]["title"]
        == "原版资料"
    )
    assert (
        client.get(f"/api/v1/resources/{rid}", headers=friend).json()["data"][
            "review_status"
        ]
        == "rejected"
    )


def test_admin_cannot_delete_learning_or_modify_preferences(client, friend):
    ah = admin(client)
    uid = me(client, friend)
    push(client, friend, [{"id": "keep-task", "type": "task", "title": "保留学习数据"}])
    assert client.delete(f"/api/v1/admin/members/{uid}", headers=ah).status_code == 403
    assert (
        client.put(
            f"/api/v1/admin/members/{uid}", headers=ah, json={"daily_goal_min": 999}
        ).status_code
        == 403
    )
    assert (
        client.put(
            f"/api/v1/admin/members/{uid}",
            headers=ah,
            json={"vip_action": "renew", "vip_days": 5, "note": "延长测试授权"},
        ).status_code
        == 200
    )
    with client.app.state.session_factory() as db:
        assert db.get(LearningRecord, (uid, "keep-task")).deleted == 0
        log = db.scalar(
            select(Audit)
            .where(Audit.action == "admin.update_member", Audit.user_id == uid)
            .order_by(Audit.id.desc())
        )
        assert (
            log.actor_id == 1
            and "before" in json.loads(log.detail)
            and "after" in json.loads(log.detail)
        )


def test_configuration_announcement_and_batch_invites(client):
    ah = admin(client)
    current = client.get("/api/v1/admin/config", headers=ah).json()["data"]
    payload = {"site_name": "研时新名字", "expected_revision": current["revision"]}
    assert (
        client.put("/api/v1/admin/config", headers=ah, json=payload).status_code == 200
    )
    assert (
        client.put("/api/v1/admin/config", headers=ah, json=payload).status_code == 409
    )
    assert (
        client.put(
            "/api/v1/admin/config", headers=ah, json={"registration_open": "false"}
        ).status_code
        == 400
    )
    codes = client.post(
        "/api/v1/admin/invites/batch", headers=ah, json={"count": 3, "vip_days": 30}
    )
    assert codes.status_code == 200, codes.text
    assert len({r["code"] for r in codes.json()["data"]}) == 3
    row = client.post(
        "/api/v1/admin/announcements", headers=ah, json={"content": "公告原版"}
    ).json()["data"]
    for expected, status in [(row["revision"], 200), (row["revision"], 409)]:
        result = client.put(
            "/api/v1/admin/announcements/" + str(row["id"]),
            headers=ah,
            json={"content": "公告新版", "expected_revision": expected},
        )
        assert result.status_code == status, result.text
