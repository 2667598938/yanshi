"""四人自习室（v0.3-c）端到端测试。"""
import time
import uuid
from datetime import datetime, timedelta, timezone

from app.tests.conftest import login, read_latest_code

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}
CN = timezone(timedelta(hours=8))


def auth_header(token):
    return {'Authorization': 'Bearer ' + token}


def register_friend(client, admin_headers, email, name, password='Friend2028'):
    invite = client.post('/api/v1/admin/invites', json={'remark': 'x'},
                         headers=admin_headers).json()['data']['code']
    client.post('/api/v1/auth/email-code', json={'email': email, 'scene': 'register'})
    code = read_latest_code(client.app.state.settings.mail_directory)
    r = client.post('/api/v1/auth/register', json={
        'email': email, 'code': code, 'password': password,
        'nickname': name, 'invite_code': invite, 'accepted_terms': True})
    assert r.status_code == 200, r.text
    return auth_header(r.json()['data']['access_token'])


def today():
    return datetime.now(CN).date().isoformat()


def session_record(rid, sec, day=None):
    now_ms = int(time.time() * 1000)
    return {'id': rid, 'type': 'session', 'subjectId': 'math', 'mode': 'timer',
            'activityType': 'practice', 'plannedMin': 25, 'actualSec': sec, 'status': 'done',
            'startedAt': now_ms - sec * 1000, 'endedAt': now_ms,
            'date': day or today(), 'note': '', 'createdAt': now_ms}


def test_privacy_mode_anonymizes_and_excludes_ranking(client):
    """隐私模式：他人视角匿名占位、隐藏时长，排行榜排除；本人仍可见自己。"""
    admin = login(client, **ADMIN)
    ah = auth_header(admin['access_token'])
    fh = register_friend(client, ah, 'privacy@test.com', '隐私同学')

    client.post('/api/v1/room/heartbeat', headers=fh, json={
        'status': 'focusing', 'subject_client_id': 'math', 'subject_name': '数学',
        'activity_type': 'practice', 'mode': 'timer',
        'focus_started_at': int(time.time() * 1000) - 120_000})
    state = client.get('/api/v1/room', headers=ah).json()['data']
    friend_id = find_member(state, '隐私同学')['user_id']

    r = client.put('/api/v1/users/me', headers=fh, json={'privacy_mode': True})
    assert r.status_code == 200, r.text
    assert r.json()['data']['privacy_mode'] is True

    other = client.get('/api/v1/room', headers=ah).json()['data']
    hidden = next(m for m in other['members'] if m['user_id'] == friend_id)
    assert hidden['nickname'] == '隐私同学'
    assert hidden['avatar_key'] == ''
    assert hidden['privacy'] is True
    assert hidden['online'] is False         # 他人不获知个人在线状态
    assert other['room']['online_count'] == 0  # 不通过聚合泄露隐私用户在线与否
    assert hidden['presence'] == {'status':'private'}
    assert 'today_sec' not in hidden and 'total_sec' not in hidden

    ranking = client.get('/api/v1/room/ranking', headers=ah).json()['data']
    assert all(x['user_id'] != friend_id for x in ranking['items'])

    # 本人仍看到自己的真实信息
    mine = client.get('/api/v1/room', headers=fh).json()['data']
    self_row = next(m for m in mine['members'] if m['user_id'] == friend_id)
    assert self_row['nickname'] == '隐私同学'
    assert self_row['privacy'] is True


def find_member(state, nickname):
    return next(m for m in state['members'] if m['nickname'] == nickname)


