import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError
from app.tests.test_sync import headers
from app.models import SessionFact, LearningRecord


def send(c, h, rows):
    return c.post(
        "/api/v1/sync/commands",
        headers=h,
        json={
            "operationId": uuid.uuid4().hex,
            "changes": [
                {"id": r["id"], "expectedRevision": 0, "record": r} for r in rows
            ],
        },
    )


def record(key="valid"):
    end = int(datetime.now(timezone.utc).timestamp() * 1000)
    return {
        "id": key,
        "type": "session",
        "mode": "timer",
        "status": "done",
        "startedAt": end - 1500000,
        "endedAt": end,
        "plannedMin": 25,
        "pauseAccum": 0,
        "actualSec": 999999,
        "date": "1999-01-01",
    }


def test_invalid_session_never_enters_storage(client):
    h = headers(client)
    rows = [
        {"id": "missing", "type": "session", "actualSec": 999999},
        {**record("old"), "startedAt": 1700000000000},
        {**record("bad"), "endedAt": 0},
    ]
    for r in rows:
        assert send(client, h, [r]).status_code == 422
    with client.app.state.session_factory() as db:
        assert all(db.get(LearningRecord, (1, r["id"])) is None for r in rows)


def test_duration_date_and_database_constraints(client):
    h = headers(client)
    response = send(client, h, [record()])
    assert response.status_code == 200, response.text
    r = response.json()["data"]["changed"][0]["record"]
    assert r["actualSec"] == 1500 and r["date"] != "1999-01-01"
    with client.app.state.session_factory() as db:
        assert db.get(SessionFact, (1, "valid")).actual_sec == 1500
        with pytest.raises(IntegrityError):
            db.add(
                SessionFact(
                    user_id=1,
                    record_id="direct",
                    started_at=0,
                    ended_at=1,
                    actual_sec=999999,
                    study_date="1999-01-01",
                )
            )
            db.commit()


def test_overlap_retained_but_not_counted(client):
    h = headers(client)
    a = record("overlap-a")
    response = send(client, h, [a, {**a, "id": "overlap-b"}])
    assert response.status_code == 200, response.text
    assert all(
        r["record"]["conflict_flag"] and r["record"]["actualSec"] == 0
        for r in response.json()["data"]["changed"]
    )
    with client.app.state.session_factory() as db:
        assert all(
            db.get(LearningRecord, (1, k)).deleted == 0
            and db.get(SessionFact, (1, k)).conflict
            for k in ["overlap-a", "overlap-b"]
        )

    from app.services.ai_context import account_context

    with client.app.state.session_factory() as db:
        assert account_context(db, 1)["session_issues"]["excluded"] == 2


def test_global_lease_excludes_second_device_and_release_is_scoped(client):
    h = headers(client)
    a = record()
    body = {
        "session_id": "lease-a",
        "device_id": "desktop",
        "started_at": a["startedAt"],
    }
    assert client.post("/api/v1/timer/start", headers=h, json=body).status_code == 200
    assert client.post("/api/v1/timer/start", headers=h, json=body).status_code == 200
    peer = {**body, "session_id": "lease-b", "device_id": "phone"}
    denied = client.post("/api/v1/timer/start", headers=h, json=peer)
    assert denied.status_code == 409
    assert denied.json()["data"]["current"]["session_id"] == "lease-a"
    assert client.post("/api/v1/timer/release", headers=h, json=peer).status_code == 200
    assert (
        client.get("/api/v1/timer/current", headers=h).json()["data"]["session_id"]
        == "lease-a"
    )
    assert client.post("/api/v1/timer/release", headers=h, json=body).status_code == 200
    assert client.post("/api/v1/timer/start", headers=h, json=peer).status_code == 200


def test_overlap_resolution_needs_confirmation_and_unchanged_versions(client):
    h = headers(client)
    a = record("resolve-a")
    assert send(client, h, [a, {**a, "id": "resolve-b"}]).status_code == 200
    data = client.get("/api/v1/timer/conflicts", headers=h).json()["data"]
    group = data["groups"][0]
    body = {
        "group_id": group["id"],
        "keep_id": "resolve-a",
        "versions": {i["id"]: i["revision"] for i in group["items"]},
        "confirmed": False,
    }
    assert client.post("/api/v1/timer/resolve", headers=h, json=body).status_code == 400
    assert (
        client.post(
            "/api/v1/timer/resolve",
            headers=h,
            json={**body, "confirmed": True, "versions": {}},
        ).status_code
        == 409
    )
    result = client.post(
        "/api/v1/timer/resolve", headers=h, json={**body, "confirmed": True}
    )
    assert result.status_code == 200, result.text
    rows = client.get("/api/v1/sync/records", headers=h).json()["data"]["records"]
    by = {r["id"]: r for r in rows}
    assert (
        by["resolve-a"]["record"]["actualSec"] == 1500
        and not by["resolve-a"]["record"]["conflict_flag"]
    )
    assert by["resolve-b"]["record"] is None
    assert not client.get("/api/v1/timer/conflicts", headers=h).json()["data"]["groups"]


def test_strict_byok_ignores_platform_key_and_keeps_private_history(
    client, monkeypatch
):
    h = headers(client)
    client.app.state.settings.volc_api_key = "must-not-be-used"
    client.put(
        "/api/v1/admin/members/1",
        headers=h,
        json={"vip_action": "permanent", "note": "owner test"},
    )
    assert not client.get("/api/v1/ai/enabled", headers=h).json()["data"]["enabled"]
    assert (
        client.post(
            "/api/v1/ai/chat", headers=h, json={"content": "不应使用平台Key"}
        ).status_code
        == 400
    )
    assert client.get("/api/v1/ai/conversations", headers=h).status_code == 200


def test_two_devices_racing_for_global_timer_have_exactly_one_winner(client):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    h = headers(client)
    gate = Barrier(2)
    started = record()["startedAt"]

    def claim(i):
        gate.wait(timeout=5)
        return client.post(
            "/api/v1/timer/start",
            headers=h,
            json={
                "session_id": f"concurrent-{i}",
                "device_id": f"device-{i}",
                "started_at": started,
            },
        ).status_code

    with ThreadPoolExecutor(2) as pool:
        codes = list(pool.map(claim, range(2)))
    assert sorted(codes) == [200, 409]


def test_expired_timer_can_recover_but_old_device_cannot_release_new_lease(
    client, monkeypatch
):
    from datetime import timedelta
    from app.time import utcnow

    h = headers(client)
    now = utcnow()
    a = {
        "session_id": "expired",
        "device_id": "old",
        "started_at": record()["startedAt"],
    }
    assert client.post("/api/v1/timer/start", headers=h, json=a).status_code == 200
    monkeypatch.setattr(
        "app.routers.timer.utcnow", lambda: now + timedelta(seconds=130)
    )
    b = {**a, "session_id": "recovered", "device_id": "new"}
    assert client.post("/api/v1/timer/start", headers=h, json=b).status_code == 200
    assert client.put("/api/v1/timer/heartbeat", headers=h, json=a).status_code == 409
    client.post("/api/v1/timer/release", headers=h, json=a)
    assert (
        client.get("/api/v1/timer/current", headers=h).json()["data"]["session_id"]
        == "recovered"
    )
