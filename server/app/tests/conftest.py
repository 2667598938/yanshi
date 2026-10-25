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
        database_url='sqlite:///' + (tmp_path / 'test.sqlite').as_posix(),
        environment='test',
        mail_console=True,
        mail_directory=tmp_path / 'mail',
        image_directory=tmp_path / 'uploads',
        volc_api_key='',   # 测试禁用真实 AI，用例内 monkeypatch
        admin_email='admin@test.com',
        admin_password='Admin2028',
        auth_email_domains='',   # 测试环境不限制邮箱域名
    )
    app = create_app(settings)
    Base.metadata.create_all(bind=app.state.engine)
    session_factory = app.state.session_factory
    with session_factory() as db:
        seed(db, settings, echo=lambda *a: None)
    return TestClient(app)


def read_latest_code(mail_dir) -> str:
    files = sorted(Path(mail_dir).glob('*.txt'), key=lambda p: p.stat().st_mtime)
    assert files, '未找到邮件文件'
    text = files[-1].read_text(encoding='utf-8')
    match = re.search(r'验证码是 (\d{6})', text)
    assert match, '邮件中未找到验证码'
    return match.group(1)


def login(client, email, password):
    resp = client.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert resp.status_code == 200, resp.text
    return resp.json()['data']
