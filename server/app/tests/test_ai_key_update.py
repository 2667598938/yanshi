from app.models import UserAIKey
from app.tests.test_ai import friend
from app.errors import ApiError
import asyncio
import pytest
from starlette.requests import Request
from app.models import User, AIConversation
from app.schemas.ai import ChatInput
from app.routers.ai import chat_stream


def test_change_model_reuses_cipher_but_never_sends_key_to_other_provider(client, friend):
    uid = client.get('/api/v1/auth/me', headers=friend).json()['data']['id']
    with client.app.state.session_factory() as db:
        original = db.get(UserAIKey, uid).key_cipher
    response = client.put('/api/v1/ai/key', headers=friend, json={
        'provider': 'deepseek', 'model': 'new-available-model'})
    assert response.status_code == 200, response.text
    assert response.json()['data']['model'] == 'new-available-model'
    assert 'isolated-byok-test-key' not in response.text
    with client.app.state.session_factory() as db:
        assert db.get(UserAIKey, uid).key_cipher == original
    for body in [
        {'provider': 'openai', 'model': 'other-model'},
        {'provider': 'deepseek', 'base_url': 'https://api.deepseek.com/other', 'model': 'other-model'},
    ]:
        assert client.put('/api/v1/ai/key', headers=friend, json=body).status_code == 400
    assert client.delete('/api/v1/ai/key', headers=friend).status_code == 200
    assert client.put('/api/v1/ai/key', headers=friend, json={'provider': 'deepseek', 'model': 'no-key'}).status_code == 400


def test_partial_stream_survives_reopening_history_but_cannot_import_tasks(client, friend, monkeypatch):
    partial = '先复习数学。\n```yanshi_tasks\n{"tasks":[{"title":"复习数学","estimated_min":30}]}\n```'
    async def interrupted(settings, messages):
        yield {'delta': partial}
        raise ApiError(502, 50201, '供应商中途断开')
    monkeypatch.setattr('app.services.ai.stream_ark', interrupted)
    cid = client.post('/api/v1/ai/conversations', headers=friend, json={}).json()['data']['id']
    response = client.post('/api/v1/ai/chat/stream', headers=friend, json={'conversation_id': cid, 'content': '安排明天计划'})
    assert response.status_code == 200 and '"type": "error"' in response.text
    messages = client.get(f'/api/v1/ai/conversations/{cid}', headers=friend).json()['data']['messages']
    assert messages[-1]['role'] == 'assistant'
    assert messages[-1]['content'] == partial
    assert messages[-1]['interrupted'] is True and messages[-1]['failed'] is True
    assert messages[-1]['suggested_tasks'] == []
    assert client.post(f'/api/v1/ai/messages/{messages[-1]["id"]}/import-tasks',
        headers=friend, json={'confirmed': True}).status_code == 400


def test_cancelled_stream_preserves_partial_and_releases_conversation(client, friend, monkeypatch):
    async def cancelled(settings, messages):
        yield {'delta': '已经读到的推导过程'}
        raise asyncio.CancelledError()
    monkeypatch.setattr('app.services.ai.stream_ark', cancelled)
    uid = client.get('/api/v1/auth/me', headers=friend).json()['data']['id']
    cid = client.post('/api/v1/ai/conversations', headers=friend, json={}).json()['data']['id']
    async def consume():
        with client.app.state.session_factory() as db:
            request = Request({'type': 'http', 'app': client.app, 'headers': [], 'client': ('testclient', 0)})
            response = await chat_stream(ChatInput(conversation_id=cid, content='请讲解'), request, db.get(User, uid), db)
            iterator = response.body_iterator
            assert 'delta' in await anext(iterator)
            with pytest.raises(asyncio.CancelledError):
                await anext(iterator)
    asyncio.run(consume())
    messages = client.get(f'/api/v1/ai/conversations/{cid}', headers=friend).json()['data']['messages']
    assert messages[-1]['content'] == '已经读到的推导过程'
    assert messages[-1]['aborted'] is True
    with client.app.state.session_factory() as db:
        assert db.get(AIConversation, cid).busy_until is None
