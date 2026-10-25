"""账号与 AI：验证码登录、开放注册、资料、错误类型、BYOK。"""
from app.models import UserAIKey
from app.tests.conftest import login, read_latest_code

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def h(token):
    return {'Authorization': 'Bearer ' + token}


def test_code_login_auto_register(client):
    email = 'newbie@test.com'
    assert client.post('/api/v1/auth/email-code',
                       json={'email': email, 'scene': 'login'}).status_code == 200
    code = read_latest_code(client.app.state.settings.mail_directory)

    r = client.post('/api/v1/auth/email-login',
                    json={'email': email, 'code': code, 'accepted_terms': True})
    assert r.status_code == 200, r.text
    data = r.json()['data']
    assert data['registered'] is True
    assert data['user']['email'] == email
    assert data['user']['figure_id'] == 'figure-1'

    # 已注册账号走验证码登录：不重复建号
    admin_email = 'admin@test.com'
    assert client.post('/api/v1/auth/email-code',
                       json={'email': admin_email, 'scene': 'login'}).status_code == 200
    code2 = read_latest_code(client.app.state.settings.mail_directory)
    again = client.post('/api/v1/auth/email-login',
                        json={'email': admin_email, 'code': code2, 'accepted_terms': True})
    assert again.status_code == 200, again.text
    assert again.json()['data']['registered'] is False


def test_register_without_invite_and_profile(client):
    email = 'free@test.com'
    client.post('/api/v1/auth/email-code', json={'email': email, 'scene': 'register'})
    code = read_latest_code(client.app.state.settings.mail_directory)
    r = client.post('/api/v1/auth/register', json={
        'email': email, 'code': code, 'password': 'Friend2028',
        'nickname': '自由注册', 'accepted_terms': True})
    assert r.status_code == 200, r.text

    token = r.json()['data']['access_token']
    up = client.put('/api/v1/users/me', headers=h(token),
                    json={'signature': '一战上岸', 'figure_id': 'figure-4'})
    assert up.status_code == 200, up.text
    assert up.json()['data']['signature'] == '一战上岸'
    assert up.json()['data']['figure_id'] == 'figure-4'


def test_error_type_crud(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    base = client.get('/api/v1/mistake/error-types', headers=ah).json()['data']
    assert len(base['presets']) == 6

    created = client.post('/api/v1/mistake/error-types', headers=ah,
                          json={'name': '单位换算'})
    assert created.status_code == 200, created.text
    tid = created.json()['data']['id']

    # 重名
    assert client.post('/api/v1/mistake/error-types', headers=ah,
                       json={'name': '单位换算'}).status_code == 409

    renamed = client.put(f'/api/v1/mistake/error-types/{tid}', headers=ah,
                         json={'name': '单位/量纲'})
    assert renamed.status_code == 200
    assert renamed.json()['data']['name'] == '单位/量纲'

    assert client.delete(f'/api/v1/mistake/error-types/{tid}', headers=ah).status_code == 200
    rows = client.get('/api/v1/mistake/error-types', headers=ah).json()['data']['custom']
    assert all(x['id'] != tid for x in rows)


def test_ai_key_vip_only_and_encrypted(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    m = client.post('/api/v1/admin/members', headers=ah,
                    json={'email': 'byok@test.com', 'nickname': 'BYOK',
                          'password': 'Friend2028'}).json()['data']
    member = login(client, 'byok@test.com', 'Friend2028')
    mh = h(member['access_token'])

    # 非 VIP 无法读写
    assert client.get('/api/v1/ai/key', headers=mh).status_code == 403
    assert client.put('/api/v1/ai/key', headers=mh, json={
        'provider': 'deepseek', 'api_key': 'sk-test-1234567890'}).status_code == 403

    # 管理员开通 VIP
    up = client.put(f'/api/v1/admin/members/{m["id"]}', headers=ah,
                    json={'vip_action': 'grant', 'vip_days': 30, 'note': '测试开通会员'})
    assert up.status_code == 200, up.text

    saved = client.put('/api/v1/ai/key', headers=mh, json={
        'provider': 'deepseek', 'model': 'deepseek-chat',
        'api_key': 'sk-test-1234567890'})
    assert saved.status_code == 200, saved.text
    body = saved.json()['data']
    assert body['configured'] is True
    assert body['key_mask'].endswith('7890')
    assert 'sk-test-1234567890' not in str(body)

    # 数据库中是密文
    with client.app.state.session_factory() as db:
        row = db.get(UserAIKey, m['id'])
        assert row and 'sk-test-1234567890' not in row.key_cipher

    # 删除
    assert client.delete('/api/v1/ai/key', headers=mh).status_code == 200
    assert client.get('/api/v1/ai/key', headers=mh).json()['data']['configured'] is False


def test_oauth_channels_disabled_by_default(client):
    cfg = client.get('/api/v1/config/public').json()['data']
    assert cfg['enabled_auth_channels'] == ['email']

    assert client.get('/api/v1/auth/oauth/wechat/authorize').status_code == 403
    assert client.get('/api/v1/auth/oauth/qq/authorize').status_code == 403
    assert client.post('/api/v1/auth/phone/send-code',
                       json={'phone': '13800138000'}).status_code == 403
    # 未知渠道
    assert client.get('/api/v1/auth/oauth/github/authorize').status_code == 404
    # 无效 ticket
    assert client.post('/api/v1/auth/oauth/exchange',
                       json={'ticket': 'not-a-real-ticket'}).status_code == 400


def test_phone_login_when_channel_enabled(client, monkeypatch):
    client.app.state.settings.auth_channels = 'email,phone'
    import app.routers.oauth as oauth
    monkeypatch.setattr(oauth.secrets, 'randbelow', lambda _n: 123456)

    phone = '13800138000'
    assert client.post('/api/v1/auth/phone/send-code',
                       json={'phone': phone}).status_code == 200
    r = client.post('/api/v1/auth/phone/verify-code',
                    json={'phone': phone, 'code': '123456'})
    assert r.status_code == 200, r.text
    data = r.json()['data']
    assert data['user']['phone'] == phone
    assert data['access_token']

    # 同一手机号已绑定：再次验证码登录应复用账号
    # （发送验证码有 60 秒限流，这里直接复用内存中的票据键做校验）
    from app.services.transient import digest
    client.app.state.transient.set('phone-code:' + digest(phone), digest('123456'), 300)
    again = client.post('/api/v1/auth/phone/verify-code',
                        json={'phone': phone, 'code': '123456'})
    assert again.status_code == 200
    assert again.json()['data']['user']['id'] == data['user']['id']
