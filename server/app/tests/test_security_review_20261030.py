import asyncio
import io
import json
import jwt
import pytest
from PIL import Image
from sqlalchemy import delete
from app.models import RoomMember,User,Attachment
from app.routers import room_media
from app.tests.conftest import login

ADMIN={'email':'admin@test.com','password':'Admin2028'}
def headers(token):return {'Authorization':'Bearer '+token}

def test_logout_invalidates_current_and_rotated_access_without_logging_out_other_session(client):
    original=login(client,**ADMIN)['access_token']
    rotated=client.post('/api/v1/auth/refresh').json()['data']['access_token']
    refresh=client.cookies.get('yanshi_refresh')
    independent=login(client,**ADMIN)['access_token']
    assert client.post('/api/v1/auth/logout',json={'refresh_token':refresh},headers=headers(rotated)).status_code==200
    assert client.get('/api/v1/auth/me',headers=headers(original)).status_code==401
    assert client.get('/api/v1/auth/me',headers=headers(rotated)).status_code==401
    assert client.get('/api/v1/auth/me',headers=headers(independent)).status_code==200

def test_repeated_upload_delete_cannot_bypass_physical_disk_quota(client):
    auth=headers(login(client,**ADMIN)['access_token'])
    picture=io.BytesIO();Image.new('RGB',(40,40),'green').save(picture,format='JPEG')
    def upload():return client.post('/api/v1/attachments/image',headers=auth,files={'file':('test.jpg',picture.getvalue(),'image/jpeg')})
    response=upload();assert response.status_code==200
    size=response.json()['data']['size'];client.app.state.settings.storage_quota_bytes=size+8
    for index in range(3):
        if index:response=upload()
        if response.status_code==200:
            key=response.json()['data']['key']
            assert client.delete('/api/v1/attachments',params={'key':key},headers=auth).status_code==200
        else:assert response.status_code==403
    physical=sum(path.stat().st_size for path in client.app.state.settings.image_directory.rglob('*.jpg'))
    assert physical<=client.app.state.settings.storage_quota_bytes

@pytest.mark.parametrize('reason',['membership','logout','ban'])
def test_silent_media_peer_loses_access_after_revocation(client,monkeypatch,reason):
    session=login(client,**ADMIN);client.app.state.settings.features+=',av_room'
    with client.app.state.session_factory() as db:
        db.get(User,session['user']['id']).vip_permanent=True;db.commit()
    response=client.post('/api/v1/rooms',headers=headers(session['access_token']),json={'name':'撤权验收房','room_type':'av_room','accept_sharing':True})
    assert response.status_code==200,response.text
    rid=response.json()['data']['id']
    monkeypatch.setattr(room_media,'RECHECK_INTERVAL',.05,raising=False)
    async def check():
        class Socket:
            app=client.app
            headers={'origin':client.app.state.settings.public_origin}
            def __init__(self):self.welcome=asyncio.Event();self.silence=asyncio.Event();self.first=True;self.closed=[]
            async def accept(self):pass
            async def receive_text(self):
                if self.first:self.first=False;return json.dumps({'token':session['access_token']})
                await self.silence.wait()
            async def send_json(self,payload):
                if payload['type']=='welcome':self.welcome.set()
            async def close(self,code):self.closed.append(code)
        socket=Socket();task=asyncio.create_task(room_media.signaling(socket,rid))
        try:
            await asyncio.wait_for(socket.welcome.wait(),1)
            if reason=='logout':assert client.post('/api/v1/auth/logout').status_code==200
            else:
                with client.app.state.session_factory() as db:
                    if reason=='membership':db.execute(delete(RoomMember).where(RoomMember.room_id==rid,RoomMember.user_id==session['user']['id']))
                    else:db.get(User,session['user']['id']).status='banned'
                    db.commit()
            await asyncio.wait_for(task,1)
            assert 4403 in socket.closed
        finally:
            task.cancel()
            try:await task
            except asyncio.CancelledError:pass
    asyncio.run(check())

def test_bearer_only_logout_also_blocks_refresh_for_that_login(client):
    session=login(client,**ADMIN);refresh=client.cookies.get('yanshi_refresh');client.cookies.clear()
    assert client.post('/api/v1/auth/logout',headers=headers(session['access_token'])).status_code==200
    assert client.get('/api/v1/auth/me',headers=headers(session['access_token'])).status_code==401
    assert client.post('/api/v1/auth/refresh',json={'refresh_token':refresh}).status_code==401

def test_legacy_refresh_upgrades_without_requiring_a_new_password(client):
    session=login(client,**ADMIN);secret=client.app.state.secret;settings=client.app.state.settings
    def legacy(token):
        claims=jwt.decode(token,secret,audience=settings.jwt_audience,issuer=settings.jwt_issuer,algorithms=['HS256']);claims.pop('sid')
        return jwt.encode(claims,secret,algorithm='HS256')
    old_refresh=legacy(client.cookies.get('yanshi_refresh'))
    assert client.get('/api/v1/auth/me',headers=headers(legacy(session['access_token']))).status_code==401
    response=client.post('/api/v1/auth/refresh',json={'refresh_token':old_refresh});assert response.status_code==200
    assert client.get('/api/v1/auth/me',headers=headers(response.json()['data']['access_token'])).status_code==200

@pytest.mark.parametrize('failure',['partial_write','disk_reserve'])
def test_failed_local_image_write_does_not_leave_uncharged_files(client,monkeypatch,failure):
    from app.services import image_storage
    auth=headers(login(client,**ADMIN)['access_token'])
    if failure=='partial_write':
        def fail(source,destination,*args):destination.write(b'partial');raise OSError('disk full')
        monkeypatch.setattr(image_storage.shutil,'copyfileobj',fail)
    else:
        from collections import namedtuple
        monkeypatch.setattr(image_storage.shutil,'disk_usage',lambda path:namedtuple('Usage','total used free')(10,10,0))
    picture=io.BytesIO();Image.new('RGB',(40,40),'green').save(picture,format='JPEG')
    response=client.post('/api/v1/attachments/image',headers=auth,files={'file':('test.jpg',picture.getvalue(),'image/jpeg')})
    assert response.status_code==507
    assert not list(client.app.state.settings.image_directory.rglob('*.jpg'))
    with client.app.state.session_factory() as db:assert db.query(Attachment).count()==0

def test_old_avatar_purge_releases_physical_space_and_keeps_current_avatar(client):
    from app.services.attachments import purge_deleted_attachments
    from app.services.image_storage import ImageStorage
    auth=headers(login(client,**ADMIN)['access_token'])
    picture=io.BytesIO();Image.new('RGB',(40,40),'green').save(picture,format='JPEG')
    def upload():return client.post('/api/v1/attachments/avatar',headers=auth,files={'file':('test.jpg',picture.getvalue(),'image/jpeg')}).json()['data']['key']
    old=upload();current=upload();storage=ImageStorage(client.app.state.settings)
    assert storage.path(old).is_file()
    assert purge_deleted_attachments(client.app.state.session_factory,client.app.state.settings)==1
    assert not storage.path(old).exists() and storage.path(current).is_file()
