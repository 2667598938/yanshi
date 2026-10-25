"""V1 privacy boundaries, personal configuration and explicit AI imports."""
import json
import uuid
from sqlalchemy import select
from app.models import User, LearningRecord, TimeNode, StudyGroupMember
from app.tests.conftest import login
from app.tests.test_ai import friend
from app.tests.test_attachment import upload
from app.tests.test_room import register_friend, today, session_record


def headers(client):
    return {'Authorization':'Bearer '+login(client,'admin@test.com','Admin2028')['access_token']}


def push(client,h,records):
    response=client.post('/api/v1/sync/commands',headers=h,json={'operationId':str(uuid.uuid4()),
        'changes':[{'id':r['id'],'expectedRevision':0,'record':r} for r in records]})
    assert response.status_code==200,response.text
    return response.json()['data']


def test_group_privacy_owner_admin_and_public_room_boundaries(client):
    admin=headers(client)
    owner=register_friend(client,admin,'shared@test.com','学习同学')
    key=upload(client,'/api/v1/attachments/image',owner,'mistake').json()['data']['key']
    uid=client.get('/api/v1/auth/me',headers=owner).json()['data']['id']
    push(client,owner,[{'id':'task-one','type':'task','title':'数学','estimatedMin':40,'done':0},
        {'id':'wrong-one','type':'mistake','images':[key],'answerImages':[],'content':'题干'},
        {'id':'hidden-profile','type':'userSchool','note':'个人备注不可泄露'}])
    path=f'/api/v1/group/members/{uid}/learning'
    visible=client.get(path,headers=admin).json()['data']['items']
    assert len(visible)==2 and any(r.get('estimatedMin')==40 for r in visible)
    assert client.get('/api/v1/attachments/view',headers=admin,params={'key':key}).status_code==200
    assert client.put('/api/v1/users/me',headers=owner,json={'is_private_mode':True}).status_code==200
    assert client.get(path,headers=admin).status_code==404
    assert client.get('/api/v1/attachments/view',headers=admin,params={'key':key}).status_code==404
    assert client.get(path,headers=owner).status_code==200
    client.post('/api/v1/group/presence',headers=owner,json={'status':'focusing','subject_name':'数学'})
    state=client.get('/api/v1/room',headers=admin).json()['data']
    row=next(r for r in state['members'] if r['user_id']==uid)
    assert row['presence']=={'status':'private'} and 'today_sec' not in row and 'goal' not in row
    assert state['room']['online_count']==0
    client.post('/api/v1/group/presence',headers=owner,json={'status':'offline'})
    row=next(r for r in client.get('/api/v1/room',headers=admin).json()['data']['members'] if r['user_id']==uid)
    assert row['presence']=={'status':'private'}
    client.put('/api/v1/users/me',headers=owner,json={'is_private_mode':False})
    assert client.get(path,headers=admin).status_code==200
    # Removing trusted membership does not remove public-room membership, but stops learning access.
    client.delete(f'/api/v1/admin/group-members/{uid}',headers=admin)
    assert client.get('/api/v1/room',headers=owner).status_code==200
    assert client.get(path,headers=admin).status_code==404
    assert client.get('/api/v1/attachments/view',headers=admin,params={'key':key}).status_code==404


def test_old_profile_sync_cannot_disable_privacy(client):
    h=headers(client)
    client.put('/api/v1/users/me',headers=h,json={'is_private_mode':True})
    profile=next(r for r in client.get('/api/v1/sync/records',headers=h).json()['data']['records'] if r['id']=='profile')
    response=client.post('/api/v1/sync/commands',headers=h,json={'operationId':'stale-profile', 'changes':[{
        'id':'profile','expectedRevision':profile['revision'],'record':{'id':'profile','key':'profile','type':'profile','value':{'privacy_mode':False,'nickname':'旧资料'}}}]})
    assert response.status_code==200,response.text
    assert client.get('/api/v1/auth/me',headers=h).json()['data']['is_private_mode'] is True
    assert client.put('/api/v1/users/me',headers=h,json={'privacy_mode':False,'is_private_mode':True}).status_code==400


