"""页面门槛以外，直接请求业务数据仍需真实登录；邀请码不能绕过注册总开关。"""
import pytest

from app.models import Config
from app.tests.conftest import login, read_latest_code


@pytest.mark.parametrize('path', ['/api/v1/sync/records', '/api/v1/schools', '/api/v1/rooms',
                                 '/api/v1/group/members', '/api/v1/ai/conversations', '/api/v1/auth/me'])
def test_business_api_requires_login(client, path):
    assert client.get(path).status_code == 401


def test_closed_registration_rejects_even_valid_invite(client):
    token = login(client, 'admin@test.com', 'Admin2028')['access_token']
    result = client.post('/api/v1/admin/invites', headers={'Authorization': 'Bearer ' + token},
                         json={'remark': '准入边界测试'})
    assert result.status_code == 200, result.text
    invite = result.json()['data']['code']
    assert client.post('/api/v1/auth/email-code', json={'email': 'closed@test.com', 'scene': 'register'}).status_code == 200
    code = read_latest_code(client.app.state.settings.mail_directory)
    with client.app.state.session_factory() as db:
        db.get(Config, 'registration_open').config_value = 'false'
        db.commit()
    assert client.get('/api/v1/config/public').json()['data']['registration_open'] is False
    response = client.post('/api/v1/auth/register', json={'email': 'closed@test.com', 'code': code,
        'password': 'Password2026', 'nickname': '待注册同学', 'invite_code': invite, 'accepted_terms': True})
    assert response.status_code == 403
    assert '注册已关闭' in response.json()['message']
