"""后台管理（v0.3-f）测试。"""
from app.tests.conftest import login

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def h(t):
    return {'Authorization': 'Bearer ' + t}


def make_member(client, ah, email='adm1@test.com', name='后台成员'):
    r = client.post('/api/v1/admin/members', headers=ah,
                    json={'email': email, 'nickname': name, 'password': 'Friend2028'})
    assert r.status_code == 200, r.text
    return r.json()['data']


def test_member_lifecycle(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    m = make_member(client, ah)
    mid = m['id']

    # 改名
    r = client.put(f'/api/v1/admin/members/{mid}', headers=ah, json={'nickname': '新名字'})
    assert r.status_code == 200 and r.json()['data']['nickname'] == '新名字'

    # 封禁后无法登录
    assert client.put(f'/api/v1/admin/members/{mid}', headers=ah,
                      json={'status': 'banned'}).status_code == 200
    banned = client.post('/api/v1/auth/login', json={'email': 'adm1@test.com', 'password': 'Friend2028'})
    assert banned.status_code in (403, 401), banned.text

    # 解封后可登录
    assert client.put(f'/api/v1/admin/members/{mid}', headers=ah,
                      json={'status': 'active'}).status_code == 200
    assert login(client, 'adm1@test.com', 'Friend2028')['access_token']

    # 重置密码：旧密码失败、新密码成功
    assert client.post(f'/api/v1/admin/members/{mid}/reset-password', headers=ah,
                       json={'new_password': 'NewPass2028'}).status_code == 200
    assert client.post('/api/v1/auth/login',
                       json={'email': 'adm1@test.com', 'password': 'Friend2028'}).status_code in (403, 401)
    assert login(client, 'adm1@test.com', 'NewPass2028')['access_token']

    # 删除
    assert client.delete(f'/api/v1/admin/members/{mid}', headers=ah).status_code == 200
    members = client.get('/api/v1/admin/members', headers=ah).json()['data']
    assert all(x['id'] != mid for x in members)
    assert client.post('/api/v1/auth/login',
                       json={'email': 'adm1@test.com', 'password': 'NewPass2028'}).status_code in (401, 403, 404)


def test_announcement_crud_and_public(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])

    r = client.post('/api/v1/admin/announcements', headers=ah, json={'content': '本周六模考'})
    assert r.status_code == 200, r.text
    aid = r.json()['data']['id']

    pub = client.get('/api/v1/announcements')
    assert pub.status_code == 200
    assert any(a['id'] == aid for a in pub.json()['data'])

    # 下线
    assert client.put(f'/api/v1/admin/announcements/{aid}', headers=ah,
                      json={'is_active': False}).status_code == 200
    assert all(a['id'] != aid for a in client.get('/api/v1/announcements').json()['data'])

    # 删除
    assert client.delete(f'/api/v1/admin/announcements/{aid}', headers=ah).status_code == 200


def test_overview_export_audit_config(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    make_member(client, ah, 'adm2@test.com', '大盘成员')

    ov = client.get('/api/v1/admin/overview', headers=ah)
    assert ov.status_code == 200, ov.text
    data = ov.json()['data']
    assert data['member_count'] == 2
    assert data['room_member_count'] == 2
    assert 'total_focus_sec' in data and 'attachment_bytes' in data

    ex = client.get('/api/v1/admin/export', headers=ah)
    assert ex.status_code == 200
    assert 'records' in ex.json()['data'] and 'users' in ex.json()['data']

    logs = client.get('/api/v1/admin/audit-logs', headers=ah)
    assert logs.status_code == 200 and isinstance(logs.json()['data'], list)

    cfg = client.put('/api/v1/admin/config', headers=ah,
                     json={'registration_open': True, 'site_name': '研时测试'})
    assert cfg.status_code == 200, cfg.text
    pub = client.get('/api/v1/config/public').json()['data']
    assert pub['registration_open'] is True and pub['site_name'] == '研时测试'


def test_non_admin_forbidden(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    make_member(client, ah, 'adm3@test.com', '普通成员')
    mh = h(login(client, 'adm3@test.com', 'Friend2028')['access_token'])
    assert client.get('/api/v1/admin/overview', headers=mh).status_code == 403
