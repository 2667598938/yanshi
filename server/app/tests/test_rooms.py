"""多自习室：创建、公开/私密、房间码、成员上限与房主管理。"""
from app.tests.conftest import login

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def h(token):
    return {'Authorization': 'Bearer ' + token}


def make_member(client, ah, email, name):
    r = client.post('/api/v1/admin/members', headers=ah,
                    json={'email': email, 'nickname': name, 'password': 'Friend2028'})
    assert r.status_code == 200, r.text
    return r.json()['data']


def test_public_room_create_join_and_isolation(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    make_member(client, ah, 'room1@test.com', '房客甲')
    make_member(client, ah, 'room1b@test.com', '房客丙')
    mh = h(login(client, 'room1@test.com', 'Friend2028')['access_token'])
    ch = h(login(client, 'room1b@test.com', 'Friend2028')['access_token'])

    created = client.post('/api/v1/rooms', headers=ah,
                          json={'name': '冲刺小组', 'intro': '每天 6 小时', 'visibility': 'public'})
    assert created.status_code == 200, created.text
    room = created.json()['data']
    rid = room['id']
    assert room['my_role'] == 'owner' and len(room['code']) == 6

    # 其他成员在列表里能看到公开房间，且默认自习室仍在
    listed = client.get('/api/v1/rooms', headers=mh).json()['data']
    assert any(x['id'] == rid for x in listed)

    joined = client.post(f'/api/v1/rooms/{rid}/join', headers=mh, json={'code': ''})
    assert joined.status_code == 200
    assert joined.json()['data']['joined'] is True

    # 房内留言不会串到默认房间
    assert client.post(f'/api/v1/rooms/{rid}/messages', headers=mh,
                       json={'content': '冲刺房报到'}).status_code == 200
    default = client.get('/api/v1/room', headers=mh).json()['data']
    assert all(m['content'] != '冲刺房报到' for m in default['messages'])

    # 房内心跳只影响该房间
    assert client.post(f'/api/v1/rooms/{rid}/heartbeat', headers=mh,
                       json={'status': 'focusing', 'focus_started_at': 1}).status_code == 200
    state = client.get(f'/api/v1/rooms/{rid}', headers=mh).json()['data']
    assert any(m['presence']['status'] == 'focusing' for m in state['members'])

    # 普通成员可退出，房主不能
    assert client.post(f'/api/v1/rooms/{rid}/leave', headers=mh).status_code == 200
    assert client.post(f'/api/v1/rooms/{rid}/leave', headers=ah).status_code == 400

    # 房主可移除其他成员
    joined2 = client.post(f'/api/v1/rooms/{rid}/join', headers=ch, json={'code': ''})
    assert joined2.status_code == 200
    cid = joined2.json()['data']['members'][-1]['user_id']
    assert client.delete(f'/api/v1/rooms/{rid}/members/{cid}', headers=ah).status_code == 200
    after = client.get(f'/api/v1/rooms/{rid}', headers=ah).json()['data']
    assert all(m['user_id'] != cid for m in after['members'])

    # 房主改名、换码、解散
    updated = client.patch(f'/api/v1/rooms/{rid}', headers=ah,
                           json={'name': '冲刺小组 2.0'})
    assert updated.json()['data']['name'].endswith('2.0')
    new_code = client.post(f'/api/v1/rooms/{rid}/code', headers=ah).json()['data']['code']
    assert len(new_code) == 6 and new_code != room['code']
    assert client.delete(f'/api/v1/rooms/{rid}', headers=ah).status_code == 200
    assert client.get(f'/api/v1/rooms/{rid}', headers=ah).status_code == 404


def test_private_room_requires_code(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    make_member(client, ah, 'room2@test.com', '房客乙')
    mh = h(login(client, 'room2@test.com', 'Friend2028')['access_token'])

    room = client.post('/api/v1/rooms', headers=ah,
                       json={'name': '私密二人组', 'visibility': 'private'}).json()['data']
    rid = room['id']

    # 非成员列表看不到，直接访问 403
    assert all(x['id'] != rid for x in client.get('/api/v1/rooms', headers=mh).json()['data'])
    assert client.get(f'/api/v1/rooms/{rid}', headers=mh).status_code == 403

    # 错误房间码 403，正确房间码可加入
    assert client.post(f'/api/v1/rooms/{rid}/join', headers=mh,
                       json={'code': 'WRONG1'}).status_code == 403
    ok = client.post(f'/api/v1/rooms/{rid}/join', headers=mh,
                     json={'code': room['code'].lower()})
    assert ok.status_code == 200
    assert ok.json()['data']['joined'] is True

    # 默认房间不可解散
    default_id = client.get('/api/v1/room', headers=ah).json()['data']['room']['id']
    assert client.delete(f'/api/v1/rooms/{default_id}', headers=ah).status_code == 400
