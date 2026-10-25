"""学习数据同步（v0.3-b）端到端测试。"""
import uuid

from app.tests.conftest import login, read_latest_code

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def headers(client):
    return {'Authorization': 'Bearer ' + login(client, **ADMIN)['access_token']}


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


def session(rid, started, ended, paused=0, status='done'):
    return {'id': rid, 'type': 'session', 'subjectId': 's1', 'mode': 'stopwatch',
            'activityType': '', 'plannedMin': 0, 'actualSec': 0, 'status': status,
            'startedAt': started, 'endedAt': ended, 'pauseAccum': paused,
            'date': '2026-10-25', 'note': '', 'createdAt': ended}


def test_session_is_normalized_by_server(client):
    h = headers(client)
    base = 1700000000000

    # 挂起 5 小时：服务端按 180 分钟上限记为 quit(timeout)
    r = send(client, h, op_id(), [
        {'id': 'x1', 'expectedRevision': 0,
         'record': session('x1', base, base + 5 * 3600 * 1000)}])
    assert r.status_code == 200, r.text
    rec = r.json()['data']['changed'][0]['record']
    assert rec['status'] == 'quit'
    assert rec['actualSec'] == 180 * 60
    assert rec['end_reason'] == 'timeout'

    # 暂停累计 31 分钟：按暂停超时 quit，实际时长扣除暂停
    r = send(client, h, op_id(), [
        {'id': 'x2', 'expectedRevision': 0,
         'record': session('x2', base, base + 3600 * 1000, paused=31 * 60 * 1000)}])
    rec = r.json()['data']['changed'][0]['record']
    assert rec['status'] == 'quit'
    assert rec['end_reason'] == 'pause_timeout'
    assert rec['actualSec'] == 3600 - 31 * 60

    # 正常完成：状态 done，小于上限
    r = send(client, h, op_id(), [
        {'id': 'x3', 'expectedRevision': 0,
         'record': session('x3', base, base + 25 * 60 * 1000)}])
    rec = r.json()['data']['changed'][0]['record']
    assert rec['status'] == 'done'
    assert rec['actualSec'] == 25 * 60
    assert rec['end_reason'] == 'completed'


def test_sync_requires_auth(client):
    assert client.get('/api/v1/sync/records').status_code == 401
    assert client.post('/api/v1/sync/commands', json={'operationId': 'x', 'changes': []}).status_code == 401


def test_create_update_and_conflict(client):
    h = headers(client)
    # 初始为空
    assert client.get('/api/v1/sync/records', headers=h).json()['data']['records'] == []

    # 创建 s1 -> revision 1
    r = send(client, h, op_id(), [{'id': 's1', 'expectedRevision': 0, 'record': subject('s1')}])
    assert r.status_code == 200, r.text
    assert r.json()['data']['changed'][0]['revision'] == 1

    # 基于 revision 1 更新 -> revision 2
    r = send(client, h, op_id(), [{'id': 's1', 'expectedRevision': 1, 'record': subject('s1', '高数')}])
    assert r.status_code == 200, r.text
    assert r.json()['data']['changed'][0]['revision'] == 2

    # 拉取
    records = client.get('/api/v1/sync/records', headers=h).json()['data']['records']
    assert len(records) == 1
    assert records[0]['revision'] == 2
    assert records[0]['record']['name'] == '高数'

    # 过期版本提交 -> 冲突
    r = send(client, h, op_id(), [{'id': 's1', 'expectedRevision': 1, 'record': subject('s1', '冲突')}])
    assert r.status_code == 409
    body = r.json()
    assert body['code'] == 40902
    assert body['data']['conflicts'][0]['revision'] == 2
    assert body['data']['conflicts'][0]['record']['name'] == '高数'


