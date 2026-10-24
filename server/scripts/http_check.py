"""真实 HTTP 冒烟测试：查看原始 JSON（不经过 PowerShell 日期转换）。

管理员账号从环境变量读取：YANSHI_ADMIN_EMAIL / YANSHI_ADMIN_PASSWORD。
"""
import os

import httpx

base = 'http://127.0.0.1:8000'
c = httpx.Client(base_url=base, timeout=10)

print('health      :', c.get('/health').text)
print('public cfg  :', c.get('/api/v1/config/public').text)

r = c.post('/api/v1/auth/login', json={
    'email': os.environ.get('YANSHI_ADMIN_EMAIL', ''),
    'password': os.environ.get('YANSHI_ADMIN_PASSWORD', ''),
})
print('login status:', r.status_code)
assert r.status_code == 200, r.text
data = r.json()['data']
h = {'Authorization': 'Bearer ' + data['access_token']}

print('me          :', c.get('/api/v1/auth/me', headers=h).text)
r = c.post('/api/v1/admin/invites', json={'remark': '研友', 'expires_days': 7}, headers=h)
print('invite raw  :', r.text)
print('members raw :', c.get('/api/v1/admin/members', headers=h).text)

# 未授权访问后台应 401
print('no-token admin:', c.get('/api/v1/admin/members').status_code)
print('ALL OK')