def test_personal_time_nodes_sync_delete_and_validation(client):
    h=headers(client)
    nodes=client.get('/api/v1/time-nodes',headers=h).json()['data']
    assert len(nodes)==2
    for row in nodes:
        response=client.post('/api/v1/sync/commands',headers=h,json={'operationId':str(uuid.uuid4()),'changes':[{'id':row['id'],'expectedRevision':row['_rev'],'record':None}]})
        assert response.status_code==200,response.text
    assert client.get('/api/v1/time-nodes',headers=h).json()['data']==[]
    value={'node_name':'复试','target_date':'2028-03-01','show_on_home':True,'custom_msg':'加油'}
    push(client,h,[{'id':'custom-node','type':'timeNode','value':value}])
    assert client.get('/api/v1/time-nodes',headers=h).json()['data'][0]['custom_msg']=='加油'
    with client.app.state.session_factory() as db:
        assert db.get(TimeNode,(1,'custom-node')).node_name=='复试'
    bad=client.post('/api/v1/sync/commands',headers=h,json={'operationId':'bad-date','changes':[{'id':'invalid-node','expectedRevision':0,'record':{'id':'invalid-node','type':'timeNode','value':{**value,'target_date':'2028-02-30'}}}]})
    assert bad.status_code==400


def test_personal_schools_unlimited_delete_no_reseed_and_images(client):
    h=headers(client)
    peer=register_friend(client,h,'school@test.com','梦校同学')
    originals=client.get('/api/v1/schools',headers=h).json()['data']
    for i in range(9):
        response=client.post('/api/v1/schools',headers=h,json={'key':f'custom-{i}','name':f'梦校{i}','sort_order':-i})
        assert response.status_code==200,response.text
    mine=client.get('/api/v1/schools',headers=h).json()['data']
    assert len(mine)==len(originals)+9 and mine[0]['key']=='custom-8'
    assert client.get('/api/v1/schools/custom-8',headers=peer).status_code==404
    key=upload(client,'/api/v1/attachments/image',h,'school').json()['data']['key']
    assert client.put('/api/v1/schools/custom-8',headers=h,json={'album_keys':[key]}).status_code==200
    assert client.post('/api/v1/schools',headers=peer,json={'key':'stolen','name':'不能盗用','album_keys':[key]}).status_code==400
    for row in mine:
        assert client.delete('/api/v1/schools/'+row['key'],headers=h).status_code==200
    assert client.get('/api/v1/schools',headers=h).json()['data']==[]


def test_ai_owner_context_and_confirmed_import(client,friend,monkeypatch):
    admin=headers(client)
    peer_record={'id':'peer-secret','type':'task','title':'绝不能出现在模型里的组员任务'}
    push(client,admin,[peer_record])
    push(client,friend,[{'id':'own-task','type':'task','title':'复习积分','estimatedMin':45,'done':0},
        {'id':'own-done','type':'task','title':'完成英语','estimatedMin':30,'done':1},session_record('own-session',1500)])
    client.put('/api/v1/users/me',headers=friend,json={'is_private_mode':True})
    captured={}
    async def fake(settings,messages):
        captured['messages']=messages
        return '明日计划\n```yanshi_tasks\n'+json.dumps({'tasks':[{'title':'巩固积分','due_date':'2026-10-26','estimated_min':50}]},ensure_ascii=False)+'\n```'
    monkeypatch.setattr('app.services.ai.call_ark',fake)
    cid=client.post('/api/v1/ai/conversations',headers=friend,json={}).json()['data']['id']
    result=client.post('/api/v1/ai/chat',headers=friend,json={'conversation_id':cid,'content':'帮我计划明天'})
    assert result.status_code==200,result.text
    data=result.json()['data'];payload=json.dumps(captured['messages'],ensure_ascii=False)
    assert '复习积分' in payload and '完成英语' in payload and '1500' in payload and '45' in payload
    assert peer_record['title'] not in payload and 'api_key' not in payload
    path=f'/api/v1/ai/messages/{data["message_id"]}/import-tasks'
    assert len(data['suggested_tasks'])==1
    assert client.post(path,headers=friend,json={'confirmed':False}).status_code==400
    assert client.post(path,headers=admin,json={'confirmed':True}).status_code in (403,404)
    for _ in range(2):
        response=client.post(path,headers=friend,json={'confirmed':True})
        assert response.status_code==200,response.text
    uid=client.get('/api/v1/auth/me',headers=friend).json()['data']['id']
    with client.app.state.session_factory() as db:
        imported=db.scalars(select(LearningRecord).where(LearningRecord.user_id==uid,LearningRecord.id.like('ai-task-%'))).all()
        assert len(imported)==1 and json.loads(imported[0].body)['estimatedMin']==50
    assert client.post('/api/v1/ai/chat',headers=friend,json={'content':'操作页面','use_tools':True}).status_code==403


def test_ai_malformed_task_blocks_are_not_importable():
    from app.services.ai_tasks import proposals
    assert proposals('```yanshi_tasks\n{broken}\n```')==[]
    assert proposals('```json\n{"tasks":[{"title":"ok","estimated_min":-1}]}\n```')==[]
    assert proposals('```json\n{"tasks":[]}\n```')==[]
