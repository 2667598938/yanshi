"""真实火山方舟 AI 冒烟：登录管理员 → 一次性问答（非会话），验证服务端代理连通。

管理员账号从环境变量读取：YANSHI_ADMIN_EMAIL / YANSHI_ADMIN_PASSWORD。
"""
import os

import httpx

base = 'http://127.0.0.1:8000'
c = httpx.Client(base_url=base, timeout=90)

r = c.post('/api/v1/auth/login', json={
    'email': os.environ.get('YANSHI_ADMIN_EMAIL', ''),
    'password': os.environ.get('YANSHI_ADMIN_PASSWORD', ''),
})
print('login status:', r.status_code)
assert r.status_code == 200, r.text
h = {'Authorization': 'Bearer ' + r.json()['data']['access_token']}

print('enabled:', c.get('/api/v1/ai/enabled', headers=h).text)
print('scenes :', c.get('/api/v1/ai/scenes', headers=h).text)

r = c.post('/api/v1/ai/chat', headers=h,
           json={'scene': 'general', 'content': '用一句话给考研的同学打气，不要超过30字。'})
print('chat status:', r.status_code)
print('chat raw   :', r.text)
assert r.status_code == 200, r.text
assert r.json()['data']['reply']
print('AI SMOKE OK')
