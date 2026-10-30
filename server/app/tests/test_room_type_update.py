"""Existing rooms can change type without losing membership or room history."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from sqlalchemy import select
from app.models import Room, RoomMember, User
from app.tests.conftest import login
from app.tests.test_rooms import ADMIN, h, make_member


def setup_room(client, *, vip=True, members=1):
    session=login(client,**ADMIN)
    client.app.state.settings.features+=',av_room'
    with client.app.state.session_factory() as db:
        owner=db.get(User,session['user']['id']);owner.vip_permanent=vip;db.commit()
    auth=h(session['access_token'])
    room=client.post('/api/v1/rooms',headers=auth,json={'name':'原有自习室','visibility':'private','capacity':50,'accept_sharing':True}).json()['data']
    with client.app.state.session_factory() as db:
        for index in range(members-1):
            user=User(email=f'type-test-{index}@example.invalid',nickname=f'原有成员{index}',password_hash='not-a-login',vip_permanent=True)
            db.add(user);db.flush()
            db.add(RoomMember(room_id=room['id'],user_id=user.id,sharing_confirmed=True))
        db.commit()
    return room,auth


def test_owner_changes_both_directions_preserving_private_members_and_messages(client):
    room,auth=setup_room(client,members=2);url=f"/api/v1/rooms/{room['id']}"
    assert client.post(url+'/messages',headers=auth,json={'content':'原来的留言'}).status_code==200
    response=client.patch(url,headers=auth,json={'room_type':'av_room'})
    assert response.status_code==200,response.text
    video=response.json()['data']
    assert (video['room_type'],video['capacity'],video['media_mode'])==('av_room',6,'mesh')
    assert video['id']==room['id'] and video['code']==room['code'] and video['visibility']=='private'
    assert video['member_count']==2 and video['my_role']=='owner'
    assert client.patch(url,headers=auth,json={'name':'只修改名字'}).json()['data']['room_type']=='av_room'
    response=client.patch(url,headers=auth,json={'room_type':'text_room','capacity':20})
    assert response.status_code==200,response.text
    text=response.json()['data']
    assert (text['room_type'],text['capacity'],text['media_mode'])==('text_room',20,'')
    state=client.get(url,headers=auth).json()['data']
    assert len(state['members'])==2 and state['messages'][0]['content']=='原来的留言'
    assert state['room']['code']==room['code']


@pytest.mark.parametrize('reason',['no_vip','disabled','too_many'])
def test_conversion_failure_keeps_original_room_and_members(client,reason):
    room,auth=setup_room(client,vip=reason!='no_vip',members=7 if reason=='too_many' else 1)
    if reason=='disabled':client.app.state.settings.features='text_room'
    response=client.patch(f"/api/v1/rooms/{room['id']}",headers=auth,json={'room_type':'av_room','name':'不应保存的新名字'})
    assert response.status_code==(409 if reason=='too_many' else 403),response.text
    if reason=='too_many':assert '7位成员' in response.json()['message']
    current=client.get(f"/api/v1/rooms/{room['id']}",headers=auth).json()['data']['room']
    assert current['name']==room['name'] and current['room_type']=='text_room' and current['capacity']==50
    assert current['member_count']==(7 if reason=='too_many' else 1)


@pytest.mark.parametrize('body,status',[
    ({'room_type':'av_room','capacity':20},400),
    ({'room_type':'text_room','capacity':6},400),
    ({'room_type':'av_room','media_mode':'sfu'},403),
    ({'room_type':'video_room'},400),
])
def test_type_update_enforces_creation_rules(client,body,status):
    room,auth=setup_room(client)
    response=client.patch(f"/api/v1/rooms/{room['id']}",headers=auth,json=body)
    assert response.status_code==status,response.text


def test_nonowner_cannot_change_type_or_capacity(client):
    room,auth=setup_room(client)
    make_member(client,auth,'not-owner@test.com','普通成员')
    other=h(login(client,'not-owner@test.com','Friend2028')['access_token'])
    url=f"/api/v1/rooms/{room['id']}"
    assert client.patch(url,headers=other,json={'room_type':'av_room'}).status_code==403
    assert client.patch(url,headers=other,json={'capacity':100}).status_code==403
    assert client.patch(url,json={'room_type':'av_room'}).status_code==401


def test_join_racing_type_change_never_overfills_room(client):
    room,auth=setup_room(client,members=6)
    uid=make_member(client,auth,'last-seat@test.com','最后一席')['id']
    with client.app.state.session_factory() as db:db.get(User,uid).vip_permanent=True;db.commit()
    other=h(login(client,'last-seat@test.com','Friend2028')['access_token'])
    url=f"/api/v1/rooms/{room['id']}";ready=Barrier(2)
    def convert():ready.wait();return client.patch(url,headers=auth,json={'room_type':'av_room'}).status_code
    def join():ready.wait();return client.post(url+'/join',headers=other,json={'code':room['code'],'accept_sharing':True}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        change=pool.submit(convert);addition=pool.submit(join);statuses=(change.result(),addition.result())
    assert statuses in ((200,403),(409,200)),statuses
    with client.app.state.session_factory() as db:
        current=db.get(Room,room['id'])
        count=len(db.scalars(select(RoomMember.id).where(RoomMember.room_id==room['id'])).all())
        assert count<=current.capacity
