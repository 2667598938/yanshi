import json
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import pytest
from app.tests.test_ai import friend
from app.tests.test_attachment import upload
from app.tests.conftest import login
from app.tests.test_community import ADMIN, h
from app.tests.test_sync import send, session


def save_key(client, headers, images=False, tools=False):
    result = client.put('/api/v1/ai/key', headers=headers, json={'provider': 'deepseek',
        'model': 'test-model', 'api_key': 'secret-test-key-12345',
        'supports_images': images, 'supports_tools': tools})
    assert result.status_code == 200, result.text


def test_image_payload_history_and_cross_account_denied(client, friend, monkeypatch):
    save_key(client, friend, images=True)
    key = upload(client, '/api/v1/attachments/image', friend, 'ai').json()['data']['key']
    captured = []
    async def call(base, key, model, messages, max_tokens):
        captured.append(messages)
        return {'content': 'image answer', 'prompt_tokens': 3, 'completion_tokens': 4, 'latency_ms': 5}
    monkeypatch.setattr('app.services.ai.call_openai', call)
    cid = client.post('/api/v1/ai/conversations', headers=friend, json={}).json()['data']['id']
    result = client.post('/api/v1/ai/chat', headers=friend,
        json={'content': 'explain image', 'image_keys': [key], 'conversation_id': cid})
    assert result.status_code == 200, result.text
    assert captured[0][-1]['content'][1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert client.post('/api/v1/ai/chat', headers=friend,
        json={'content': 'follow up', 'conversation_id': cid}).status_code == 200
    assert isinstance(captured[1][1]['content'], list)
    messages = client.get(f'/api/v1/ai/conversations/{cid}', headers=friend).json()['data']['messages']
    assert messages[0]['image_keys'] == [key]
    ah = h(login(client, **ADMIN)['access_token'])
    client.put('/api/v1/admin/members/1', headers=ah, json={'vip_action': 'permanent', 'note': 'test images entitlement'})
    save_key(client, ah, images=True)
    wrong = client.post('/api/v1/ai/chat', headers=ah, json={'content': 'steal image', 'image_keys': [key]})
    assert wrong.status_code == 400
    assert client.get('/api/v1/ai/usage', headers=ah).json()['data']['requests'] == 0
    save_key(client, friend, images=False)
    assert client.post('/api/v1/ai/chat', headers=friend,
        json={'content': 'image', 'image_keys': [key]}).status_code == 400


def test_same_conversation_busy_lease_and_failure_release(client, friend, monkeypatch):
    save_key(client, friend)
    cid = client.post('/api/v1/ai/conversations', headers=friend, json={}).json()['data']['id']
    entered, release = threading.Event(), threading.Event()
    async def slow(*args):
        import asyncio
        entered.set()
        await asyncio.to_thread(release.wait, 10)
        return {'content': 'done'}
    monkeypatch.setattr('app.services.ai.call_openai', slow)
    with ThreadPoolExecutor(2) as pool:
        running = pool.submit(client.post, '/api/v1/ai/chat', headers=friend,
            json={'content': 'first', 'conversation_id': cid})
        assert entered.wait(5)
        try:
            assert client.post('/api/v1/ai/chat', headers=friend,
                json={'content': 'overlap', 'conversation_id': cid}).status_code == 409
            assert client.delete(f'/api/v1/ai/conversations/{cid}', headers=friend).status_code == 409
        finally: release.set()
        assert running.result().status_code == 200
    assert client.post('/api/v1/ai/chat', headers=friend,
        json={'content': 'after completion', 'conversation_id': cid}).status_code == 200


def test_bounded_agent_tools_own_summary_and_search_sources(client, friend, monkeypatch):
    save_key(client, friend, tools=True)
    client.app.state.settings.brave_search_api_key = 'mock-search-only'
    now = int(time.time() * 1000)
    assert send(client, friend, 'learning-tool-source', [{
        'id': 'focus-1', 'expectedRevision': 0, 'record': session('focus-1', now - 1500000, now)}]).status_code == 200
    seen = []
    async def step(base, key, payload):
        seen.append(payload)
        if len(seen) == 1:
            return {'tool_calls': [
                {'id': 'c1', 'type': 'function', 'function': {'name': 'learning_summary', 'arguments': '{"days":7}'}},
                {'id': 'c2', 'type': 'function', 'function': {'name': 'search_web', 'arguments': '{"query":"考研安排"}'}}]}, {'prompt_tokens': 10}
        return {'content': '根据本人记录和公开来源给出建议'}, {'prompt_tokens': 4, 'completion_tokens': 6}
    async def search(settings, query):
        assert query == '考研安排'
        return {'results': [{'title': 'official page', 'url': 'https://example.com/exam', 'snippet': 'schedule'}]}
    monkeypatch.setattr('app.services.ai_agent.model_step', step)
    monkeypatch.setattr('app.services.ai_agent.search_web', search)
    cid = client.post('/api/v1/ai/conversations', headers=friend, json={}).json()['data']['id']
    response = client.post('/api/v1/ai/chat/stream', headers=friend,
        json={'content': '结合我的学习记录查一下考试安排', 'use_tools': True, 'use_search': True, 'conversation_id': cid})
    events = [json.loads(line[5:]) for line in response.text.splitlines() if line.startswith('data:')]
    done = events[-1]
    assert done['type'] == 'done' and done['prompt_tokens'] == 14 and done['completion_tokens'] == 6
    assert [t['name'] for t in done['tools']] == ['learning_summary', 'search_web']
    assert done['sources'][0]['url'] == 'https://example.com/exam'
    tool_messages = [m for m in seen[1]['messages'] if m['role'] == 'tool']
    assert json.loads(tool_messages[0]['content'])['source'] == '本人已同步记录'
    history = client.get(f'/api/v1/ai/conversations/{cid}', headers=friend).json()['data']['messages']
    assert history[-1]['sources'] == done['sources']
    assert client.get('/api/v1/ai/usage', headers=friend).json()['data']['requests'] == 1


def test_agent_cannot_execute_unknown_write_tool_and_stops_at_bound(client, friend, monkeypatch):
    save_key(client, friend, tools=True)
    attempts = []
    async def loop(base, key, payload):
        attempts.append(payload)
        return {'tool_calls': [{'id': f'call-{len(attempts)}', 'type': 'function',
            'function': {'name': 'delete_all_records', 'arguments': '{}'}}]}, {}
    monkeypatch.setattr('app.services.ai_agent.model_step', loop)
    result = client.post('/api/v1/ai/chat', headers=friend,
        json={'content': 'delete everything', 'use_tools': True})
    assert result.status_code == 502 and len(attempts) == 3
    assert attempts[-1]['tool_choice'] == 'none'
    outputs = [m for m in attempts[-1]['messages'] if m['role'] == 'tool']
    assert all('工具不存在' in json.loads(m['content'])['error'] for m in outputs)
    assert client.get('/api/v1/ai/usage', headers=friend).json()['data']['failed'] == 1


def test_search_requires_configuration_before_charging(client, friend):
    save_key(client, friend, tools=True)
    assert client.post('/api/v1/ai/chat', headers=friend,
        json={'content': 'search', 'use_search': True}).status_code == 503
    assert client.get('/api/v1/ai/usage', headers=friend).json()['data']['requests'] == 0


def test_published_school_images_are_shared_but_private_biz_images_cannot_be_published(client, friend):
    ah = h(login(client, **ADMIN)['access_token'])
    key = upload(client, '/api/v1/attachments/image', ah, 'school').json()['data']['key']
    private = upload(client, '/api/v1/attachments/image', ah, 'mistake').json()['data']['key']
    assert client.get('/api/v1/attachments/view', headers=friend, params={'key': key}).status_code == 404
    assert client.put('/api/v1/admin/schools/pku', headers=ah,
        json={'logo_key': key, 'album_keys': [key]}).status_code == 200
    assert client.get('/api/v1/attachments/view', headers=friend, params={'key': key}).status_code == 200
    assert client.put('/api/v1/admin/schools/pku', headers=ah, json={'album_keys': [private]}).status_code == 400
    assert client.put('/api/v1/admin/schools/pku', headers=ah, json={'logo_key': '', 'album_keys': []}).status_code == 200
    assert client.get('/api/v1/attachments/view', headers=friend, params={'key': key}).status_code == 404
