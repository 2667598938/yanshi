"""Room friendship, isolation, consent, revocation, and shared-network safety."""

import json

from sqlalchemy import event, select
from app.models import (
    User,
    Room,
    RoomMember,
    StudyGroup,
    StudyGroupMember,
    LearningRecord,
    SessionFact,
    LearningChange,
)
from app.tests.conftest import login
from app.tests.test_group_v1 import push


def admin(client):
    return {
        "Authorization": "Bearer "
        + login(client, "admin@test.com", "Admin2028")["access_token"]
    }


def account(client, owner, n):
    email = f"circle-{n}@test.com"
    r = client.post(
        "/api/v1/admin/members",
        headers=owner,
        json={"email": email, "nickname": f"好友{n}", "password": "Circle2026!"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"], {
        "Authorization": "Bearer " + login(client, email, "Circle2026!")["access_token"]
    }


def room(client, h, name="好友房间", visibility="private"):
    r = client.post(
        "/api/v1/rooms",
        headers=h,
        json={"name": name, "visibility": visibility, "accept_sharing": True},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def join(client, h, r):
    result = client.post(
        f"/api/v1/rooms/{r['id']}/join",
        headers=h,
        json={"code": r["code"], "accept_sharing": True},
    )
    assert result.status_code == 200, result.text
    return result.json()["data"]


def test_admin_account_creation_grants_no_room_or_group_even_with_legacy_rows(client):
    ah = admin(client)
    aid, a = account(client, ah, 1)
    bid, b = account(client, ah, 2)
    with client.app.state.session_factory() as db:
        assert (
            db.scalars(
                select(RoomMember).where(RoomMember.user_id.in_([aid, bid]))
            ).all()
            == []
        )
        assert db.scalars(select(StudyGroupMember)).all() == []
        db.add(StudyGroup(id=1, name="旧全站组"))
        db.flush()
        db.add_all([StudyGroupMember(group_id=1, user_id=uid) for uid in [1, aid, bid]])
        db.commit()
    push(client, a, [{"id": "secret", "type": "task", "title": "陌生人的私密任务"}])
    assert client.get("/api/v1/rooms", headers=a).json()["data"] == []
    assert client.get("/api/v1/group/members", headers=a).json()["data"] == []
    for viewer in [ah, b]:
        assert (
            client.get(
                f"/api/v1/group/members/{aid}/learning", headers=viewer
            ).status_code
            == 404
        )
    assert (
        client.get(f"/api/v1/group/members/{aid}/learning", headers=a).status_code
        == 200
    )


def test_rooms_isolate_friends_without_transitive_access(client):
    ah = admin(client)
    aid, a = account(client, ah, 1)
    bid, b = account(client, ah, 2)
    cid, c = account(client, ah, 3)
    ra = room(client, a, "甲的好友房")
    rb = room(client, b, "乙的好友房")
    join(client, c, ra)
    push(client, b, [{"id": "b-task", "type": "task", "title": "乙的学习安排"}])
    path = f"/api/v1/group/members/{bid}/learning"
    assert client.get(path, headers=a).status_code == 404
    assert client.get(path, headers=c).status_code == 404
    # A joins B's room; this does not make A's friend C a member of B's room.
    join(client, a, rb)
    assert client.get(path, headers=a).status_code == 200
    assert client.get(path, headers=c).status_code == 404
    assert client.get(path, headers=a, params={"room_id": ra["id"]}).status_code == 404
    assert (
        client.get(
            path + "/changes", headers=a, params={"room_id": ra["id"]}
        ).status_code
        == 404
    )
    assert client.get(path, headers=a, params={"room_id": rb["id"]}).status_code == 200
    assert {
        u["id"]
        for u in client.get(
            "/api/v1/group/members", headers=a, params={"room_id": ra["id"]}
        ).json()["data"]
    } == {aid, cid}


def test_public_room_requires_invitation_or_owner_approval_before_any_member_data(
    client,
):
    ah = admin(client)
    aid, a = account(client, ah, 1)
    bid, b = account(client, ah, 2)
    r = room(client, a, visibility="public")
    rid = r["id"]
    push(client, a, [{"id": "history", "type": "task", "title": "加入前的历史任务"}])
    assert client.get(f"/api/v1/rooms/{rid}", headers=b).status_code == 403
    preview = client.get(f"/api/v1/rooms/{rid}/preview", headers=b).json()["data"]
    assert preview["room"]["code"] == "" and preview["room"]["online_count"] == 0
    assert "members" not in preview and "ranking" not in preview
    assert (
        client.post(
            f"/api/v1/rooms/{rid}/join", headers=b, json={"accept_sharing": True}
        ).status_code
        == 403
    )
    request = client.post(
        f"/api/v1/rooms/{rid}/apply", headers=b, json={"accept_sharing": True}
    ).json()["data"]
    assert (
        client.get(f"/api/v1/group/members/{aid}/learning", headers=b).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/rooms/{rid}/applies/{request['id']}/review",
            headers=a,
            json={"approve": True},
        ).status_code
        == 200
    )
    result = client.get(f"/api/v1/group/members/{aid}/learning", headers=b).json()[
        "data"
    ]["items"]
    assert result[0]["title"] == "加入前的历史任务"


def test_explicit_consent_required_on_all_sharing_operations(client):
    ah = admin(client)
    _, a = account(client, ah, 1)
    assert (
        client.post("/api/v1/rooms", headers=a, json={"name": "尚未确认"}).status_code
        == 400
    )
    r = room(client, ah)
    for path, body in [
        (f"/api/v1/rooms/{r['id']}/join", {"code": r["code"]}),
        ("/api/v1/rooms/join-by-code", {"code": r["code"]}),
        (f"/api/v1/rooms/{r['id']}/apply", {}),
    ]:
        assert client.post(path, headers=a, json=body).status_code == 400
    assert client.get("/api/v1/group/members", headers=a).json()["data"] == []


def test_legacy_room_members_must_both_confirm_and_privacy_still_wins(client):
    ah = admin(client)
    uid, a = account(client, ah, 1)
    with client.app.state.session_factory() as db:
        r = db.scalar(select(Room).order_by(Room.id))
        rid = r.id
        db.add(RoomMember(room_id=rid, user_id=uid))
        db.commit()
    push(client, a, [{"id": "old", "type": "task", "title": "历史学习数据"}])
    path = f"/api/v1/group/members/{uid}/learning"
    assert client.get(path, headers=ah).status_code == 404
    assert (
        client.post(
            f"/api/v1/rooms/{rid}/sharing/confirm",
            headers=ah,
            json={"accept_sharing": True},
        ).status_code
        == 200
    )
    assert client.get(path, headers=ah).status_code == 404
    assert (
        client.post(
            f"/api/v1/rooms/{rid}/sharing/confirm",
            headers=a,
            json={"accept_sharing": True},
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/rooms/{rid}/join", headers=a, json={"accept_sharing": True}
        ).status_code
        == 403
    )
    invitation = client.get(f"/api/v1/rooms/{rid}", headers=ah).json()["data"]["room"][
        "code"
    ]
    assert (
        client.post(
            f"/api/v1/rooms/{rid}/join",
            headers=a,
            json={"code": invitation, "accept_sharing": True},
        ).status_code
        == 200
    )
    assert client.get(path, headers=ah).status_code == 200
    client.put("/api/v1/users/me", headers=a, json={"is_private_mode": True})
    assert client.get(path, headers=ah).status_code == 404
    assert client.get(path, headers=a).status_code == 200
    data = client.get(f"/api/v1/rooms/{rid}", headers=ah).json()["data"]
    peer = next(m for m in data["members"] if m["user_id"] == uid)
    assert peer["presence"] == {"status": "private"} and "today_sec" not in peer


def test_platform_admin_cannot_self_approve_or_manage_someone_elses_room(client):
    ah = admin(client)
    _, a = account(client, ah, 1)
    r = room(client, a, visibility="public")
    rid = r["id"]
    request = client.post(
        f"/api/v1/rooms/{rid}/apply", headers=ah, json={"accept_sharing": True}
    ).json()["data"]
    assert client.get(f"/api/v1/rooms/{rid}/applies", headers=ah).status_code == 403
    assert (
        client.post(
            f"/api/v1/rooms/{rid}/applies/{request['id']}/review",
            headers=ah,
            json={"approve": True},
        ).status_code
        == 403
    )
    assert client.post(f"/api/v1/rooms/{rid}/code", headers=ah).status_code == 403
    assert (
        client.patch(
            f"/api/v1/rooms/{rid}", headers=ah, json={"visibility": "public"}
        ).status_code
        == 403
    )
    assert client.delete(f"/api/v1/rooms/{rid}", headers=ah).status_code == 403
    assert client.get(f"/api/v1/rooms/{rid}", headers=ah).status_code == 403


def test_kick_rotates_invite_code_and_revokes_learning_and_incremental_access(client):
    ah = admin(client)
    uid, a = account(client, ah, 1)
    r = room(client, ah)
    join(client, a, r)
    push(client, ah, [{"id": "private-again", "type": "task", "title": "退出后不能看"}])
    assert client.get("/api/v1/group/members/1/learning", headers=a).status_code == 200
    assert (
        client.delete(f"/api/v1/rooms/{r['id']}/members/{uid}", headers=ah).status_code
        == 200
    )
    assert client.get("/api/v1/group/members/1/learning", headers=a).status_code == 404
    assert (
        client.get("/api/v1/group/members/1/learning/changes", headers=a).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/rooms/join-by-code",
            headers=a,
            json={"code": r["code"], "accept_sharing": True},
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/rooms/{r['id']}/preview", headers=a).json()["data"][
            "room"
        ]["code"]
        == ""
    )


