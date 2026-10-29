import json
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from app.config import Settings
from app.errors import ApiError
from app.tests.conftest import login
from app.tests.test_admin import ADMIN, h, make_member
from app.services.persistent_transient import PersistentTransientStore
from app.services.transient import digest
from app.services.sms import send_sms


def test_shared_state_restart_atomic_consumption_and_limits(client):
    first = client.app.state.transient
    second = PersistentTransientStore(
        client.app.state.session_factory, client.app.state.secret
    )
    first.set("one-time-ticket", "private-token", 300)
    with ThreadPoolExecutor(2) as pool:
        values = list(
            pool.map(lambda store: store.consume("one-time-ticket"), [first, second])
        )
    assert sorted(x for x in values if x) == ["private-token"]
    first.limit("limit-test", 1, 60)
    with pytest.raises(ApiError):
        second.limit("limit-test", 1, 60)
    first.set("code-test", digest("123456"), 300)
    for _ in range(5):
        assert not second.verify("code-test", digest("bad"))
    assert not first.verify("code-test", digest("123456"))
    from sqlalchemy import text

    with client.app.state.engine.connect() as connection:
        assert "private-token" not in str(
            connection.execute(text("select value_cipher from transient_states")).all()
        )


def test_tencent_sms_request_and_provider_errors(monkeypatch):
    settings = Settings(
        _env_file=None,
        environment="production",
        sms_provider="tencent",
        sms_secret_id="id",
        sms_secret_key="secret",
        sms_sdk_app_id="app",
        sms_sign_name="研时",
        sms_template_id="template",
    )
    captured = {}

    def post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return httpx.Response(
            200, json={"Response": {"SendStatusSet": [{"Code": "Ok"}]}}
        )

    monkeypatch.setattr("app.services.sms.httpx.post", post)
    monkeypatch.setattr("app.services.sms.time.time", lambda: 1700000000)
    send_sms(settings, "13800138000", "123456")
    assert captured["url"] == "https://sms.tencentcloudapi.com/"
    assert json.loads(captured["content"])["PhoneNumberSet"] == ["+8613800138000"]
    assert captured["headers"]["X-TC-Version"] == "2021-01-11"
    assert captured["headers"]["Authorization"].startswith(
        "TC3-HMAC-SHA256 Credential=id/2023-11-14/sms/tc3_request"
    )
    monkeypatch.setattr(
        "app.services.sms.httpx.post",
        lambda *a, **k: httpx.Response(
            200, json={"Response": {"SendStatusSet": [{"Code": "FailedOperation"}]}}
        ),
    )
    with pytest.raises(ApiError):
        send_sms(settings, "13800138000", "123456")
    settings.sms_provider = ""
    with pytest.raises(ApiError):
        send_sms(settings, "13800138000", "123456")


def test_oauth_requires_browser_state_cookie_and_consumes_it(client, monkeypatch):
    settings = client.app.state.settings
    settings.auth_channels, settings.qq_app_id = "email,qq", "test-app"

    async def profile(*args):
        return "provider-uid-001", "QQ学友", ""

    monkeypatch.setattr("app.routers.oauth._qq_profile", profile)
    callback = "/api/v1/auth/oauth/qq/callback"
    assert (
        client.get(callback, params={"code": "code", "format": "json"}).status_code
        == 400
    )
    state = client.get(
        "/api/v1/auth/oauth/qq/authorize", params={"accepted_terms": True}
    ).json()["data"]["state"]
    cookie = client.cookies.get("yanshi_oauth_state")
    client.cookies.clear()
    assert (
        client.get(
            callback, params={"code": "code", "state": state, "format": "json"}
        ).status_code
        == 400
    )
    client.cookies.set("yanshi_oauth_state", cookie, path="/api/v1/auth/oauth")
    result = client.get(
        callback, params={"code": "code", "state": state, "format": "json"}
    )
    assert result.status_code == 200, result.text
    assert (
        client.get(
            callback, params={"code": "code", "state": state, "format": "json"}
        ).status_code
        == 400
    )


