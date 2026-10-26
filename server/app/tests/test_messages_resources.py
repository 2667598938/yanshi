"""站内消息 + 资料区。"""
from app.tests.conftest import login

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def h(token):
    return {'Authorization': 'Bearer ' + token}


def make_member(client, ah, email, name):
    r = client.post('/api/v1/admin/members', headers=ah,
                    json={'email': email, 'nickname': name, 'password': 'Friend2028'})
    assert r.status_code == 200, r.text
    return r.json()['data']


def grant_vip(client, ah, uid):
    r = client.put(f'/api/v1/admin/members/{uid}', headers=ah,
                   json={'vip_action': 'grant', 'vip_days': 30, 'note': '测试开通会员'})
    assert r.status_code == 200, r.text


def test_apply_and_vip_notifications(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    m = make_member(client, ah, 'msg1@test.com', '消息甲')
    mh = h(login(client, 'msg1@test.com', 'Friend2028')['access_token'])

    # 提交申请 → 管理员通过
    rid = client.post('/api/v1/requests', headers=mh,
                      json={'feature': 'ai', 'reason': '想用 AI 讲数学题'}).json()['data']['id']
    reviewed = client.post(f'/api/v1/admin/requests/{rid}/review', headers=ah,
                           json={'action': 'approve', 'note': '同意，自备 Key'})
    assert reviewed.status_code == 200, reviewed.text

    msgs = client.get('/api/v1/messages', headers=mh).json()['data']
    assert any(m['kind'] == 'apply' and '通过' in m['title'] for m in msgs)
    assert client.get('/api/v1/messages/unread-count', headers=mh).json()['data']['count'] >= 1

    mid = msgs[0]['id']
    assert client.post(f'/api/v1/messages/{mid}/read', headers=mh).status_code == 200
    assert client.post('/api/v1/messages/read-all', headers=mh).status_code == 200
    assert client.get('/api/v1/messages/unread-count', headers=mh).json()['data']['count'] == 0

    # 管理员调整 VIP → 再来一条
    grant_vip(client, ah, m['id'])
    msgs2 = client.get('/api/v1/messages', headers=mh).json()['data']
    assert any(x['kind'] == 'vip' for x in msgs2)


def test_resource_vip_masking_like_favorite(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    m1 = make_member(client, ah, 'res1@test.com', '资料甲')
    make_member(client, ah, 'res2@test.com', '资料乙')
    h1 = h(login(client, 'res1@test.com', 'Friend2028')['access_token'])
    h2 = h(login(client, 'res2@test.com', 'Friend2028')['access_token'])

    payload = {'title': '英语真题精析', 'url': 'https://pan.quark.cn/s/7f3a9c2b1d4e',
               'code': 'x7k2', 'category': '英语', 'intro': '2010-2026 真题'}

    # 非 VIP 不能发布
    assert client.post('/api/v1/resources', headers=h1, json=payload).status_code == 403

    grant_vip(client, ah, m1['id'])
    created = client.post('/api/v1/resources', headers=h1, json=payload)
    assert created.status_code == 200, created.text
    rid = created.json()['data']['id']
    assert client.post(f'/api/v1/admin/resources/{rid}/review',headers=ah,json={'action':'approve','expected_revision':1}).status_code==200

    # 普通用户看到脱敏链接且没有提取码
    masked = client.get(f'/api/v1/resources/{rid}', headers=h2).json()['data']
    assert masked['masked'] is True
    assert masked['code'] == ''
    assert '******' in masked['url'] and '7f3a9c2b1d4e' not in masked['url']

    # VIP 看到完整链接与提取码
    full = client.get(f'/api/v1/resources/{rid}', headers=h1).json()['data']
    assert full['masked'] is False
    assert full['url'] == payload['url'] and full['code'] == 'x7k2'

    # 点赞切换
    assert client.post(f'/api/v1/resources/{rid}/like', headers=h2).json()['data'] == {
        'liked': True, 'like_count': 1}
    assert client.post(f'/api/v1/resources/{rid}/like', headers=h2).json()['data'] == {
        'liked': False, 'like_count': 0}

    # 收藏与我的收藏
    assert client.post(f'/api/v1/resources/{rid}/favorite',
                       headers=h2).json()['data']['favorited'] is True
    favs = client.get('/api/v1/resources/favorites', headers=h2).json()['data']
    assert len(favs) == 1 and favs[0]['id'] == rid
    assert client.post(f'/api/v1/resources/{rid}/favorite',
                       headers=h2).json()['data']['favorited'] is False

    # 离线同步用的幂等收藏接口：重复提交同一状态不翻转
    for _ in range(2):
        assert client.put(f'/api/v1/resources/{rid}/favorite', headers=h2,
                          json={'favorited': True}).json()['data']['favorited'] is True
    assert len(client.get('/api/v1/resources/favorites', headers=h2).json()['data']) == 1
    for _ in range(2):
        assert client.put(f'/api/v1/resources/{rid}/favorite', headers=h2,
                          json={'favorited': False}).json()['data']['favorited'] is False
    assert client.get('/api/v1/resources/favorites', headers=h2).json()['data'] == []

    # 编辑与删除
    edited = client.put(f'/api/v1/resources/{rid}', headers=h1, json={'title': '英语真题精析 2026'})
    assert edited.status_code == 200
    assert edited.json()['data']['title'].endswith('2026')
    assert client.delete(f'/api/v1/resources/{rid}', headers=h1).status_code == 200
    assert client.get(f'/api/v1/resources/{rid}', headers=h1).status_code == 404

    # 管理员删除他人资料必须填写原因
    second = client.post('/api/v1/resources', headers=h1, json=payload).json()['data']['id']
    r = client.delete(f'/api/v1/resources/{second}', headers=ah)
    assert r.status_code == 400 and r.json()['code'] == 40001
    assert client.get(f'/api/v1/resources/{second}', headers=h1).status_code == 200
    assert client.delete(f'/api/v1/resources/{second}', headers=ah,
                         params={'reason': '链接失效'}).status_code == 200
    msgs = client.get('/api/v1/messages', headers=h1).json()['data']
    assert any('资料' in m['title'] and '链接失效' in m['content'] for m in msgs)
