"""运营体系：VIP 开通 / 功能申请 / 后台审批。"""
from app.tests.conftest import login


def h(t):
    return {'Authorization': 'Bearer ' + t}


def test_vip_redeem_and_admin_adjust(client):
    admin = login(client, 'admin@test.com', 'Admin2028')
    ah = h(admin['access_token'])

    m = client.post('/api/v1/admin/members', headers=ah,
                    json={'email': 'vip1@test.com', 'nickname': '会员甲',
                          'password': 'Friend2028'}).json()['data']
    assert m['is_vip'] is False

    invite = client.post('/api/v1/admin/invites', headers=ah,
                         json={'remark': 'VIP 批次', 'vip_days': 30}).json()['data']
    assert invite['vip_days'] == 30

    member = login(client, 'vip1@test.com', 'Friend2028')
    mh = h(member['access_token'])

    # 状态：非 VIP
    status = client.get('/api/v1/vip/status', headers=mh).json()['data']
    assert status['is_vip'] is False and status['days_left'] == 0

    # 核销邀请码
    r = client.post('/api/v1/vip/redeem', headers=mh, json={'code': invite['code']})
    assert r.status_code == 200, r.text
    data = r.json()['data']
    assert data['is_vip'] is True and data['granted_days'] == 30

    # 同一码不能重复用
    assert client.post('/api/v1/vip/redeem', headers=mh,
                       json={'code': invite['code']}).status_code == 400

    # 后台续期必须填写备注
    assert client.put(f"/api/v1/admin/members/{m['id']}", headers=ah,
                      json={'vip_action': 'renew', 'vip_days': 30,
                            'note': '短'}).status_code == 400
    renewed = client.put(f"/api/v1/admin/members/{m['id']}", headers=ah,
                         json={'vip_action': 'renew', 'vip_days': 30,
                               'note': '研友续期一个月'})
    assert renewed.status_code == 200, renewed.text
    assert renewed.json()['data']['is_vip'] is True

    # 降级
    revoked = client.put(f"/api/v1/admin/members/{m['id']}", headers=ah,
                         json={'vip_action': 'revoke', 'note': '测试降级操作'})
    assert revoked.status_code == 200
    assert revoked.json()['data']['is_vip'] is False


def test_feature_request_flow(client):
    admin = login(client, 'admin@test.com', 'Admin2028')
    ah = h(admin['access_token'])
    client.post('/api/v1/admin/members', headers=ah,
                json={'email': 'req1@test.com', 'nickname': '申请甲',
                      'password': 'Friend2028'})
    member = login(client, 'req1@test.com', 'Friend2028')
    mh = h(member['access_token'])

    created = client.post('/api/v1/requests', headers=mh,
                          json={'feature': 'ai', 'reason': '想用 AI 讲数学题'})
    assert created.status_code == 200, created.text
    rid = created.json()['data']['id']

    # 同类申请不能重复提交
    assert client.post('/api/v1/requests', headers=mh,
                       json={'feature': 'ai', 'reason': '再申请一次试试'}).status_code == 409
    # 后台可见待审
    pending = client.get('/api/v1/admin/requests', headers=ah).json()['data']
    assert any(x['id'] == rid for x in pending)

    # 通过
    reviewed = client.post(f'/api/v1/admin/requests/{rid}/review', headers=ah,
                           json={'action': 'approve', 'note': '同意，注意自备 Key'})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()['data']['status'] == 'approved'

    mine = client.get('/api/v1/requests/mine', headers=mh).json()['data']
    assert mine[0]['status'] == 'approved' and mine[0]['review_note']

    # 已处理的不能再审
    assert client.post(f'/api/v1/admin/requests/{rid}/review', headers=ah,
                       json={'action': 'reject', 'note': '重复处理'}).status_code == 400

    # 撤回仅限审核中
    second = client.post('/api/v1/requests', headers=mh,
                         json={'feature': 'materials', 'reason': '需要完整资料链接'})
    rid2 = second.json()['data']['id']
    assert client.post(f'/api/v1/requests/{rid2}/withdraw', headers=mh).status_code == 200
    assert client.post(f'/api/v1/requests/{rid2}/withdraw', headers=mh).status_code == 400
