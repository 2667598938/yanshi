from sqlalchemy import select
from app.models import User, StudyGroupMember, RoomMember, GroupInvite
from app.tests.test_sync import headers
from app.tests.conftest import login
from app.services.security import hash_password


def applicant(client):
    with client.app.state.session_factory() as db:
        user = User(
            email="candidate@test.com",
            nickname="申请人",
            password_hash=hash_password("Candidate2026!"),
        )
        db.add(user)
        db.commit()
        uid = user.id
    token = login(client, "candidate@test.com", "Candidate2026!")["access_token"]
    return uid, {"Authorization": "Bearer " + token}


def test_invite_requires_review_and_grants_only_group_membership(client):
    admin = headers(client)
    uid, h = applicant(client)
    created = client.post(
        "/api/v1/group-admission/invites", headers=admin, json={"target_user_id": uid}
    )
    assert created.status_code == 200, created.text
    invite = created.json()["data"]
    # A group token is not a VIP token and grants nothing by itself.
    assert (
        client.post(
            "/api/v1/vip/redeem", headers=h, json={"code": invite["code"]}
        ).status_code
        == 400
    )
    body = {"code": invite["code"], "reason": "一起学习"}
    apply = client.post("/api/v1/group-admission/applications", headers=h, json=body)
    assert apply.status_code == 200, apply.text
    row = apply.json()["data"]
    assert (
        client.post(
            "/api/v1/group-admission/applications", headers=h, json=body
        ).json()["data"]["id"]
        == row["id"]
    )
    assert client.get("/api/v1/group/members", headers=h).json()["data"] == []
    review = {"approve": True, "expected_revision": row["revision"]}
    assert (
        client.post(
            f"/api/v1/group-admission/applications/{row['id']}/review",
            headers=h,
            json=review,
        ).status_code
        == 403
    )
    result = client.post(
        f"/api/v1/group-admission/applications/{row['id']}/review",
        headers=admin,
        json=review,
    )
    assert result.status_code == 200, result.text
    assert (
        client.post(
            f"/api/v1/group-admission/applications/{row['id']}/review",
            headers=admin,
            json=review,
        ).status_code
        == 409
    )
    with client.app.state.session_factory() as db:
        assert db.get(StudyGroupMember, (1, uid))
        assert db.scalar(select(RoomMember.id).where(RoomMember.user_id == uid)) is None
        user = db.get(User, uid)
        assert not user.vip_until and not user.vip_permanent
        stored = db.get(GroupInvite, invite["id"])
        assert invite["code"] not in stored.token_hash


def test_withdraw_revoke_and_reject_have_version_checks(client):
    admin = headers(client)
    uid, h = applicant(client)
    invite = client.post(
        "/api/v1/group-admission/invites", headers=admin, json={}
    ).json()["data"]
    row = client.post(
        "/api/v1/group-admission/applications", headers=h, json={"code": invite["code"]}
    ).json()["data"]
    path = f"/api/v1/group-admission/applications/{row['id']}"
    assert (
        client.post(
            path + "/withdraw", headers=h, json={"expected_revision": 1}
        ).status_code
        == 200
    )
    assert (
        client.post(
            path + "/review",
            headers=admin,
            json={"approve": True, "expected_revision": 1},
        ).status_code
        == 409
    )
    new = client.post(
        "/api/v1/group-admission/applications", headers=h, json={"code": invite["code"]}
    ).json()["data"]
    assert (
        client.post(
            f"/api/v1/group-admission/invites/{invite['id']}/revoke",
            headers=admin,
            json={},
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/group-admission/mine", headers=h).json()["data"][
            "applications"
        ][0]["status"]
        == "rejected"
    )
    assert (
        client.post(
            f"/api/v1/group-admission/applications/{new['id']}/review",
            headers=admin,
            json={"approve": True, "expected_revision": 1},
        ).status_code
        == 409
    )
    with client.app.state.session_factory() as db:
        assert db.get(StudyGroupMember, (1, uid)) is None


def test_registration_and_vip_codes_never_grant_group_or_room_membership(client):
    from app.tests.conftest import read_latest_code

    admin = headers(client)
    for index, days in enumerate([0, 30]):
        code = client.post(
            "/api/v1/admin/invites", headers=admin, json={"vip_days": days}
        ).json()["data"]
        assert code["kind"] == ("vip_only" if days else "register_only")
        email = f"code-user-{index}@test.com"
        assert (
            client.post(
                "/api/v1/auth/email-code", json={"email": email, "scene": "register"}
            ).status_code
            == 200
        )
        verify = read_latest_code(client.app.state.settings.mail_directory)
        created = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "code": verify,
                "password": "Register2026!",
                "nickname": "注册同学",
                "invite_code": code["code"],
                "accepted_terms": True,
            },
        )
        assert created.status_code == 200, created.text
        uid = created.json()["data"]["user"]["id"]
        with client.app.state.session_factory() as db:
            assert db.get(StudyGroupMember, (1, uid)) is None
            assert (
                db.scalar(select(RoomMember.id).where(RoomMember.user_id == uid))
                is None
            )
            user = db.get(User, uid)
            assert not user.vip_permanent and bool(user.vip_until) == bool(days)
    assert (
        client.post(
            "/api/v1/admin/invites",
            headers=admin,
            json={"kind": "combine", "vip_days": 30},
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/admin/invites", headers=admin, json={"kind": "group_invite"}
        ).status_code
        == 400
    )
