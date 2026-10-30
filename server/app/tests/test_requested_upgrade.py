import io
import asyncio
import httpx
import pytest
from PIL import Image
from sqlalchemy import func,select
from app.models import User,UserAuth,Room
from app.routers import oauth
from app.tests.conftest import login
from app.tests.test_rooms import make_member,h,ADMIN
from app.errors import ApiError

def test_primary_admin_payload_marks_backend_only(client):
    session=login(client,**ADMIN)
    assert session['user']['is_super_admin'] is True
    assert client.get('/api/v1/auth/me',headers=h(session['access_token'])).json()['data']['is_super_admin'] is True

def test_production_local_images_remain_authenticated_and_readable(client,tmp_path):
    headers=h(login(client,**ADMIN)['access_token'])
    settings=client.app.state.settings
    settings.environment='production';settings.image_storage='local';settings.image_directory=tmp_path/'persistent-images'
    photo=io.BytesIO();Image.new('RGB',(40,40),'green').save(photo,format='JPEG')
    result=client.post('/api/v1/attachments/image',headers=headers,files={'file':('photo.jpg',photo.getvalue(),'image/jpeg')})
    assert result.status_code==200,result.text
    key=result.json()['data']['key']
    assert client.get('/api/v1/attachments/view',params={'key':key}).status_code==401
    view=client.get('/api/v1/attachments/view',headers=headers,params={'key':key})
    assert view.status_code==200 and view.headers['cache-control']=='private, no-store'
    assert list(settings.image_directory.rglob('*.jpg'))

def test_room_capacity_types_and_private_listing(client):
    headers=h(login(client,**ADMIN)['access_token'])
    for capacity in (20,50,100):
        response=client.post('/api/v1/rooms',headers=headers,json={'accept_sharing':True,'name':f'文字房{capacity}','capacity':capacity})
        assert response.status_code==200,response.text
        assert response.json()['data']['capacity']==capacity
        assert response.json()['data']['room_type']=='text_room'
    assert client.post('/api/v1/rooms',headers=headers,json={'accept_sharing':True,'name':'旧四人房','capacity':4}).status_code==400
    private=client.post('/api/v1/rooms',headers=headers,json={'accept_sharing':True,'name':'私密文字房','visibility':'private'}).json()['data']
    assert private['visibility']=='private'  # The public UI filters private rooms; the authenticated owner may retrieve their own invitation.
    client.app.state.settings.features+=',av_room'
    with client.app.state.session_factory() as db: db.scalar(select(User).where(User.email==ADMIN['email'])).vip_permanent=True;db.commit()
    av=client.post('/api/v1/rooms',headers=headers,json={'accept_sharing':True,'name':'音视频房','room_type':'av_room'})
    assert av.status_code==200,av.text
    assert av.json()['data']['capacity']==6 and av.json()['data']['media_mode']=='mesh'

def test_github_verified_email_links_existing_account_and_rejects_replay(client,monkeypatch):
    settings=client.app.state.settings
    settings.github_client_id='test-client';settings.github_client_secret='test-secret';settings.auth_channels='email,github'
    async def profile(*args):return '12345','GitHub研友','','admin@test.com'
    monkeypatch.setattr(oauth,'_github_profile',profile)
    authorize=client.get('/api/v1/auth/oauth/github/authorize',params={'accepted_terms':True})
    assert authorize.status_code==200
    data=authorize.json()['data'];assert 'code_challenge_method=S256' in data['url']
    response=client.get('/api/v1/auth/oauth/github/callback',params={'state':data['state'],'code':'test-code','format':'json'})
    assert response.status_code==200,response.text
    assert response.json()['data']['user']['email']=='admin@test.com'
    with client.app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(User))==1
        assert db.scalar(select(UserAuth).where(UserAuth.provider=='github')).provider_uid=='12345'
    assert client.get('/api/v1/auth/oauth/github/callback',params={'state':data['state'],'code':'test-code','format':'json'}).status_code==400

def test_github_unconfigured_not_advertised(client):
    client.app.state.settings.auth_channels='email,github'
    assert 'github' not in client.get('/api/v1/config/public').json()['data']['enabled_auth_channels']

def test_github_profile_only_uses_verified_emails(client,monkeypatch):
    original=oauth.httpx.AsyncClient
    rows=[{'email':'unverified@test.com','primary':True,'verified':False}]
    def respond(request):
        if request.url.path.endswith('/access_token'):return httpx.Response(200,json={'access_token':'test-token'})
        if request.url.path=='/user':return httpx.Response(200,json={'id':123,'login':'test-user'})
        return httpx.Response(200,json=rows)
    monkeypatch.setattr(oauth.httpx,'AsyncClient',lambda **kwargs:original(transport=httpx.MockTransport(respond),**kwargs))
    with pytest.raises(ApiError) as error:
        asyncio.run(oauth._github_profile(client.app.state.settings,'test-code','https://boang.fun/callback','test-verifier'))
    assert error.value.status==403
    rows.append({'email':'Verified@Test.com','primary':False,'verified':True})
    result=asyncio.run(oauth._github_profile(client.app.state.settings,'test-code','https://boang.fun/callback','test-verifier'))
    assert result[0]=='123' and result[3]=='verified@test.com'

def test_media_auth_requires_same_origin_and_room_membership(client):
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/api/v1/rooms/1/media',headers={'Origin':'https://wrong.example'}):pass

def test_mesh_signaling_uses_authenticated_identity_and_does_not_leak_to_nonmembers(client):
    session=login(client,**ADMIN);headers=h(session['access_token'])
    uid=make_member(client,headers,'media@test.com','音视频同学')
    guest=login(client,'media@test.com','Friend2028')
    client.app.state.settings.features+=',av_room'
    with client.app.state.session_factory() as db:
        for user in db.scalars(select(User)).all():user.vip_permanent=True
        db.commit()
    room=client.post('/api/v1/rooms',headers=headers,json={'accept_sharing':True,'name':'测试音视频','room_type':'av_room'}).json()['data']
    assert client.post(f"/api/v1/rooms/{room['id']}/join",headers=h(guest['access_token']),json={'accept_sharing':True,'code':room['code']}).status_code==200
    url=f"/api/v1/rooms/{room['id']}/media";origin={'Origin':client.app.state.settings.public_origin}
    with client:  # Both sockets share the application's event loop, as with one production worker.
        with client.websocket_connect(url,headers=origin) as first:
            first.send_json({'token':session['access_token']});assert first.receive_json()['peers']==[]
            with client.websocket_connect(url,headers=origin) as second:
                second.send_json({'token':guest['access_token']})
                welcome=second.receive_json();assert welcome['peers'][0]['id']==session['user']['id']
                second.send_json({'type':'offer','to':session['user']['id'],'from':9999,'payload':{'type':'offer','sdp':'test-sdp'}})
                message=first.receive_json();assert message['from']==guest['user']['id'] and message['payload']['sdp']=='test-sdp'
                first.send_json({'type':'answer','to':guest['user']['id'],'payload':{'type':'answer','sdp':'reply'}})
                assert second.receive_json()['from']==session['user']['id']
            assert first.receive_json()=={'type':'left','id':guest['user']['id']}
            first.send_json({'type':'auth','token':session['access_token']})
            assert first.receive_json()=={'type':'auth-ok'}
            first.send_json({'type':'auth','token':guest['access_token']})
            from starlette.websockets import WebSocketDisconnect
            with pytest.raises(WebSocketDisconnect):first.receive_json()