def test_room_state_heartbeat_and_stats(client):
    admin = login(client, **ADMIN)
    ah = auth_header(admin['access_token'])
    fh = register_friend(client, ah, 'f1@test.com', '研友一号')

    # 固定房间：管理员（房主）+ 研友一号 = 2 人
    state = client.get('/api/v1/room', headers=ah).json()['data']
    assert state['room']['member_count'] == 2
    owner = find_member(state, '管理员')
    assert owner['role'] == 'owner'

    # 研友一心跳：正在专注数学，已进行约 300 秒
    started = int(time.time() * 1000) - 300_000
    r = client.post('/api/v1/room/heartbeat', headers=fh, json={
        'status': 'focusing', 'subject_client_id': 'math', 'subject_name': '数学',
        'activity_type': 'practice', 'mode': 'timer', 'focus_started_at': started})
    assert r.status_code == 200, r.text
    state = client.get('/api/v1/room', headers=ah).json()['data']
    me = find_member(state, '研友一号')
    assert me['online'] is True
    assert me['presence']['status'] == 'focusing'
    assert me['presence']['subject_name'] == '数学'
    assert 295 <= me['presence']['focus_sec'] <= 305
    assert state['room']['online_count'] == 1

    # 通过同步写一条今天的学习记录 1500 秒，房间聚合应反映
    op = uuid.uuid4().hex
    r = client.post('/api/v1/sync/commands', headers=fh, json={
        'operationId': op, 'changes': [
            {'id': 'sess1', 'expectedRevision': 0, 'record': session_record('sess1', 1500)}]})
    assert r.status_code == 200, r.text
    state = client.get('/api/v1/room', headers=ah).json()['data']
    me = find_member(state, '研友一号')
    assert me['today_sec'] == 1500
    assert me['week_sec'] == 1500
    assert me['total_sec'] == 1500
    assert me['streak'] == 1
    assert state['ranking']['today'][0]['user_id'] == me['user_id']


def test_room_messages_and_goal(client):
    admin = login(client, **ADMIN)
    ah = auth_header(admin['access_token'])
    fh = register_friend(client, ah, 'g1@test.com', '留言同学')

    # 发留言
    r = client.post('/api/v1/room/messages', headers=fh, json={'content': '一起上岸，大雪深埋'})
    assert r.status_code == 200, r.text
    msg_id = r.json()['data']['id']
    assert r.json()['data']['mine'] is True

    # 房间里能看到，管理员视角 mine=False
    state = client.get('/api/v1/room', headers=ah).json()['data']
    assert any(m['id'] == msg_id and m['mine'] is False for m in state['messages'])
    state = client.get('/api/v1/room', headers=fh).json()['data']
    assert any(m['id'] == msg_id and m['mine'] is True for m in state['messages'])

    # 目标墙
    r = client.put('/api/v1/room/goal', headers=fh, json={
        'target_school': '复旦大学', 'target_score': '450', 'words': '明年复旦见'})
    assert r.status_code == 200, r.text
    state = client.get('/api/v1/room', headers=ah).json()['data']
    me = find_member(state, '留言同学')
    assert me['goal']['target_school'] == '复旦大学'
    assert me['goal']['target_score'] == '450'

    # 删除留言
    assert client.delete(f'/api/v1/room/messages/{msg_id}', headers=fh).status_code == 200
    state = client.get('/api/v1/room', headers=ah).json()['data']
    assert all(m['id'] != msg_id for m in state['messages'])

    # 不能删别人的留言
    other = client.post('/api/v1/room/messages', headers=ah, json={'content': '管理员留言'})
    other_id = other.json()['data']['id']
    assert client.delete(f'/api/v1/room/messages/{other_id}', headers=fh).status_code == 403


def test_room_capacity_four(client):
    client.app.state.settings.account_max_users = 4  # 显式四人内测账号上限，与房间席位分别校验。
    admin = login(client, **ADMIN)
    ah = auth_header(admin['access_token'])
    # 已有管理员 1 人，再注册 1 人 + 管理员建 2 人 = 4 人
    register_friend(client, ah, 'c1@test.com', '成员一')
    for i in range(2):
        r = client.post('/api/v1/admin/members', headers=ah, json={
            'email': f'c{i + 2}@test.com', 'nickname': f'成员{i + 2}', 'password': 'Member2028'})
        assert r.status_code == 200, r.text
    state = client.get('/api/v1/room', headers=ah).json()['data']
    assert state['room']['member_count'] == 4
    # 第 5 人不允许
    r = client.post('/api/v1/admin/members', headers=ah, json={
        'email': 'c5@test.com', 'nickname': '第五人', 'password': 'Member2028'})
    assert r.status_code == 403


def _admin_create_member(client, ah, email, name):
    r = client.post('/api/v1/admin/members', headers=ah,
                    json={'email': email, 'nickname': name, 'password': 'Member2028'})
    assert r.status_code == 200, r.text
    uid = r.json()['data']['id']
    return uid, auth_header(login(client, email, 'Member2028')['access_token'])


