from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select

from app.models import Room, User
from app.tests.test_rooms import make_member, h, ADMIN
from app.tests.conftest import login


def test_two_users_race_for_last_seat_only_one_joins(client):
    owner = h(login(client, **ADMIN)['access_token'])
    make_member(client, owner, 'seat-a@test.com', '座位甲')
    make_member(client, owner, 'seat-b@test.com', '座位乙')
    users = [h(login(client, email, 'Friend2028')['access_token']) for email in ['seat-a@test.com', 'seat-b@test.com']]
    room = client.post('/api/v1/rooms', headers=owner, json={'name': '并发座位'}).json()['data']
    with client.app.state.session_factory() as db:
        db.get(Room, room['id']).capacity = 2
        db.commit()
    def join(headers):
        return client.post(f'/api/v1/rooms/{room["id"]}/join', headers=headers, json={'code': ''}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(join, users))
    assert sorted(results) == [200, 403]
    state = client.get(f'/api/v1/rooms/{room["id"]}', headers=owner).json()['data']
    assert len(state['members']) == 2


def test_resting_and_idle_presence_and_private_online_flag(client):
    owner = h(login(client, **ADMIN)['access_token'])
    make_member(client, owner, 'rest@test.com', '休息同学')
    guest = h(login(client, 'rest@test.com', 'Friend2028')['access_token'])
    for status in ['resting', 'idle']:
        assert client.post('/api/v1/room/heartbeat', headers=guest, json={'status': status}).status_code == 200
        state = client.get('/api/v1/room', headers=owner).json()['data']
        assert any(member['presence']['status'] == status for member in state['members'])
    with client.app.state.session_factory() as db:
        db.scalar(select(User).where(User.email == 'rest@test.com')).privacy_mode = True
        db.commit()
    state = client.get('/api/v1/room', headers=owner).json()['data']
    hidden = next(member for member in state['members'] if member['nickname'] == '休息同学')
    assert hidden['online'] is False and hidden['presence']['status'] == 'private'
    assert state['room']['online_count'] == 0
    mine = client.get('/api/v1/room', headers=guest).json()['data']
    assert any(member['nickname'] == '休息同学' and member['online'] for member in mine['members'])
