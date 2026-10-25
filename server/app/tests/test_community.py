"""社区：动态、二级评论、励志区审核。"""
from app.tests.conftest import login

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def h(token):
    return {'Authorization': 'Bearer ' + token}


def make_member(client, ah, email, name):
    r = client.post('/api/v1/admin/members', headers=ah,
                    json={'email': email, 'nickname': name, 'password': 'Friend2028'})
    assert r.status_code == 200, r.text
    return r.json()['data']


def test_posts_and_nested_comments(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    make_member(client, ah, 'post1@test.com', '帖主')
    make_member(client, ah, 'post2@test.com', '回复者')
    p1 = h(login(client, 'post1@test.com', 'Friend2028')['access_token'])
    p2 = h(login(client, 'post2@test.com', 'Friend2028')['access_token'])

    post = client.post('/api/v1/posts', headers=p1,
                       json={'content': '今天线代终于通了，记录一下。'})
    assert post.status_code == 200, post.text
    pid = post.json()['data']['id']

    feed = client.get('/api/v1/posts', headers=p2).json()['data']
    assert any(x['id'] == pid for x in feed)

    c1 = client.post(f'/api/v1/posts/{pid}/comments', headers=p2,
                     json={'content': '恭喜，求笔记'}).json()['data']
    # 回复一级评论
    c2 = client.post(f'/api/v1/posts/{pid}/comments', headers=p1,
                     json={'content': '发你了', 'parent_id': c1['id']}).json()['data']
    assert c2['parent_id'] == c1['id']
    # 回复二级评论：仍挂在父级下，最多两层
    c3 = client.post(f'/api/v1/posts/{pid}/comments', headers=p2,
                     json={'content': '收到，谢谢', 'parent_id': c2['id']}).json()['data']
    assert c3['parent_id'] == c1['id']
    assert c3['reply_to'] == '帖主'

    comments = client.get(f'/api/v1/posts/{pid}/comments', headers=p1).json()['data']
    assert len(comments) == 3

    # 删除父评论 → 子回复一并隐藏
    assert client.delete(f"/api/v1/comments/{c1['id']}", headers=p2).status_code == 200
    left = client.get(f'/api/v1/posts/{pid}/comments', headers=p1).json()['data']
    assert all(x['id'] != c1['id'] and x['parent_id'] != c1['id'] for x in left)

    # 管理员删除帖子 → 作者收到消息
    assert client.delete(f'/api/v1/posts/{pid}', headers=ah,
                         params={'reason': '内容违规'}).status_code == 200
    msgs = client.get('/api/v1/messages', headers=p1).json()['data']
    assert any('帖子' in m['title'] for m in msgs)
    assert client.get(f'/api/v1/posts/{pid}', headers=p1).status_code == 404


def test_admin_delete_requires_reason(client):
    """管理员删除他人内容必须填写原因；作者自删不受限。"""
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    make_member(client, ah, 'reason1@test.com', '被删作者')
    make_member(client, ah, 'reason2@test.com', '评论作者')
    p1 = h(login(client, 'reason1@test.com', 'Friend2028')['access_token'])
    p2 = h(login(client, 'reason2@test.com', 'Friend2028')['access_token'])

    pid = client.post('/api/v1/posts', headers=p1, json={'content': '先留着'}).json()['data']['id']
    cid = client.post(f'/api/v1/posts/{pid}/comments', headers=p2,
                      json={'content': '一条评论'}).json()['data']['id']

    # 管理员无原因删帖 / 删评论都被拒，内容仍在
    r = client.delete(f'/api/v1/posts/{pid}', headers=ah)
    assert r.status_code == 400 and r.json()['code'] == 40001
    assert client.get(f'/api/v1/posts/{pid}', headers=p1).status_code == 200
    r = client.delete(f'/api/v1/comments/{cid}', headers=ah)
    assert r.status_code == 400 and r.json()['code'] == 40001

    # 填原因后删除成功，作者收到含原因的站内消息
    assert client.delete(f'/api/v1/comments/{cid}', headers=ah,
                         params={'reason': '评论含广告'}).status_code == 200
    msgs = client.get('/api/v1/messages', headers=p2).json()['data']
    assert any('评论' in m['title'] and '评论含广告' in m['content'] for m in msgs)
    assert client.delete(f'/api/v1/posts/{pid}', headers=ah,
                         params={'reason': '内容违规'}).status_code == 200
    msgs = client.get('/api/v1/messages', headers=p1).json()['data']
    assert any('帖子' in m['title'] and '内容违规' in m['content'] for m in msgs)

    # 作者自删不需要原因
    own = client.post('/api/v1/posts', headers=p1, json={'content': '自己删'}).json()['data']['id']
    assert client.delete(f'/api/v1/posts/{own}', headers=p1).status_code == 200


def test_offline_post_client_id_is_idempotent(client):
    """离线发帖重试：同一 client_id 只落一条。"""
    admin = login(client, **ADMIN)
    make_member(client, h(admin['access_token']), 'offline1@test.com', '离线发帖')
    ph = h(login(client, 'offline1@test.com', 'Friend2028')['access_token'])

    payload = {'content': '离线写的动态，联网后自动上传。', 'client_id': 'p-offline-001'}
    first = client.post('/api/v1/posts', headers=ph, json=payload)
    assert first.status_code == 200, first.text
    pid = first.json()['data']['id']
    again = client.post('/api/v1/posts', headers=ph, json=payload)
    assert again.json()['data']['id'] == pid

    feed = client.get('/api/v1/posts', headers=ph).json()['data']
    assert [x['id'] for x in feed].count(pid) == 1


def test_inspiration_submit_and_review(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    make_member(client, ah, 'insp@test.com', '投稿者')
    sh = h(login(client, 'insp@test.com', 'Friend2028')['access_token'])

    created = client.post('/api/v1/inspirations', headers=sh,
                          json={'content': '大雪深埋，静候春来。'})
    assert created.status_code == 200, created.text
    iid = created.json()['data']['id']

    # 审核前公开列表看不到
    public = client.get('/api/v1/inspirations').json()['data']
    assert all(x['id'] != iid for x in public)

    pending = client.get('/api/v1/admin/inspirations', headers=ah).json()['data']
    assert any(x['id'] == iid for x in pending)

    reviewed = client.post(f'/api/v1/admin/inspirations/{iid}/review', headers=ah,
                           json={'action': 'approve', 'note': ''})
    assert reviewed.status_code == 200, reviewed.text

    public2 = client.get('/api/v1/inspirations').json()['data']
    assert any(x['id'] == iid for x in public2)
    msgs = client.get('/api/v1/messages', headers=sh).json()['data']
    assert any('励志' in m['title'] for m in msgs)
