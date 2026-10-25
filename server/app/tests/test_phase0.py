"""第 0 期：权限、计时与励志附件的真实 API 回归。"""
import uuid

import pytest
from sqlalchemy import func, select

from app.models import RoomGoal, RoomMember, RoomMessage, RoomPresence
from app.tests.conftest import login
from app.tests.test_attachment import upload
from app.tests.test_rooms import make_member
from app.tests.test_sync import send, session


def auth(client, email='admin@test.com', password='Admin2028'):
    return {'Authorization': 'Bearer ' + login(client, email, password)['access_token']}


@pytest.mark.parametrize('visibility', ['private', 'public'])
def test_room_writes_require_current_membership(client, visibility):
    owner = auth(client)
    member = make_member(client, owner, 'outsider@test.com', '未加入同学')
    outsider = auth(client, 'outsider@test.com', 'Friend2028')
    room = client.post('/api/v1/rooms', headers=owner,
                       json={'name': '权限回归房', 'visibility': visibility}).json()['data']
    rid = room['id']

    def write_all(expected):
        assert client.post(f'/api/v1/rooms/{rid}/heartbeat', headers=outsider,
                           json={'status': 'online'}).status_code == expected
        assert client.post(f'/api/v1/rooms/{rid}/messages', headers=outsider,
                           json={'content': '无权留言'}).status_code == expected
        assert client.put(f'/api/v1/rooms/{rid}/goal', headers=outsider,
                          json={'words': '目标'}).status_code == expected

    write_all(403)
    with client.app.state.session_factory() as db:
        for model in (RoomMember, RoomPresence, RoomMessage, RoomGoal):
            assert db.scalar(select(func.count()).select_from(model).where(
                model.room_id == rid, model.user_id == member['id'])) == 0
    # 只有显式加入授予成员身份；被移除后心跳不能自动重新加入。
    assert client.post(f'/api/v1/rooms/{rid}/join', headers=outsider,
                       json={'code': room['code']}).status_code == 200
    write_all(200)
    assert client.delete(f'/api/v1/rooms/{rid}/members/{member["id"]}', headers=owner).status_code == 200
    write_all(403)


def test_default_room_writes_cannot_rejoin_after_leaving(client):
    owner = auth(client)
    make_member(client, owner, 'leave@test.com', '退出同学')
    member = auth(client, 'leave@test.com', 'Friend2028')
    rid = client.get('/api/v1/room', headers=member).json()['data']['room']['id']
    assert client.post(f'/api/v1/rooms/{rid}/leave', headers=member).status_code == 200
    assert client.post('/api/v1/room/heartbeat', headers=member, json={'status': 'online'}).status_code == 403
    assert client.post('/api/v1/room/messages', headers=member, json={'content': 'x'}).status_code == 403
    assert client.put('/api/v1/room/goal', headers=member, json={'words': 'x'}).status_code == 403


@pytest.mark.parametrize('patch, expected', [
    ({'pauseAccum': 10 * 60000}, (1500, 'done', 'completed')),
    ({'pauseAccum': 35 * 60000, 'maxPauseMs': 25 * 60000,
      'endedAt': 1700000000000 + 60 * 60000}, (1500, 'done', 'completed')),
    ({'maxPauseMs': 30 * 60000, 'end_reason': 'completed'}, (2100, 'quit', 'pause_timeout')),
    ({'end_reason': 'abandoned'}, (2100, 'quit', 'abandoned')),
    ({'endedAt': 1700000000000 + 181 * 60000, 'end_reason': 'completed'}, (10800, 'quit', 'timeout')),
    ({'mode': 'timer', 'plannedMin': 25, 'endedAt': 1700000000000 + 180 * 60000},
     (1500, 'done', 'completed')),
])
def test_session_pause_contract(client, patch, expected):
    headers = auth(client)
    record = session('contract', 1700000000000, 1700000000000 + 35 * 60000)
    record.update(patch)
    result = send(client, headers, uuid.uuid4().hex, [
        {'id': record['id'], 'expectedRevision': 0, 'record': record}])
    assert result.status_code == 200, result.text
    saved = result.json()['data']['changed'][0]['record']
    assert (saved['actualSec'], saved['status'], saved['end_reason']) == expected
    pulled = client.get('/api/v1/sync/records', headers=headers).json()['data']['records'][0]['record']
    assert pulled == saved


def test_legacy_session_without_pause_detail_keeps_effective_duration(client):
    headers = auth(client)
    record = session('legacy', 1700000000000, 1700000000000 + 35 * 60000)
    record.pop('pauseAccum')
    record['actualSec'] = 1500
    result = send(client, headers, uuid.uuid4().hex, [
        {'id': 'legacy', 'expectedRevision': 0, 'record': record}])
    assert result.json()['data']['changed'][0]['record']['actualSec'] == 1500


@pytest.mark.parametrize('action', ['approve', 'reject'])
def test_inspiration_image_upload_submit_review_and_visibility(client, action):
    admin = auth(client)
    make_member(client, admin, 'author@test.com', '投稿同学')
    make_member(client, admin, 'viewer@test.com', '读者同学')
    author = auth(client, 'author@test.com', 'Friend2028')
    viewer = auth(client, 'viewer@test.com', 'Friend2028')
    uploaded = upload(client, '/api/v1/attachments/image', author, 'inspiration')
    assert uploaded.status_code == 200, uploaded.text
    image = uploaded.json()['data']
    assert image['biz_type'] == 'inspiration'
    key = image['key']
    assert key.startswith('inspiration/')
    assert client.get('/api/v1/attachments/view', params={'key': key}, headers=author).status_code == 200
    assert client.get('/api/v1/attachments/view', params={'key': key}, headers=viewer).status_code == 404
    # 其他账号不能把这张图挂到自己的投稿。
    assert client.post('/api/v1/inspirations', headers=viewer,
                       json={'content': '盗用', 'image_key': key}).status_code == 400
    submitted = client.post('/api/v1/inspirations', headers=author,
                            json={'content': '静候春来', 'image_key': key})
    assert submitted.status_code == 200, submitted.text
    iid = submitted.json()['data']['id']
    assert client.post(f'/api/v1/admin/inspirations/{iid}/review', headers=admin,
                       json={'action': action, 'note': '回归验收备注'}).status_code == 200
    expected = 200 if action == 'approve' else 404
    assert client.get('/api/v1/attachments/view', params={'key': key}, headers=viewer).status_code == expected
    assert client.delete('/api/v1/attachments', params={'key': key}, headers=author).status_code == 200
    assert client.get('/api/v1/attachments/view', params={'key': key}, headers=viewer).status_code == 404


def test_inspiration_rejects_invalid_biz_and_wrong_attachment_kind(client):
    admin = auth(client)
    assert upload(client, '/api/v1/attachments/image', admin, 'invalid').status_code == 400
    key = upload(client, '/api/v1/attachments/image', admin, 'mistake').json()['data']['key']
    assert client.post('/api/v1/inspirations', headers=admin,
                       json={'content': '不能公开错题图', 'image_key': key}).status_code == 400