def test_phone_binding_requires_scoped_code_and_prevents_account_takeover(
    client, monkeypatch
):
    ah = h(login(client, **ADMIN)["access_token"])
    member = make_member(client, ah, "phone@test.com")
    mh = h(login(client, "phone@test.com", "Friend2028")["access_token"])
    assert (
        client.post(
            "/api/v1/users/me/phone/send-code",
            headers=mh,
            json={"phone": "13800138000"},
        ).status_code
        == 403
    )
    client.app.state.settings.auth_channels = "email,phone"
    store = client.app.state.transient
    store.set("phone-code:" + digest("13800138000"), digest("123456"), 300)
    assert (
        client.put(
            "/api/v1/users/me/phone",
            headers=mh,
            json={"phone": "13800138000", "code": "123456"},
        ).status_code
        == 400
    )
    store.set(
        f"bind-phone:{member['id']}:" + digest("13800138000"), digest("123456"), 300
    )
    assert (
        client.put(
            "/api/v1/users/me/phone",
            headers=mh,
            json={"phone": "13800138000", "code": "123456"},
        ).status_code
        == 200
    )
    store.set("bind-phone:1:" + digest("13800138000"), digest("123456"), 300)
    assert (
        client.put(
            "/api/v1/users/me/phone",
            headers=ah,
            json={"phone": "13800138000", "code": "123456"},
        ).status_code
        == 409
    )


def test_room_type_closed_open_authorized_and_all_api_gates(client):
    ah = h(login(client, **ADMIN)["access_token"])
    make_member(client, ah, "roomtype@test.com")
    mh = h(login(client, "roomtype@test.com", "Friend2028")["access_token"])
    payload = {
        "name": "video room",
        "room_type": "video_small_room",
        "accept_sharing": True,
    }
    assert client.post("/api/v1/rooms", headers=mh, json=payload).status_code == 403
    client.app.state.settings.features += ",video_small_room"
    assert client.post("/api/v1/rooms", headers=mh, json=payload).status_code == 403
    client.put(
        "/api/v1/admin/members/2",
        headers=ah,
        json={"vip_action": "permanent", "note": "room type test"},
    )
    row = client.post("/api/v1/rooms", headers=mh, json=payload).json()["data"]
    assert row["room_type"] == "video_small_room"
    assert client.get(f"/api/v1/rooms/{row['id']}", headers=mh).status_code == 200
    client.app.state.settings.features = "checkin_room"
    assert client.get(f"/api/v1/rooms/{row['id']}", headers=mh).status_code == 403
    assert (
        client.post(
            f"/api/v1/rooms/{row['id']}/heartbeat", headers=mh, json={"status": "idle"}
        ).status_code
        == 403
    )
    assert client.get("/api/v1/resources", headers=mh).status_code == 403


def test_account_capacity_is_independent_from_room_and_diagnostics_redacted(client):
    ah = h(login(client, **ADMIN)["access_token"])
    client.app.state.settings.account_max_users = 1
    assert (
        client.post(
            "/api/v1/admin/members",
            headers=ah,
            json={
                "email": "extra@test.com",
                "nickname": "extra",
                "password": "Friend2028",
            },
        ).status_code
        == 403
    )
    client.app.state.settings.account_max_users = 0
    for i in range(5):
        make_member(client, ah, f"extra{i}@test.com")
    assert len(client.get("/api/v1/admin/members", headers=ah).json()["data"]) == 6
    client.app.state.settings.sms_secret_key = "secret-must-never-be-returned"
    response = client.get("/api/v1/admin/diagnostics", headers=ah)
    assert (
        response.status_code == 200
        and "secret-must-never-be-returned" not in response.text
    )
    assert (
        client.get("/health/ready").status_code == 503
    )  # create_all测试库没有alembic版本，不可假报可上线。
