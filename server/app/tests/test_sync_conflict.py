"""学习同步冲突 / 边界专项（第二优先级清单补强，只测不改业务）。

覆盖：正常增量 push/pull 一致性、双设备同记录 40902（带服务端版本）、
不存在记录的 expectedRevision 冲突、单条超 2MB 配额 41301、
软删墓碑后重新激活、整批多记录一致性。
"""
import uuid

from app.tests.conftest import login

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def h_of(token):
    return {'Authorization': 'Bearer ' + token}


def op_id():
    return uuid.uuid4().hex


def send(client, h, operation_id, changes):
    return client.post('/api/v1/sync/commands',
                       json={'operationId': operation_id, 'changes': changes}, headers=h)


def subject(rid, name='数学'):
    return {'id': rid, 'type': 'subject', 'name': name, 'color': '#1a73e8', 'icon': 'math',
            'tags': [], 'order': 0, 'archived': 0, 'builtin': 0, 'createdAt': 1700000000000}


def task(rid, title='做极限'):
    return {'id': rid, 'type': 'task', 'title': title, 'subjectId': 's1', 'phase': 'base',
            'acceptCriteria': '', 'dueDate': '', 'done': 0, 'doneAt': 0, 'createdAt': 1700000000000}


def pull(client, h):
    return client.get('/api/v1/sync/records', headers=h).json()['data']['records']


def test_push_pull_consistency_multi_records(client):
    """正常增量：一次 push 两条记录，pull 后条数 / revision / 内容完全一致。"""
    h = h_of(login(client, **ADMIN)['access_token'])
    changes = [
        {'id': 's1', 'expectedRevision': 0, 'record': subject('s1', '数据结构')},
        {'id': 'k1', 'expectedRevision': 0, 'record': task('k1', '刷第一章')},
    ]
    r = send(client, h, op_id(), changes)
    assert r.status_code == 200, r.text
    changed = {c['id']: c for c in r.json()['data']['changed']}
    assert changed['s1']['revision'] == 1
    assert changed['k1']['revision'] == 1

    records = {x['id']: x for x in pull(client, h)}
    assert set(records) == {'s1', 'k1'}
    assert records['s1']['revision'] == 1 and records['s1']['record']['name'] == '数据结构'
    assert records['k1']['revision'] == 1 and records['k1']['record']['title'] == '刷第一章'


def test_two_device_conflict_returns_server_version(client):
    """同账号两次会话（设备 A / 设备 B）基于过期 expectedRevision 改同一条记录：
    设备 B 收到 40902，data.conflicts 带回服务端当前 revision 与记录内容。"""
    h_a = h_of(login(client, **ADMIN)['access_token'])  # 设备 A
    h_b = h_of(login(client, **ADMIN)['access_token'])  # 设备 B（同账号另一次登录）

    # 设备 A 创建 m1 -> revision 1
    r = send(client, h_a, op_id(), [{'id': 'm1', 'expectedRevision': 0, 'record': subject('m1', '设备一')}])
    assert r.status_code == 200, r.text
    assert r.json()['data']['changed'][0]['revision'] == 1

    # 设备 B 仍以为 m1 不存在（expectedRevision=0），抢先写入 -> 40902
    r = send(client, h_b, op_id(), [{'id': 'm1', 'expectedRevision': 0, 'record': subject('m1', '设备二强改')}])
    assert r.status_code == 409, r.text
    body = r.json()
    assert body['code'] == 40902
    conf = body['data']['conflicts'][0]
    assert conf['id'] == 'm1'
    assert conf['revision'] == 1                 # 服务端真实版本
    assert conf['record']['name'] == '设备一'    # 服务端真实内容

    # 设备 A 基于 revision 1 继续推进 -> revision 2
    r = send(client, h_a, op_id(), [{'id': 'm1', 'expectedRevision': 1, 'record': subject('m1', '设备一再改')}])
    assert r.status_code == 200, r.text
    assert r.json()['data']['changed'][0]['revision'] == 2


def test_conflict_on_nonexistent_record(client):
    """对服务端不存在的记录提交不匹配的 expectedRevision（=7）-> 40902，
    conflicts.revision=0 且 record=null（表示云端尚无此记录）。"""
    h = h_of(login(client, **ADMIN)['access_token'])
    r = send(client, h, op_id(), [{'id': 'ghost', 'expectedRevision': 7, 'record': subject('ghost')}])
    assert r.status_code == 409, r.text
    assert r.json()['code'] == 40902
    conf = r.json()['data']['conflicts'][0]
    assert conf['revision'] == 0
    assert conf['record'] is None
    # 该记录并未被写入
    assert all(x['id'] != 'ghost' for x in pull(client, h))


def test_single_record_too_large_rejected_41301(client):
    """单条记录 body 超过 2MB -> 413 / 41301，且该条不落库。"""
    h = h_of(login(client, **ADMIN)['access_token'])
    big = subject('big1')
    big['note'] = 'x' * (2 * 1024 * 1024 + 5000)   # 纯 ASCII，字节数≈字符数
    r = send(client, h, op_id(), [{'id': 'big1', 'expectedRevision': 0, 'record': big}])
    assert r.status_code == 413, r.text
    assert r.json()['code'] == 41301
    # 失败回滚：服务端没有这条记录
    assert all(x['id'] != 'big1' for x in pull(client, h))


def test_soft_delete_tombstone_then_reactivate(client):
    """record=null 软删后 pull 返回墓碑（record=null）；基于墓碑 revision 重新写入同 id 可复活。"""
    h = h_of(login(client, **ADMIN)['access_token'])
    # 创建 -> rev1
    r = send(client, h, op_id(), [{'id': 'z1', 'expectedRevision': 0, 'record': task('z1', '待删')}])
    assert r.status_code == 200 and r.json()['data']['changed'][0]['revision'] == 1
    # 软删 -> rev2（墓碑）
    r = send(client, h, op_id(), [{'id': 'z1', 'expectedRevision': 1, 'record': None}])
    assert r.status_code == 200 and r.json()['data']['changed'][0]['revision'] == 2

    row = next(x for x in pull(client, h) if x['id'] == 'z1')
    assert row['revision'] == 2 and row['record'] is None   # 墓碑

    # 基于墓碑 revision=2 重新推送同 id -> 复活为 rev3
    r = send(client, h, op_id(), [{'id': 'z1', 'expectedRevision': 2, 'record': task('z1', '复活后')}])
    assert r.status_code == 200, r.text
    assert r.json()['data']['changed'][0]['revision'] == 3
    row = next(x for x in pull(client, h) if x['id'] == 'z1')
    assert row['record']['title'] == '复活后'


def test_replay_keeps_single_record(client):
    """幂等重放后 pull 仍只有一条记录、revision 不增长。"""
    h = h_of(login(client, **ADMIN)['access_token'])
    payload = [{'id': 'rp1', 'expectedRevision': 0, 'record': subject('rp1', '幂等')}]
    op = op_id()
    first = send(client, h, op, payload)
    assert first.status_code == 200 and first.json()['data']['changed'][0]['revision'] == 1
    replay = send(client, h, op, payload)
    assert replay.status_code == 200 and replay.json()['data']['changed'][0]['revision'] == 1
    records = pull(client, h)
    assert len(records) == 1 and records[0]['revision'] == 1
