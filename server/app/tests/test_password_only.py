"""内测登录策略直接校验接口、旧验证码/票据、密码重置与管理员登录。"""
from app.config import Settings
from app.tests.conftest import login, read_latest_code
from app.services.transient import digest


def test_password_only_is_default():
    assert Settings(_env_file=None).auth_password_only is True


def test_beta_blocks_all_other_login_paths_even_existing_codes(client):
    settings = client.app.state.settings
    settings.auth_password_only = True
    settings.auth_channels = 'email,qq,wechat,phone'
    config = client.get('/api/v1/config/public').json()['data']
    assert config['auth_password_only'] is True
    assert config['registration_open'] is False
    assert config['enabled_auth_channels'] == ['email']
    store = client.app.state.transient
    store.set('login-code:' + digest('admin@test.com'), digest('123456'), 300)
    store.set('oauth-ticket:' + digest('old-ticket'), '{}', 120)
    for path, body in [
        ('/auth/email-code', {'email': 'admin@test.com', 'scene': 'login'}),
        ('/auth/email-code', {'email': 'new@test.com', 'scene': 'register'}),
        ('/auth/email-login', {'email': 'admin@test.com', 'code': '123456', 'accepted_terms': True}),
        ('/auth/register', {'email': 'new@test.com', 'password': 'Password2026', 'nickname': '新同学', 'code': '123456', 'accepted_terms': True}),
        ('/auth/phone/send-code', {'phone': '13800138000'}),
        ('/auth/phone/verify-code', {'phone': '13800138000', 'code': '123456'}),
        ('/auth/oauth/exchange', {'ticket': 'old-ticket'}),
    ]:
        response = client.post('/api/v1' + path, json=body)
        assert response.status_code == 403, (path, response.text)
    for provider in ['qq', 'wechat']:
        assert client.get(f'/api/v1/auth/oauth/{provider}/authorize').status_code == 403
        assert client.get(f'/api/v1/auth/oauth/{provider}/callback').status_code == 403
    session = login(client, 'admin@test.com', 'Admin2028')
    assert session['user']['role'] == 'admin'
    headers = {'Authorization': 'Bearer ' + session['access_token']}
    assert client.get('/api/v1/admin/config', headers=headers).json()['data']['auth_password_only'] is True
    assert client.put('/api/v1/admin/config', headers=headers, json={'registration_open': True}).status_code == 403
    assert client.put('/api/v1/admin/config', headers=headers, json={'site_name': '内测站点'}).status_code == 200


def test_beta_still_allows_password_reset(client):
    client.app.state.settings.auth_password_only = True
    # 管理员现有账号可以不属于当前允许自助注册的域名。
    client.app.state.settings.auth_email_domains = 'qq.com'
    client.app.state.settings.auth_qq_numeric_only = True
    response = client.post('/api/v1/auth/email-code', json={'email': 'admin@test.com', 'scene': 'reset'})
    assert response.status_code == 200
    code = read_latest_code(client.app.state.settings.mail_directory)
    response = client.post('/api/v1/auth/reset-password', json={'email': 'admin@test.com', 'code': code, 'password': 'NewAdmin2028'})
    assert response.status_code == 200, response.text
    assert login(client, 'admin@test.com', 'NewAdmin2028')['user']['role'] == 'admin'
