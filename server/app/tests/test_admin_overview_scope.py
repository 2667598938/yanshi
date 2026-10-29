from datetime import timedelta
from sqlalchemy import select, delete, update
from app.models import Room, RoomMember, RoomPresence, User
from app.tests.test_admin import ADMIN, h, make_member
from app.tests.conftest import login
from app.time import utcnow


def presence(db, room, uid, now, age=0, status='idle'):
    row = db.scalar(select(RoomPresence).where(RoomPresence.room_id == room,
                                              RoomPresence.user_id == uid))
    if row is None:
        row = RoomPresence(room_id=room, user_id=uid)
        db.add(row)
    row.status = status
    row.last_heartbeat_at = now-timedelta(seconds=age)


def test_overview_aggregates_active_rooms_and_deduplicates_online_accounts(client, monkeypatch):
    ah = h(login(client, **ADMIN)['access_token'])
    a = make_member(client, ah, 'overview-a@test.com')['id']
    b = make_member(client, ah, 'overview-b@test.com')['id']
    now = utcnow()
    monkeypatch.setattr('app.routers.admin.utcnow', lambda: now)
    with client.app.state.session_factory() as db:
        first = db.scalar(select(Room).order_by(Room.id)).id
        second = Room(code='OVROOM2', name='第二间有效房间', capacity=4)
        dissolved = Room(code='OVROOM3', name='已解散房间', capacity=4, dissolved_at=now)
        db.add_all([second, dissolved]);db.flush()
        db.add_all([RoomMember(room_id=second.id, user_id=a),
                    RoomMember(room_id=second.id, user_id=b),
                    RoomMember(room_id=dissolved.id, user_id=1)])
        db.execute(update(RoomPresence).values(status='offline'))
        presence(db, first, 1, now, age=91)
        presence(db, first, a, now, age=60)
        presence(db, second.id, a, now, age=60)
        presence(db, second.id, b, now, age=90)
        presence(db, dissolved.id, 1, now)
        # An old presence row without room membership is not a current occupant.
        presence(db, second.id, 1, now)
        db.commit()
    result = client.get('/api/v1/admin/overview', headers=ah).json()['data']
    assert result['room_member_count'] == 5  # 3 in first + 2 in second; dissolved excluded.
    assert result['online_count'] == 2  # a is present in two rooms, counted once.
    assert 'room_capacity' not in result


def test_overview_online_respects_group_privacy_and_account_status(client):
    ah = h(login(client, **ADMIN)['access_token'])
    hidden = make_member(client, ah, 'overview-hidden@test.com')['id']
    visible = make_member(client, ah, 'overview-visible@test.com')['id']
    now = utcnow()
    with client.app.state.session_factory() as db:
        room = db.scalar(select(Room).order_by(Room.id))
        outsider = User(email='overview-outsider@test.com', nickname='未受邀账号', password_hash='unused-fixture')
        db.add(outsider);db.flush()
        db.add(RoomMember(room_id=room.id, user_id=outsider.id))
        db.get(User, hidden).is_private_mode = True
        db.execute(update(RoomPresence).values(status='offline'))
        for uid in [hidden, visible, outsider.id]:
            presence(db, room.id, uid, now)
        db.commit()
    result = client.get('/api/v1/admin/overview', headers=ah).json()['data']
    assert result['online_count'] == 1
    with client.app.state.session_factory() as db:
        db.get(User, visible).status = 'banned'
        db.commit()
    assert client.get('/api/v1/admin/overview', headers=ah).json()['data']['online_count'] == 0


def test_overview_dissolved_rooms_keep_memberships_but_not_occupancy(client):
    ah = h(login(client, **ADMIN)['access_token'])
    with client.app.state.session_factory() as db:
        room = db.scalar(select(Room).order_by(Room.id))
        presence(db, room.id, 1, utcnow())
        room.dissolved_at = utcnow()
        db.commit()
        assert db.scalar(select(RoomMember.id).limit(1)) is not None
    result = client.get('/api/v1/admin/overview', headers=ah).json()['data']
    assert result['room_member_count'] == 0 and result['online_count'] == 0
