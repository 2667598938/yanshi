import asyncio
import json
import httpx
import pytest
from app.errors import ApiError
from app.services import ai, ai_agent
from app.services.outbound import validate_ai_base
from app.config import Settings


def mock_async(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


def test_multimodal_model_catalog_metadata_and_unknowns(monkeypatch):
    def handle(request):
        assert request.url.path == '/v1/models'
        return httpx.Response(200, json={'data': [
            {'id': 'vision-model', 'context_length': 32000, 'capabilities': {'vision': True}},
            {'id': 'unknown-model'}, {'id': 123}, {'id': 'vision-model'}]})
    mock_async(monkeypatch, handle)
    result = asyncio.run(ai.fetch_models('https://provider.example/v1', 'mock-key'))
    assert result == ['vision-model', 'unknown-model']
    assert result.details[0]['context_length'] == 32000 and result.details[0]['supports_images']
    assert result.details[1]['context_length'] is None and result.details[1]['supports_images'] is None


@pytest.mark.parametrize('complete', [True, False])
def test_upstream_sse_completion_required(monkeypatch, complete):
    def handle(request):
        payload = json.loads(request.content)
        assert payload['messages'][0]['content'][1]['type'] == 'image_url'
        data = 'data: ' + json.dumps({'choices': [{'delta': {'content': 'image answer'}}]}) + '\n\n'
        if complete: data += 'data: [DONE]\n\n'
        return httpx.Response(200, text=data, headers={'content-type': 'text/event-stream'})
    mock_async(monkeypatch, handle)
    async def read():
        return [chunk async for chunk in ai.stream_openai('https://provider.example/v1', 'mock', 'vision',
            [{'role': 'user', 'content': [{'type': 'text', 'text': 'question'},
                {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,AAAA'}}]}])]
    if complete: assert asyncio.run(read())[0]['delta'] == 'image answer'
    else:
        with pytest.raises(ApiError, match='提前结束'): asyncio.run(read())


def test_search_protocol_filters_unsafe_sources_and_uses_server_key(monkeypatch):
    def handle(request):
        assert request.url.host == 'api.search.brave.com'
        assert request.headers['X-Subscription-Token'] == 'mock-search-secret'
        assert request.url.params['q'] == '考研时间'
        return httpx.Response(200, json={'web': {'results': [
            {'title': 'official', 'url': 'https://example.com/exam', 'description': '<b>time</b>'},
            {'title': 'bad', 'url': 'javascript:alert(1)', 'description': 'bad'}]}})
    mock_async(monkeypatch, handle)
    result = asyncio.run(ai_agent.search_web(Settings(_env_file=None, brave_search_api_key='mock-search-secret'), '考研时间'))
    assert len(result['results']) == 1 and result['results'][0]['snippet'] == 'time'


def test_production_ai_egress_allowlist():
    settings = Settings(_env_file=None, environment='production')
    for url in ('http://api.deepseek.com/v1', 'https://127.0.0.1/v1',
                'https://attacker.example/v1', 'https://user:pass@api.deepseek.com/v1'):
        with pytest.raises(ApiError): validate_ai_base(settings, url)
    assert validate_ai_base(settings, 'https://api.deepseek.com/v1')
    settings.ai_custom_hosts = 'gateway.example.com'
    assert validate_ai_base(settings, 'https://gateway.example.com/v1')
