"""Incremental sharing must retain deletions without exposing private records."""

import json
import uuid
from app.models import Inspiration, LearningChange, LearningRecord
from app.tests.test_group_v1 import headers, push
from app.tests.test_room import register_friend


def change(client, h, rid, revision, record):
    response = client.post(
        "/api/v1/sync/commands",
        headers=h,
        json={
            "operationId": str(uuid.uuid4()),
            "changes": [{"id": rid, "expectedRevision": revision, "record": record}],
        },
    )
    assert response.status_code == 200, response.text


def test_incremental_updates_deletions_and_private_ids(client):
    admin = headers(client)
    peer = register_friend(client, admin, "delta@test.com", "增量同学")
    uid = client.get("/api/v1/auth/me", headers=peer).json()["data"]["id"]
    base = f"/api/v1/group/members/{uid}/learning"
    push(client, peer, [{"id": "math", "type": "task", "title": "数学"}])
    first = client.get(base, headers=admin).json()["data"]
    cursor = first["cursor"]
    change(client, peer, "math", 1, {"id": "math", "type": "task", "title": "英语"})
    push(client, peer, [{"id": "secret-id", "type": "userSchool", "note": "私人内容"}])
    response = client.get(base + "/changes", headers=admin, params={"since": cursor})
    data = response.json()["data"]
    assert data["items"] == [
        {"id": "math", "record": {"id": "math", "type": "task", "title": "英语"}}
    ]
    assert "secret" not in response.text
    change(client, peer, "math", 2, None)
    change(client, peer, "secret-id", 1, None)
    data2 = client.get(
        base + "/changes", headers=admin, params={"since": data["cursor"]}
    ).json()["data"]
    assert data2["items"] == [{"id": "math", "record": None}]
    assert (
        client.get(
            base + "/changes", headers=admin, params={"since": data2["cursor"]}
        ).json()["data"]["items"]
        == []
    )
    assert (
        client.get(base + "/changes", headers=admin, params={"since": -1}).status_code
        == 400
    )
    assert (
        client.get(
            base + "/changes", headers=admin, params={"since": 10**40}
        ).status_code
        == 400
    )


def test_snapshot_pagination_keeps_first_watermark_and_rechecks_acl(client):
    h = headers(client)
    peer = register_friend(client, h, "snapshot@test.com", "分页同学")
    uid = client.get("/api/v1/auth/me", headers=peer).json()["data"]["id"]
    # Include a legacy record with no change-log entry: initial snapshots must retain it.
    with client.app.state.session_factory() as db:
        for i in range(201):
            db.add(
                LearningRecord(
                    user_id=uid,
                    id=f"t{i:03}",
                    body=json.dumps(
                        {"id": f"t{i:03}", "type": "task", "title": "原记录"}
                    ),
                    revision=1,
                )
            )
        db.commit()
    base = f"/api/v1/group/members/{uid}/learning"
    page = client.get(base, headers=h).json()["data"]
    assert len(page["items"]) == 200 and page["next"] == "t199"
    change(client, peer, "t001", 1, None)
    change(client, peer, "t200", 1, {"id": "t200", "type": "task", "title": "更新"})
    last = client.get(base, headers=h, params={"after": page["next"]}).json()["data"]
    assert last["items"][0]["title"] == "更新"
    delta = client.get(
        base + "/changes", headers=h, params={"since": page["cursor"]}
    ).json()["data"]
    assert {"id": "t001", "record": None} in delta["items"]
    assert (
        client.put(
            "/api/v1/users/me", headers=peer, json={"is_private_mode": True}
        ).status_code
        == 200
    )
    assert (
        client.get(
            base + "/changes", headers=h, params={"since": delta["cursor"]}
        ).status_code
        == 404
    )
    assert client.get(base + "/changes", headers=peer).status_code == 200
    assert (
        client.put(
            "/api/v1/users/me", headers=peer, json={"is_private_mode": False}
        ).status_code
        == 200
    )
    assert (
        client.delete(f"/api/v1/admin/group-members/{uid}", headers=h).status_code
        == 200
    )
    assert client.get(base + "/changes", headers=h).status_code == 404


def test_change_paging_advances_over_private_entries(client):
    h = headers(client)
    with client.app.state.session_factory() as db:
        for i in range(201):
            db.add(
                LearningChange(
                    user_id=1,
                    record_id=f"private-{i}",
                    record_type="profile",
                    revision=1,
                )
            )
        db.commit()
    base = "/api/v1/group/members/1/learning/changes"
    page = client.get(base, headers=h).json()["data"]
    assert page["has_more"] and page["items"] == []
    last = client.get(base, headers=h, params={"since": page["cursor"]}).json()["data"]
    assert not last["has_more"] and last["cursor"] > page["cursor"]


def test_bullet_pool_requires_admin_author_and_approval(client):
    h = headers(client)
    peer = register_friend(client, h, "bullet@test.com", "投稿同学")
    uid = client.get("/api/v1/auth/me", headers=peer).json()["data"]["id"]
    with client.app.state.session_factory() as db:
        for owner, status, content in [
            (1, "approved", "管理员已审核"),
            (1, "pending", "未审核"),
            (uid, "approved", "用户已审核"),
        ]:
            db.add(Inspiration(user_id=owner, status=status, content=content))
        db.commit()
    rows = client.get("/api/v1/inspirations/bullets").json()["data"]
    assert [row["content"] for row in rows] == ["管理员已审核"]
    assert set(rows[0]) == {"id", "content"}


def test_bullet_preference_sync_is_personal(client):
    h = headers(client)
    push(
        client,
        h,
        [
            {
                "id": "learning-settings",
                "key": "learning-settings",
                "type": "preferences",
                "value": {"bulletEnabled": False},
            }
        ],
    )
    with client.app.state.session_factory() as db:
        value = json.loads(db.get(LearningRecord, (1, "learning-settings")).body)[
            "value"
        ]
        assert value["bulletEnabled"] is False and value["focusMin"] == 25
    shared = client.get("/api/v1/group/members/1/learning", headers=h).json()["data"]
    assert all(row["type"] != "preferences" for row in shared["items"])