def test_offline_after_heartbeat_window(client):
    """心跳后超过 90 秒未续约即判离线：把 last_heartbeat_at 回拨 120 秒验证。"""
    from datetime import timedelta
    from sqlalchemy import select
    from app.models import RoomPresence
    from app.time import utcnow

    admin = login(client, **ADMIN)
    ah = auth_header(admin['access_token'])
    uid, fh = _admin_create_member(client, ah, 'hb@test.com', '心跳同学')

    started = int(time.time() * 1000) - 120_000
    r = client.post('/api/v1/room/heartbeat', headers=fh, json={
        'status': 'focusing', 'subject_client_id': 'math', 'subject_name': '数学',
        'activity_type': 'practice', 'mode': 'timer', 'focus_started_at': started})
    assert r.status_code == 200, r.text
    # 刚心跳：在线
    state = client.get('/api/v1/room', headers=ah).json()['data']
    me = find_member(state, '心跳同学')
    assert me['online'] is True

    # 把心跳时间回拨 120 秒（>90 秒窗口），模拟离线
    with client.app.state.session_factory() as db:
        p = db.scalar(select(RoomPresence).where(RoomPresence.user_id == uid))
        p.last_heartbeat_at = utcnow() - timedelta(seconds=120)
        db.commit()
    state = client.get('/api/v1/room', headers=ah).json()['data']
    me = find_member(state, '心跳同学')
    assert me['online'] is False
    assert me['presence']['status'] == 'offline'
    assert state['room']['online_count'] == 0


def test_ranking_today_week_all_aggregation(client):
    """今日 / 本周 / 累计三种聚合口径：今天 100s + 30 天前 200s。"""
    admin = login(client, **ADMIN)
    ah = auth_header(admin['access_token'])
    _, fh = _admin_create_member(client, ah, 'rk@test.com', '排行同学')

    today_str = today()
    old_str = (datetime.now(CN).date() - timedelta(days=30)).isoformat()
    now_ms = int(time.time() * 1000)
    changes = [
        {'id': 's_today', 'expectedRevision': 0,
         'record': session_record('s_today', 100, day=today_str)},
        {'id': 's_old', 'expectedRevision': 0,
         'record': session_record('s_old', 200, day=old_str)},
    ]
    r = client.post('/api/v1/sync/commands', headers=fh,
                    json={'operationId': uuid.uuid4().hex, 'changes': changes})
    assert r.status_code == 200, r.text

    state = client.get('/api/v1/room', headers=ah).json()['data']
    me = find_member(state, '排行同学')
    assert me['today_sec'] == 100, me          # 只有今天那条
    assert me['week_sec'] == 100, me           # 30 天前不计入本周
    assert me['total_sec'] == 300, me          # 累计两条都算

    # 独立排行榜接口三种 range
    wk = client.get('/api/v1/room/ranking', headers=ah, params={'range': 'week'}).json()['data']
    al = client.get('/api/v1/room/ranking', headers=ah, params={'range': 'all'}).json()['data']
    assert wk['range'] == 'week' and al['range'] == 'all'
    my_week = next(x for x in wk['items'] if x['user_id'] == me['user_id'])
    my_all = next(x for x in al['items'] if x['user_id'] == me['user_id'])
    assert my_week['sec'] == 100
    assert my_all['sec'] == 300


def test_message_validation(client):
    """留言：空 / 纯空白 / 超长 500 字均被拒（400 / 40001），500 字以内通过。"""
    admin = login(client, **ADMIN)
    ah = auth_header(admin['access_token'])
    fh = register_friend(client, ah, 'mv@test.com', '留言校验')

    r = client.post('/api/v1/room/messages', headers=fh, json={'content': ''})
    assert r.status_code == 400 and r.json()['code'] == 40001, r.text
    r = client.post('/api/v1/room/messages', headers=fh, json={'content': '   '})
    assert r.status_code == 400 and r.json()['code'] == 40001, r.text
    r = client.post('/api/v1/room/messages', headers=fh, json={'content': '字' * 501})
    assert r.status_code == 400 and r.json()['code'] == 40001, r.text

    r = client.post('/api/v1/room/messages', headers=fh, json={'content': '字' * 500})
    assert r.status_code == 200, r.text
