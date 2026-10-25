"""多自习室：创建、公开/私密、房间码、成员上限与房主管理。"""
from app.tests.conftest import login
from app.tests.test_room import register_friend

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


def _create_private_room(client, ah, name='私密申请房'):
    room = client.post('/api/v1/rooms', headers=ah,
                       json={'name': name, 'visibility': 'private'}).json()['data']
    return room


def test_private_room_apply_and_owner_review(client):
    """无码陌生人走申请：通过前无成员权限，只有房主能审批，通过后即时生效。"""
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    make_member(client, ah, 'apply1@test.com', '申请同学')
    make_member(client, ah, 'apply2@test.com', '旁观同学')
    oh = h(login(client, 'apply1@test.com', 'Friend2028')['access_token'])
    xh = h(login(client, 'apply2@test.com', 'Friend2028')['access_token'])

    room = _create_private_room(client, ah)
    rid = room['id']

    # 未加入：列表不可见、详情 403，但预览可看到申请入口
    assert all(x['id'] != rid for x in client.get('/api/v1/rooms', headers=oh).json()['data'])
    assert client.get(f'/api/v1/rooms/{rid}', headers=oh).status_code == 403
    preview = client.get(f'/api/v1/rooms/{rid}/preview', headers=oh).json()['data']
    assert preview['joined'] is False and preview['join_required'] is True
    assert preview['apply'] is None

    # 提交申请；重复提交返回同一条 pending
    first = client.post(f'/api/v1/rooms/{rid}/apply', headers=oh,
                        json={'message': '想一起冲刺'})
    assert first.status_code == 200, first.text
    apply_id = first.json()['data']['id']
    assert first.json()['data']['status'] == 'pending'
    again = client.post(f'/api/v1/rooms/{rid}/apply', headers=oh, json={'message': ''})
    assert again.json()['data']['id'] == apply_id
    # 审批前仍无成员权限
    assert client.get(f'/api/v1/rooms/{rid}', headers=oh).status_code == 403

    # 非房主不能查看待审列表或审批
    assert client.get(f'/api/v1/rooms/{rid}/applies', headers=xh).status_code == 403
    assert client.post(f'/api/v1/rooms/{rid}/applies/{apply_id}/review', headers=xh,
                       json={'approve': True}).status_code == 403

    # 房主待审列表
    pending = client.get(f'/api/v1/rooms/{rid}/applies', headers=ah).json()['data']['items']
    assert len(pending) == 1
    assert pending[0]['nickname'] == '申请同学' and pending[0]['message'] == '想一起冲刺'

    # 通过后立即成为成员，可正常进入
    approved = client.post(f'/api/v1/rooms/{rid}/applies/{apply_id}/review', headers=ah,
                           json={'approve': True})
    assert approved.status_code == 200, approved.text
    assert approved.json()['data']['status'] == 'approved'
    state = client.get(f'/api/v1/rooms/{rid}', headers=oh).json()['data']
    assert state['joined'] is True
    # 重复处理旧申请被拒
    assert client.post(f'/api/v1/rooms/{rid}/applies/{apply_id}/review', headers=ah,
                       json={'approve': True}).status_code == 400
    # 申请人收到审批通知
    msgs = client.get('/api/v1/messages', headers=oh).json()['data']
    assert any(m['title'] == '入房申请已通过' for m in msgs)


def test_reject_then_reapply_allowed(client):
    """被驳回后可再次申请：历史保留多条，pending 始终只有一条。"""
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    make_member(client, ah, 'reapply@test.com', '再申请同学')
    rh = h(login(client, 'reapply@test.com', 'Friend2028')['access_token'])
    rid = _create_private_room(client, ah, '驳回再申请房')['id']

    first = client.post(f'/api/v1/rooms/{rid}/apply', headers=rh, json={'message': '第一次'})
    first_id = first.json()['data']['id']
    rejected = client.post(f'/api/v1/rooms/{rid}/applies/{first_id}/review', headers=ah,
                           json={'approve': False})
    assert rejected.status_code == 200 and rejected.json()['data']['status'] == 'rejected'
    assert client.get(f'/api/v1/rooms/{rid}', headers=rh).status_code == 403

    second = client.post(f'/api/v1/rooms/{rid}/apply', headers=rh, json={'message': '第二次'})
    assert second.status_code == 200, second.text
    assert second.json()['data']['id'] != first_id
    pending = client.get(f'/api/v1/rooms/{rid}/applies', headers=ah).json()['data']['items']
    assert len(pending) == 1 and pending[0]['message'] == '第二次'
    history = client.get(f'/api/v1/rooms/{rid}/applies?status=rejected',
                         headers=ah).json()['data']['items']
    assert [x['id'] for x in history] == [first_id]


def test_apply_blocked_when_full_and_public_room(client):
    """满员不可申请；公开房间直接加入，不走申请。"""
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    room = _create_private_room(client, ah, '满员房')
    rid = room['id']
    # 房主 + 3 名凭码成员 = 4 人（默认房已满，用邮件注册建号，注册不强制占默认房）
    for i in range(3):
        fh = register_friend(client, ah, f'full{i}@test.com', f'满员{i}')
        assert client.post(f'/api/v1/rooms/{rid}/join', headers=fh,
                           json={'code': room['code']}).status_code == 200
    f5 = register_friend(client, ah, 'full5@test.com', '第五人')
    r = client.post(f'/api/v1/rooms/{rid}/apply', headers=f5, json={'message': '还有位置吗'})
    assert r.status_code == 403 and r.json()['code'] == 40302

    public = client.post('/api/v1/rooms', headers=ah,
                         json={'name': '公开直入房', 'visibility': 'public'}).json()['data']
    r = client.post(f'/api/v1/rooms/{public["id"]}/apply', headers=f5, json={})
    assert r.status_code == 400