def test_leaving_last_common_room_revokes_access_but_other_common_room_remains(client):
    ah = admin(client)
    _, a = account(client, ah, 1)
    r1 = room(client, ah, "共同房间一")
    r2 = room(client, ah, "共同房间二")
    join(client, a, r1)
    join(client, a, r2)
    assert client.post(f"/api/v1/rooms/{r1['id']}/leave", headers=a).status_code == 200
    assert client.get("/api/v1/group/members/1/learning", headers=a).status_code == 200
    assert client.delete(f"/api/v1/rooms/{r2['id']}", headers=ah).status_code == 200
    assert client.get("/api/v1/group/members/1/learning", headers=a).status_code == 404


def test_failed_logins_from_ten_other_accounts_do_not_lock_shared_network(client):
    for i in range(10):
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": f"wrong{i}@test.com", "password": "Incorrect2026!"},
            ).status_code
            == 401
        )
    # Persisted IP locks from the old release must not strand valid users either.
    client.app.state.transient.set("locked:login-ip:testclient", "1", 900)
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin2028"},
        ).status_code
        == 200
    )


def test_shared_network_has_a_short_request_limit_instead_of_long_global_lock(client):
    for i in range(60):
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": f"wrong{i}@test.com", "password": "Incorrect2026!"},
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": "admin@test.com", "password": "Admin2028"},
        ).status_code
        == 429
    )


