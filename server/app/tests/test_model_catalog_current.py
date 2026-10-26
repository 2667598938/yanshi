import asyncio
import httpx
import pytest
from app.tests.test_ai import friend
from app.services.ai import fetch_models, failed_catalog

@pytest.mark.parametrize('status,code',[(401,'AI_KEY_INVALID'),(402,'AI_NO_QUOTA'),(404,'AI_NO_MODELS_API'),(429,'AI_RATE_LIMITED'),(500,'AI_UPSTREAM_ERROR')])
def test_model_catalog_classifies_without_exposing_provider_secrets(monkeypatch,status,code):
 class FakeClient:
  def __init__(self,**kwargs):pass
  async def __aenter__(self):return self
  async def __aexit__(self,*args):pass
  async def get(self,*args,**kwargs):return httpx.Response(status,json={'error':'secret-provider-key'},headers={'Retry-After':'99'})
 monkeypatch.setattr('app.services.ai.httpx.AsyncClient',FakeClient)
 result=asyncio.run(fetch_models('https://api.deepseek.com/v1','private-key'))
 assert not result and result.error['code']==code
 assert 'secret-provider-key' not in str(result.error) and 'private-key' not in str(result.error)
 if status==429:assert result.error['retry_after']==99

def test_force_refresh_and_invalid_key_does_not_reuse_cached_catalog(client,friend,monkeypatch):
 calls=[]
 async def models(*args):
  calls.append(1)
  return ['real-model'] if len(calls)==1 else failed_catalog('AI_KEY_INVALID')
 monkeypatch.setattr('app.services.ai.fetch_models',models)
 body={'provider':'deepseek','api_key':'secret-test'}
 assert client.post('/api/v1/ai/models',headers=friend,json=body).json()['data']['models']==['real-model']
 assert client.post('/api/v1/ai/models',headers=friend,json=body).json()['data']['cached']
 failed=client.post('/api/v1/ai/models',headers=friend,json={**body,'force_refresh':True}).json()['data']
 assert len(calls)==2 and failed['models']==[] and failed['error']['code']=='AI_KEY_INVALID'


def test_concurrent_catalog_requests_share_one_provider_call(client,friend,monkeypatch):
 from concurrent.futures import ThreadPoolExecutor
 from threading import Barrier
 gate=Barrier(2);calls=[]
 async def models(*args):
  calls.append(1);await asyncio.sleep(0.15);return ['one-real-model']
 monkeypatch.setattr('app.services.ai.fetch_models',models)
 def request(_):
  gate.wait(timeout=5)
  response=client.post('/api/v1/ai/models',headers=friend,json={'provider':'deepseek','api_key':'concurrent-key','force_refresh':True})
  assert response.status_code==200,response.text
  return response.json()['data']
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(request,range(2)))
 assert len(calls)==1
 assert all(r['models']==['one-real-model'] for r in results)
