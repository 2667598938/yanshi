"""AI 助教（v0.3-e）测试：mock 火山方舟，不打真实网络。"""
import json

import pytest

from app.tests.conftest import login

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def h(token):
    return {'Authorization': 'Bearer ' + token}


@pytest.fixture
def friend(client):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    client.post('/api/v1/admin/members', headers=ah,
                json={'email': 'ai1@test.com', 'nickname': 'AI同学', 'password': 'Friend2028'})
    return h(login(client, 'ai1@test.com', 'Friend2028')['access_token'])


@pytest.fixture
def fake_ark(monkeypatch):
    captured = {}

    async def fake_call(settings, messages):
        captured['messages'] = messages
        captured['model'] = settings.volc_model
        return '模拟回复：' + messages[-1]['content']

    import app.services.ai as svc
    monkeypatch.setattr(svc, 'call_ark', fake_call)
    return captured


def test_chat_without_conversation(client, friend, fake_ark):
    r = client.post('/api/v1/ai/chat', headers=friend,
                    json={'scene': 'kaoyan', 'content': '讲一下极限的定义'})
    assert r.status_code == 200, r.text
    data = r.json()['data']
    assert data['reply'].startswith('模拟回复')
    assert 'conversation_id' not in data
    # system 人设已带上
    assert fake_ark['messages'][0]['role'] == 'system'
    assert '考研' in fake_ark['messages'][0]['content']


def test_conversation_history_and_lifecycle(client, friend, fake_ark):
    # 建会话
    c = client.post('/api/v1/ai/conversations', headers=friend,
                    json={'title': '数学答疑', 'scene': 'kaoyan'})
    assert c.status_code == 200, c.text
    cid = c.json()['data']['id']

    # 两轮对话
    for q in ('第一题', '第二题'):
        r = client.post('/api/v1/ai/chat', headers=friend,
                        json={'conversation_id': cid, 'content': q})
        assert r.status_code == 200, r.text
        assert r.json()['data']['conversation_id'] == cid

    # 第二轮应带历史（system + 上一轮 user/assistant + 本轮 user）
    assert len(fake_ark['messages']) == 4

    detail = client.get(f'/api/v1/ai/conversations/{cid}', headers=friend).json()['data']
    assert len(detail['messages']) == 4
    assert detail['messages'][0]['role'] == 'user'
    assert detail['messages'][1]['role'] == 'assistant'
    assert detail['title'] == '数学答疑'

    # 改标题
    assert client.put(f'/api/v1/ai/conversations/{cid}', headers=friend,
                      json={'title': '高数专题'}).status_code == 200
    # 删除
    assert client.delete(f'/api/v1/ai/conversations/{cid}', headers=friend).status_code == 200
    assert client.get(f'/api/v1/ai/conversations/{cid}', headers=friend).status_code == 404


def test_cannot_access_other_conversation(client, friend, fake_ark):
    admin = login(client, **ADMIN)
    ah = h(admin['access_token'])
    c = client.post('/api/v1/ai/conversations', headers=friend, json={'title': '我的'})
    cid = c.json()['data']['id']
    # 管理员也不能看别人的会话（隔离）
    assert client.get(f'/api/v1/ai/conversations/{cid}', headers=ah).status_code == 404


def test_ai_disabled_without_key(client, friend):
    # conftest 未配置 key，未打补丁时应返回 503
    r = client.post('/api/v1/ai/chat', headers=friend, json={'content': 'hi'})
    assert r.status_code == 503
    assert client.get('/api/v1/ai/enabled', headers=friend).json()['data']['enabled'] is False


def test_chat_stream_sse(client, friend, monkeypatch):
    """流式对话：逐段 delta + 结束事件，并落库到会话。"""
    async def fake_stream(settings, messages):
        for part in ('流式', '回复'):
            yield {'delta': part}
        yield {'usage': {'prompt_tokens': 3, 'completion_tokens': 2}, 'latency_ms': 12}

    import app.services.ai as svc
    monkeypatch.setattr(svc, 'stream_ark', fake_stream)

    cid = client.post('/api/v1/ai/conversations', headers=friend,
                      json={'title': '流式测试'}).json()['data']['id']
    with client.stream('POST', '/api/v1/ai/chat/stream', headers=friend,
                       json={'conversation_id': cid, 'content': '你好'}) as r:
        assert r.status_code == 200
        assert r.headers['content-type'].startswith('text/event-stream')
        body = ''.join(r.iter_text())

    events = [json.loads(line[5:]) for line in body.splitlines()
              if line.startswith('data:')]
    assert [e['text'] for e in events if e['type'] == 'delta'] == ['流式', '回复']
    done = events[-1]
    assert done['type'] == 'done'
    assert done['reply'] == '流式回复'
    assert done['conversation_id'] == cid
    assert done['prompt_tokens'] == 3

    detail = client.get(f'/api/v1/ai/conversations/{cid}', headers=friend).json()['data']
    assert [m['role'] for m in detail['messages']] == ['user', 'assistant']
    assert detail['messages'][-1]['content'] == '流式回复'


def test_scenes(client, friend):
    rows = client.get('/api/v1/ai/scenes', headers=friend).json()['data']
    keys = {s['key'] for s in rows}
    assert keys == {'general', 'kaoyan', 'essay', 'plan', 'review'}
