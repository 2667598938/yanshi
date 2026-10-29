import json
from datetime import timedelta, timezone
from app.tests.test_ai import friend
from app.tests.test_current_workflows import admin, me
from app.tests.test_group_v1 import push
from app.tests.conftest import login
from app.services.ai_context import account_context
from app.time import utcnow


def test_private_note_full_form_does_not_reopen_approved_review(client, friend):
    ah = admin(client)
    body = {'title': '资料原版', 'url': 'https://pan.quark.cn/s/test',
            'code': '', 'category': '英语', 'intro': '简介', 'personal_note': '旧备注'}
    row = client.post('/api/v1/resources', headers=friend, json=body).json()['data']
    rid = row['id']
    assert client.post(f'/api/v1/admin/resources/{rid}/review', headers=ah,
                       json={'action': 'approve', 'expected_revision': 1}).status_code == 200
    edited = client.put(f'/api/v1/resources/{rid}', headers=friend,
                        json={**body, 'personal_note': '只改我的备注', 'expected_revision': 2})
    assert edited.status_code == 200, edited.text
    data = edited.json()['data']
    assert data['review_status'] == 'approved' and data['personal_note'] == '只改我的备注'
    assert not client.get('/api/v1/admin/resources', headers=ah).json()['data']['items']
    assert 'personal_note' not in client.get(f'/api/v1/resources/{rid}', headers=ah).json()['data']
    assert client.put(f'/api/v1/resources/{rid}', headers=friend,
                      json={'title': '真正修改公开内容', 'expected_revision': 3}).json()['data']['review_status'] == 'pending'


def test_ai_summary_prioritizes_recent_accomplishments_and_balances_lists(client, friend):
    now = utcnow()
    current = int(now.replace(tzinfo=timezone.utc).timestamp() * 1000)
    old = int((now-timedelta(days=70)).replace(tzinfo=timezone.utc).timestamp() * 1000)
    records = [{'id': f'pending-{i}', 'type': 'task', 'title': f'待办{i}', 'done': 0} for i in range(20)]
    records += [{'id': 'aaa-new', 'type': 'task', 'title': '今日成果', 'done': 1, 'doneAt': current}]
    records += [{'id': f'zzz-old-{i}', 'type': 'task', 'title': f'旧成果{i}', 'done': 1, 'doneAt': old} for i in range(6)]
    push(client, friend, records)
    uid = me(client, friend)
    with client.app.state.session_factory() as db:
        full = account_context(db, uid, 4000)
        assert full['tasks']['completed'][0]['title'] == '今日成果'
        assert full['tasks']['completed'][0]['completed_on'] == (now+timedelta(hours=8)).date().isoformat()
        assert full['recent_7_days']['completed'] == 1
        limited = account_context(db, uid, 1200)
        assert limited['task_list_truncated']
        assert limited['tasks']['completed'][0]['title'] == '今日成果'
        assert limited['tasks']['pending']
        assert len(json.dumps(limited, ensure_ascii=False, separators=(',', ':')).encode()) <= 1040


def test_configured_defaults_reach_admin_created_accounts_and_personal_nodes(client):
    ah = admin(client)
    assert client.put('/api/v1/admin/config', headers=ah,
                      json={'exam_year': 2031, 'exam_date': '2030-12-21'}).status_code == 200
    created = client.post('/api/v1/admin/members', headers=ah,
                          json={'email': 'defaults@test.com', 'nickname': '默认值同学', 'password': 'Defaults2028'})
    assert created.status_code == 200, created.text
    session = login(client, 'defaults@test.com', 'Defaults2028')
    h = {'Authorization': 'Bearer '+session['access_token']}
    user = client.get('/api/v1/auth/me', headers=h).json()['data']
    assert user['exam_year'] == 2031 and user['exam_date'] == '2030-12-21'
    nodes = client.get('/api/v1/time-nodes', headers=h).json()['data']
    dates = {n['node_name']: n['target_date'] for n in nodes}
    assert dates == {'考研初试': '2030-12-21', '初试出分': '2031-02-20'}
    client.put('/api/v1/admin/config', headers=ah, json={'exam_date': '2032-12-25'})
    assert client.get('/api/v1/time-nodes', headers=h).json()['data'] == nodes


def test_public_disclosure_matches_default_sharing_and_ai_summary(client):
    data = client.get('/api/v1/legal').json()['data']
    assert data['version'] == '2026-10-29'
    assert '同一好友房间中已确认共享的成员默认只读' in data['privacy']
    assert '管理员建号和VIP兑换不自动加入房间' in data['privacy']
    assert '本人学习摘要' in data['privacy']
    assert 'API Key及资料个人备注不参与共享' in data['privacy']
    assert '默认仅本人可见' not in data['terms']
    assert '看不到你的错题' not in data['privacy']


def test_expired_ai_access_does_not_block_masked_key_read_or_owner_deletion(client, friend):
    ah = admin(client)
    uid = me(client, friend)
    assert client.put('/api/v1/ai/key', headers=friend, json={
        'provider': 'deepseek', 'model': 'deepseek-chat', 'api_key': 'private-owner-key-1234'}).status_code == 200
    revoked = client.put(f'/api/v1/admin/members/{uid}', headers=ah,
                         json={'vip_action': 'revoke', 'note': '测试到期后的数据管理'})
    assert revoked.status_code == 200, revoked.text
    assert not client.get('/api/v1/ai/enabled', headers=friend).json()['data']['access']
    metadata = client.get('/api/v1/ai/key', headers=friend)
    assert metadata.status_code == 200 and metadata.json()['data']['configured']
    assert 'private-owner-key-1234' not in metadata.text
    assert client.get('/api/v1/ai/key', headers=ah).json()['data']['configured'] is False
    assert client.post('/api/v1/ai/models', headers=friend, json={'api_key': 'private-owner-key-1234'}).status_code == 403
    assert client.post('/api/v1/ai/chat', headers=friend, json={'content': '禁止调用'}).status_code == 403
    assert client.delete('/api/v1/ai/key', headers=friend).status_code == 200
    assert not client.get('/api/v1/ai/key', headers=friend).json()['data']['configured']
