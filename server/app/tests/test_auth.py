from app.tests.conftest import login, read_latest_code

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def test_health_and_public_config(client):
    assert client.get('/health').json()['status'] == 'ok'
    pub = client.get('/api/v1/config/public').json()['data']
    assert pub['site_name'] == '研时'
    assert pub['exam_date'] == '2027-12-25'
    assert pub['registration_open'] is True


def test_admin_login_and_member_requires_admin(client):
    admin = login(client, **ADMIN)
    headers = {'Authorization': 'Bearer ' + admin['access_token']}

    # 普通成员访问后台被拒
    resp = client.get('/api/v1/admin/members', headers={'Authorization': 'Bearer bad'})
    assert resp.status_code == 401


def test_full_register_login_refresh_flow(client):
    # 1. 管理员登录并生成邀请码
    admin = login(client, **ADMIN)
    admin_headers = {'Authorization': 'Bearer ' + admin['access_token']}
    resp = client.post('/api/v1/admin/invites', json={'remark': '第一位研友'}, headers=admin_headers)
    assert resp.status_code == 200, resp.text
    invite = resp.json()['data']['code']

    # 2. 索取注册邮箱验证码
    email = 'friend1@test.com'
    resp = client.post('/api/v1/auth/email-code', json={'email': email, 'scene': 'register'})
    assert resp.status_code == 200, resp.text
    code = read_latest_code(client.app.state.settings.mail_directory)

    # 3. 用邀请码注册
    resp = client.post('/api/v1/auth/register', json={
        'email': email, 'code': code, 'password': 'Friend2028',
        'nickname': '研友一号', 'invite_code': invite, 'accepted_terms': True})
    assert resp.status_code == 200, resp.text
    reg = resp.json()['data']
    assert reg['user']['nickname'] == '研友一号'
    assert reg['user']['role'] == 'member'
    # refresh token 只在 httpOnly Cookie，不返回给前端
    assert 'refresh_token' not in reg
    assert client.cookies.get('yanshi_refresh')

    # 4. me
    headers = {'Authorization': 'Bearer ' + reg['access_token']}
    me = client.get('/api/v1/auth/me', headers=headers).json()['data']
    assert me['email'] == email

    # 5. 刷新令牌（Cookie）
    resp = client.post('/api/v1/auth/refresh')
    assert resp.status_code == 200, resp.text
    assert 'access_token' in resp.json()['data']
    assert 'refresh_token' not in resp.json()['data']

    # 6. 更新资料
    resp = client.put('/api/v1/users/me', json={'nickname': '新昵称', 'daily_goal_min': 360}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()['data']['nickname'] == '新昵称'

    # 7. 成员看不到后台
    resp = client.get('/api/v1/admin/members', headers=headers)
    assert resp.status_code == 403

    # 8. 管理员看到 2 名成员
    members = client.get('/api/v1/admin/members', headers=admin_headers).json()['data']
    assert len(members) == 2

    # 9. 邀请码已被使用，不能再用
    resp = client.post('/api/v1/auth/email-code', json={'email': 'friend2@test.com', 'scene': 'register'})
    assert resp.status_code == 200
    code2 = read_latest_code(client.app.state.settings.mail_directory)
    resp = client.post('/api/v1/auth/register', json={
        'email': 'friend2@test.com', 'code': code2, 'password': 'Friend2028',
        'nickname': '研友二号', 'invite_code': invite, 'accepted_terms': True})
    assert resp.status_code == 400


def test_bad_password_and_reset(client):
    # 错误密码
    resp = client.post('/api/v1/auth/login', json={'email': ADMIN['email'], 'password': 'wrong123'})
    assert resp.status_code == 401

    # 找回密码：发码 + 重置
    resp = client.post('/api/v1/auth/email-code', json={'email': ADMIN['email'], 'scene': 'reset'})
    assert resp.status_code == 200
    code = read_latest_code(client.app.state.settings.mail_directory)
    resp = client.post('/api/v1/auth/reset-password', json={
        'email': ADMIN['email'], 'code': code, 'password': 'NewAdmin2028'})
    assert resp.status_code == 200, resp.text
    assert login(client, ADMIN['email'], 'NewAdmin2028')['user']['role'] == 'admin'


def _make_plain_member(client, ah, email, password='Friend2028', nickname='普通成员'):
    r = client.post('/api/v1/admin/members', headers=ah,
                    json={'email': email, 'nickname': nickname, 'password': password})
    assert r.status_code == 200, r.text
    return login(client, email, password)


def test_login_lock_after_5_failures(client):
    admin = login(client, **ADMIN)
    ah = {'Authorization': 'Bearer ' + admin['access_token']}
    _make_plain_member(client, ah, 'lock@test.com')

    # 连续 5 次错误密码，均返回 401
    for _ in range(5):
        r = client.post('/api/v1/auth/login', json={'email': 'lock@test.com', 'password': 'WrongPass1'})
        assert r.status_code == 401, r.text
    # 第 6 次即使密码正确，也因触发锁定返回 403 / 40302
    r = client.post('/api/v1/auth/login', json={'email': 'lock@test.com', 'password': 'Friend2028'})
    assert r.status_code == 403, r.text
    assert r.json()['code'] == 40302


def test_change_password_revokes_old_tokens(client):
    admin = login(client, **ADMIN)
    ah = {'Authorization': 'Bearer ' + admin['access_token']}
    member = _make_plain_member(client, ah, 'chg@test.com')
    old_headers = {'Authorization': 'Bearer ' + member['access_token']}
    old_refresh = client.cookies.get('yanshi_refresh')

    # 修改密码
    r = client.put('/api/v1/users/me/password', headers=old_headers,
                   json={'old_password': 'Friend2028', 'new_password': 'BrandNew2028'})
    assert r.status_code == 200, r.text
    assert client.cookies.get('yanshi_refresh') != old_refresh

    # 旧 access token 立即失效（token_version 已 +1）
    r = client.get('/api/v1/auth/me', headers=old_headers)
    assert r.status_code == 401, r.text
    # 旧 refresh token 已被吊销
    client.cookies.clear()
    client.cookies.set('yanshi_refresh', old_refresh, path='/api/v1/auth')
    r = client.post('/api/v1/auth/refresh')
    assert r.status_code == 401, r.text
    # 新密码可以登录
    assert login(client, 'chg@test.com', 'BrandNew2028')['access_token']


def test_refresh_rotation_revokes_old_refresh(client):
    admin = login(client, **ADMIN)
    ah = {'Authorization': 'Bearer ' + admin['access_token']}
    _make_plain_member(client, ah, 'rot@test.com')
    rt1 = client.cookies.get('yanshi_refresh')

    # 旋转一次得到新 refresh
    r = client.post('/api/v1/auth/refresh')
    assert r.status_code == 200, r.text
    rt2 = client.cookies.get('yanshi_refresh')
    assert rt2 and rt2 != rt1

    # 旧 refresh 重放 -> 401（一次性，已吊销）
    client.cookies.clear()
    client.cookies.set('yanshi_refresh', rt1, path='/api/v1/auth')
    r = client.post('/api/v1/auth/refresh')
    assert r.status_code == 401, r.text
    # 新 refresh 可用
    client.cookies.clear()
    client.cookies.set('yanshi_refresh', rt2, path='/api/v1/auth')
    r = client.post('/api/v1/auth/refresh')
    assert r.status_code == 200, r.text


def test_refresh_cookie_is_http_only(client):
    resp = client.post('/api/v1/auth/login', json=ADMIN)
    cookie = resp.headers.get('set-cookie', '').lower()
    assert 'yanshi_refresh=' in cookie
    assert 'httponly' in cookie
    assert 'samesite=lax' in cookie
    assert 'path=/api/v1/auth' in cookie


def test_email_code_five_minutes_and_attempt_limit(client):
    email = 'code-limit@test.com'
    assert client.post('/api/v1/auth/email-code',
                       json={'email': email, 'scene': 'register'}).status_code == 200
    code = read_latest_code(client.app.state.settings.mail_directory)
    mail_text = sorted(client.app.state.settings.mail_directory.glob('*.txt'),
                       key=lambda p: p.stat().st_mtime)[-1].read_text(encoding='utf-8')
    assert '5 分钟' in mail_text

    # 连错 5 次后验证码作废，即使输入正确也失败
    for _ in range(5):
        r = client.post('/api/v1/auth/register', json={
            'email': email, 'code': '000000', 'password': 'Friend2028',
            'nickname': '验证码测试', 'accepted_terms': True})
        assert r.status_code == 400
    r = client.post('/api/v1/auth/register', json={
        'email': email, 'code': code, 'password': 'Friend2028',
        'nickname': '验证码测试', 'accepted_terms': True})
    assert r.status_code == 400


def test_email_domain_restriction(client):
    settings = client.app.state.settings
    settings.auth_email_domains = 'qq.com'
    try:
        r = client.post('/api/v1/auth/email-code',
                        json={'email': 'not-qq@test.com', 'scene': 'register'})
        assert r.status_code == 400
        r = client.post('/api/v1/auth/email-code',
                        json={'email': 'ok@qq.com', 'scene': 'register'})
        assert r.status_code == 200
    finally:
        settings.auth_email_domains = ''
