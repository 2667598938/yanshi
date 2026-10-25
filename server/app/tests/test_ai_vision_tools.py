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
    assert isinstance(captured[1][2]['content'], list)
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


@pytest.mark.parametrize('flag', ['use_tools','use_search'])
def test_v1_rejects_general_tools_even_if_legacy_flags_enabled(client,friend,flag,monkeypatch):
    save_key(client,friend,tools=True)
    client.app.state.settings.ai_tools_enabled=True
    client.app.state.settings.brave_search_api_key='legacy-config'
    async def forbidden(*args): raise AssertionError('V1 must never invoke an agent')
    monkeypatch.setattr('app.services.ai_agent.model_step',forbidden)
    result=client.post('/api/v1/ai/chat',headers=friend,json={'content':'不允许自动操作',flag:True})
    assert result.status_code==403
    assert client.get('/api/v1/ai/usage',headers=friend).json()['data']['requests']==0


def test_published_school_images_are_shared_but_private_biz_images_cannot_be_published(client, friend):
    ah = h(login(client, **ADMIN)['access_token'])
    key = upload(client, '/api/v1/attachments/image', ah, 'school').json()['data']['key']
    private = upload(client, '/api/v1/attachments/image', ah, 'mistake').json()['data']['key']
    assert client.get('/api/v1/attachments/view', headers=friend, params={'key': key}).status_code == 404
    assert client.put('/api/v1/admin/schools/pku', headers=ah,
        json={'logo_key': key, 'album_keys': [key]}).status_code == 200
    assert client.get('/api/v1/attachments/view', headers=friend, params={'key': key}).status_code == 404
    assert client.put('/api/v1/admin/schools/pku', headers=ah, json={'album_keys': [private]}).status_code == 400
    assert client.put('/api/v1/admin/schools/pku', headers=ah, json={'logo_key': '', 'album_keys': []}).status_code == 200
    assert client.get('/api/v1/attachments/view', headers=friend, params={'key': key}).status_code == 404
