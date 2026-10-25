from app.tests.test_ai import friend, fake_ark


def test_budget_survives_new_requests_and_context_zero(client, friend, fake_ark):
    client.app.state.settings.ai_daily_limit = 2
    assert client.put('/api/v1/ai/preferences', headers=friend,
                      json={'context_turns': 0}).status_code == 200
    cid = client.post('/api/v1/ai/conversations', headers=friend, json={}).json()['data']['id']
    for text in ('first', 'second'):
        assert client.post('/api/v1/ai/chat', headers=friend,
            json={'conversation_id': cid, 'content': text}).status_code == 200
    assert len(fake_ark['messages']) == 2
    assert client.post('/api/v1/ai/chat', headers=friend, json={'content': 'third'}).status_code == 429
    usage = client.get('/api/v1/ai/usage', headers=friend).json()['data']
    assert (usage['requests'], usage['succeeded'], usage['remaining']) == (2, 2, 0)
    assert client.put('/api/v1/ai/preferences', headers=friend,
                      json={'context_turns': 51}).status_code == 400


def test_failed_provider_charged_and_reported(client, friend, monkeypatch):
    from app.errors import ApiError
    async def fail(*args): raise ApiError(502, 50201, 'mock unavailable')
    monkeypatch.setattr('app.services.ai.call_ark', fail)
    assert client.post('/api/v1/ai/chat', headers=friend, json={'content': 'question'}).status_code == 502
    usage = client.get('/api/v1/ai/usage', headers=friend).json()['data']
    assert (usage['requests'], usage['failed'], usage['succeeded']) == (1, 1, 0)


def test_models_cache_scoped_to_key_and_stale_fallback(client, friend, monkeypatch):
    calls = []
    async def models(base, key):
        calls.append(key)
        return ['model-a'] if len(calls) < 3 else []
    monkeypatch.setattr('app.services.ai.fetch_models', models)
    def fetch(key):
        return client.post('/api/v1/ai/models', headers=friend,
            json={'provider': 'deepseek', 'api_key': key}).json()['data']
    assert fetch('secret-a')['models'] == ['model-a']
    assert fetch('secret-a')['cached']
    assert fetch('secret-b')['models'] == ['model-a']
    assert calls == ['secret-a', 'secret-b']
    from app.models.ai import AIModelCache
    from app.time import utcnow
    from datetime import timedelta
    from sqlalchemy import select
    with client.app.state.session_factory() as db:
        for row in db.scalars(select(AIModelCache)).all():
            row.fetched_at = utcnow() - timedelta(days=2)
        db.commit()
    assert fetch('secret-a')['stale']