def test_100_member_room_list_and_presence_use_constant_number_of_queries(client):
    ah = admin(client)
    r = room(client, ah, "百人规模查询检查")
    with client.app.state.session_factory() as db:
        password = db.get(User, 1).password_hash
        for i in range(99):
            u = User(
                email=f"scale{i}@test.com", nickname=f"规模{i}", password_hash=password
            )
            db.add(u)
            db.flush()
            db.add(RoomMember(room_id=r["id"], user_id=u.id, sharing_confirmed=True))
            for n in range(20):
                key = f"s-{i}-{n}"
                start = 1767225600000 + n * 120000
                db.add(
                    LearningRecord(
                        user_id=u.id,
                        id=key,
                        body=json.dumps(
                            {
                                "id": key,
                                "type": "session",
                                "mode": "timer",
                                "actualSec": 60,
                                "plannedMin": 1,
                                "status": "done",
                                "date": "2026-01-01",
                                "startedAt": start,
                                "endedAt": start + 60000,
                            }
                        ),
                    )
                )
                if i == 0:
                    db.add(
                        LearningChange(
                            user_id=u.id,
                            record_id=key,
                            record_type="session",
                            revision=1,
                        )
                    )
                db.add(
                    SessionFact(
                        user_id=u.id,
                        record_id=key,
                        started_at=start,
                        ended_at=start + 60000,
                        actual_sec=60,
                        study_date="2026-01-01",
                    )
                )
        db.commit()
    statements = []

    def count(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    engine = client.app.state.engine
    event.listen(engine, "before_cursor_execute", count)
    try:
        members = client.get(
            "/api/v1/group/members", headers=ah, params={"room_id": r["id"]}
        )
        assert members.status_code == 200 and len(members.json()["data"]) == 100
        assert len(statements) < 15, len(statements)
        statements.clear()
        state = client.get(f"/api/v1/rooms/{r['id']}", headers=ah)
        assert state.status_code == 200 and len(state.json()["data"]["members"]) == 100
        assert len(statements) < 20, len(statements)
        assert (
            sum(m["total_sec"] for m in state.json()["data"]["members"]) == 99 * 20 * 60
        )
        for path in [
            "/api/v1/group/members/2/learning",
            "/api/v1/group/members/2/learning/changes",
        ]:
            statements.clear()
            response = client.get(path, headers=ah)
            assert (
                response.status_code == 200
                and len(response.json()["data"]["items"]) == 20
            )
            assert len(statements) < 15, len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", count)


def test_seed_never_rejoins_or_creates_friendship_on_redeployment(client):
    from app.seed import seed
    from sqlalchemy import delete

    with client.app.state.session_factory() as db:
        db.execute(delete(RoomMember))
        db.commit()
        seed(db, client.app.state.settings, echo=lambda *args: None)
        assert db.scalars(select(RoomMember)).all() == []
        assert db.scalars(select(StudyGroupMember)).all() == []


def test_old_pending_application_cannot_be_approved_until_applicant_reconfirms(client):
    from app.models import RoomJoinApply

    ah = admin(client)
    _, a = account(client, ah, 1)
    r = room(client, ah, visibility="public")
    path = f"/api/v1/rooms/{r['id']}"
    applied = client.post(
        path + "/apply", headers=a, json={"accept_sharing": True, "message": "旧说明"}
    ).json()["data"]
    with client.app.state.session_factory() as db:
        db.get(RoomJoinApply, applied["id"]).accept_sharing = False
        db.commit()
    review = path + f"/applies/{applied['id']}/review"
    assert client.post(review, headers=ah, json={"approve": True}).status_code == 409
    revised = client.post(
        path + "/apply",
        headers=a,
        json={"accept_sharing": True, "message": "已了解共享范围"},
    ).json()["data"]
    assert (
        revised["id"] == applied["id"]
        and revised["accept_sharing"]
        and revised["message"] == "已了解共享范围"
    )
    assert client.post(review, headers=ah, json={"approve": True}).status_code == 200