def test_idempotent_replay_and_reused_id(client):
    h = headers(client)
    operation_id = op_id()
    payload = [{'id': 's1', 'expectedRevision': 0, 'record': subject('s1')}]

    first = send(client, h, operation_id, payload)
    assert first.status_code == 200
    rev = first.json()['data']['changed'][0]['revision']

    # 相同 operationId + 相同内容重放 -> 返回首次结果，不新增版本
    replay = send(client, h, operation_id, payload)
    assert replay.status_code == 200
    assert replay.json()['data']['changed'][0]['revision'] == rev

    # 相同 operationId + 不同内容 -> 拒绝
    changed_payload = [{'id': 's1', 'expectedRevision': 0, 'record': subject('s1', '改名')}]
    r = send(client, h, operation_id, changed_payload)
    assert r.status_code == 409
    assert r.json()['code'] == 40903


def test_soft_delete(client):
    h = headers(client)
    send(client, h, op_id(), [{'id': 't1', 'expectedRevision': 0, 'record': task('t1')}])
    r = send(client, h, op_id(), [{'id': 't1', 'expectedRevision': 1, 'record': None}])
    assert r.status_code == 200, r.text
    assert r.json()['data']['changed'][0]['revision'] == 2

    records = client.get('/api/v1/sync/records', headers=h).json()['data']['records']
    row = next(x for x in records if x['id'] == 't1')
    assert row['revision'] == 2
    assert row['record'] is None


def test_type_immutable(client):
    h = headers(client)
    send(client, h, op_id(), [{'id': 's1', 'expectedRevision': 0, 'record': subject('s1')}])
    # 用同 id 改成 task -> 拒绝
    r = send(client, h, op_id(), [{'id': 's1', 'expectedRevision': 1, 'record': task('s1')}])
    assert r.status_code == 400
    assert r.json()['code'] == 40003


def test_invalid_records(client):
    h = headers(client)

    # id 与 record.id 不一致
    r = send(client, h, op_id(), [{'id': 'a', 'expectedRevision': 0, 'record': subject('b')}])
    assert r.status_code == 400 and r.json()['code'] == 40004

    # 非法类型
    bad = {'id': 'x1', 'type': 'nope'}
    r = send(client, h, op_id(), [{'id': 'x1', 'expectedRevision': 0, 'record': bad}])
    assert r.status_code == 400

    # 含保护字段
    protected = subject('s9'); protected['revision'] = 5
    r = send(client, h, op_id(), [{'id': 's9', 'expectedRevision': 0, 'record': protected}])
    assert r.status_code == 400

    # 一次命令内 ID 重复
    r = send(client, h, op_id(), [
        {'id': 's1', 'expectedRevision': 0, 'record': subject('s1')},
        {'id': 's1', 'expectedRevision': 0, 'record': subject('s1')},
    ])
    assert r.status_code == 400


def test_user_isolation(client):
    # 管理员写入 s1
    ah = headers(client)
    send(client, ah, op_id(), [{'id': 's1', 'expectedRevision': 0, 'record': subject('s1')}])

    # 注册一位研友
    admin = login(client, **ADMIN)
    invite = client.post('/api/v1/admin/invites', json={'remark': 'x'},
                         headers={'Authorization': 'Bearer ' + admin['access_token']}).json()['data']['code']
    client.post('/api/v1/auth/email-code', json={'email': 'f@test.com', 'scene': 'register'})
    code = read_latest_code(client.app.state.settings.mail_directory)
    reg = client.post('/api/v1/auth/register', json={
        'email': 'f@test.com', 'code': code, 'password': 'Friend2028',
        'nickname': '研友', 'invite_code': invite, 'accepted_terms': True}).json()['data']
    fh = {'Authorization': 'Bearer ' + reg['access_token']}

    # 研友看不到管理员的记录
    assert client.get('/api/v1/sync/records', headers=fh).json()['data']['records'] == []
    # 研友也能用同 id（不同用户空间互不影响）
    r = send(client, fh, op_id(), [{'id': 's1', 'expectedRevision': 0, 'record': subject('s1', '英语')}])
    assert r.status_code == 200
    assert r.json()['data']['changed'][0]['revision'] == 1
