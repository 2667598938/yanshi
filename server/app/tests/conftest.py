import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.database import Base
from app.main import create_app
from app.seed import seed


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        database_url="sqlite:///" + (tmp_path / "test.sqlite").as_posix(),
        environment="test",
        auth_password_only=False,  # 旧渠道回归显式开放；默认内测策略有独立边界测试。
        mail_console=True,
        mail_directory=tmp_path / "mail",
        image_directory=tmp_path / "uploads",
        volc_api_key="",  # 测试禁用真实 AI，用例内 monkeypatch
        admin_email="admin@test.com",
        admin_password="Admin2028",
        auth_email_domains="",  # 测试环境不限制邮箱域名
        registration_open=True,  # 注册用例显式启用；产品首次初始化默认关闭。
        account_max_users=0,  # 房间用例需构造第5个账号；账号名额另有独立验收用例。
    )
    app = create_app(settings)
    Base.metadata.create_all(bind=app.state.engine)
    session_factory = app.state.session_factory
    with session_factory() as db:
        seed(db, settings, echo=lambda *a: None)
        # Test participants explicitly have an initial private friend room. Seed
        # itself creates no room or sharing membership in a real deployment.
        from app.models import Room, RoomMember

        room = Room(
            code="TEST01",
            name="测试好友房",
            owner_id=1,
            visibility="private",
            capacity=0,
        )
        db.add(room)
        db.flush()
        db.add(
            RoomMember(room_id=room.id, user_id=1, role="owner", sharing_confirmed=True)
        )
        db.commit()
    return TestClient(app)


def read_latest_code(mail_dir) -> str:
    files = sorted(Path(mail_dir).glob("*.txt"), key=lambda p: p.stat().st_mtime)
    assert files, "未找到邮件文件"
    text = files[-1].read_text(encoding="utf-8")
    match = re.search(r"验证码是 (\d{6})", text)
    assert match, "邮件中未找到验证码"
    return match.group(1)


def login(client, email, password):
    resp = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def join_friend_room(client, owner_headers, guest_headers, room_id=None):
    """Test participation is always an explicit invitation, never account creation."""
    rooms = client.get("/api/v1/rooms", headers=owner_headers).json()["data"]
    room = next(r for r in rooms if r["id"] == room_id) if room_id else rooms[0]
    result = client.post(
        f"/api/v1/rooms/{room['id']}/sharing/confirm",
        headers=owner_headers,
        json={"accept_sharing": True},
    )
    assert result.status_code == 200, result.text
    result = client.post(
        f"/api/v1/rooms/{room['id']}/join",
        headers=guest_headers,
        json={"code": room["code"], "accept_sharing": True},
    )
    assert result.status_code == 200, result.text
    return room
