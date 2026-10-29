"""Regressions from a student's daily workflow; synthetic data and mock AI only."""
import json
from datetime import timedelta, timezone
import httpx
import pytest
from app.services import ai
from app.services.ai_context import account_context
from app.models import LearningRecord
from app.tests.test_ai import friend
from app.tests.test_current_workflows import admin, me
from app.tests.test_group_v1 import push
from app.time import utcnow

REAL_STREAM = ai.stream_openai


def test_pauses_excluded_from_room_display_and_background_keeps_co_study(client, friend):
    ah, uid = admin(client), me(client, friend)
    now = int(utcnow().replace(tzinfo=timezone.utc).timestamp()*1000)
    body={'device_id':'student-laptop','room_id':1,'status':'focusing',
          'focus_started_at':now-1800000,'focus_elapsed_sec':600}
    assert client.post('/api/v1/group/presence',headers=friend,json=body).status_code==200
    state=client.get('/api/v1/rooms/1',headers=ah).json()['data']
    member=next(m for m in state['members'] if m['user_id']==uid)
    assert 600<=member['presence']['focus_sec']<=602
    assert client.post('/api/v1/group/presence',headers=friend,json={**body,'status':'away'}).status_code==200
    group=client.get('/api/v1/group/members',headers=ah).json()['data']
    away=next(m for m in group if m['id']==uid)
    assert away['status']=='away' and away['roomId']==1 and '暂离' in away['statusText']
    client.put('/api/v1/users/me',headers=friend,json={'is_private_mode':True})
    hidden=next(m for m in client.get('/api/v1/group/members',headers=ah).json()['data'] if m['id']==uid)
    assert hidden['status']=='private' and hidden['roomId'] is None and hidden['isOnline'] is None


@pytest.mark.parametrize('reason',['length','content_filter'])
def test_upstream_noncompletion_is_saved_as_interrupted_not_importable(client,friend,monkeypatch,reason):
    partial='计划尚未结束\n```yanshi_tasks\n{"tasks":[{"title":"高数训练"'
    def handler(request):
        data='data: '+json.dumps({'choices':[{'delta':{'content':partial}}]},ensure_ascii=False)+'\n\n'
        data+='data: '+json.dumps({'choices':[{'delta':{},'finish_reason':reason}]})+'\n\n'
        return httpx.Response(200,text=data+'data: [DONE]\n\n')
    original=httpx.AsyncClient
    monkeypatch.setattr(httpx,'AsyncClient',lambda **kw:original(transport=httpx.MockTransport(handler),**kw))
    monkeypatch.setattr(ai,'stream_openai',REAL_STREAM)
    cid=client.post('/api/v1/ai/conversations',headers=friend,json={}).json()['data']['id']
    response=client.post('/api/v1/ai/chat/stream',headers=friend,json={'conversation_id':cid,'content':'生成计划'})
    events=[json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    assert events[-1]['type']=='error' and not any(e['type']=='done' for e in events)
    message=client.get(f'/api/v1/ai/conversations/{cid}',headers=friend).json()['data']['messages'][-1]
    assert message['interrupted'] and message['failed'] and message['content']==partial
    assert message['suggested_tasks']==[]


def test_summary_preserves_today_amid_overdue_backlog_with_hard_byte_bound(client,friend):
    now=utcnow(); day=(now+timedelta(hours=8)).date()
    stamp=int(now.replace(tzinfo=timezone.utc).timestamp()*1000)
    records=[{'id':f'old-{i}','type':'task','title':f'旧任务{i}精读长难句并整理语法笔记',
              'dueDate':(day-timedelta(days=1)).isoformat(),'done':0,'estimatedMin':45} for i in range(25)]
    records += [{'id':'today-open','type':'task','title':'今天待办高数','dueDate':day.isoformat(),'done':0},
                {'id':'today-done','type':'task','title':'今天成果英语','done':1,'doneAt':stamp}]
    push(client,friend,records)
    with client.app.state.session_factory() as db:
        result=account_context(db,me(client,friend),1200)
    assert result['tasks']['pending'][0]['title']=='今天待办高数'
    assert result['tasks']['completed'][0]['title']=='今天成果英语'
    assert result['task_counts']['today_pending']==1 and result['task_counts']['today_completed']==1
    assert len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())<=1040


def test_import_maps_own_subjects_applies_confirmed_edits_and_rejects_changed_replay(client,friend,monkeypatch):
    push(client,friend,[{'id':'my-math','type':'subject','name':'数学二','archived':0}])
    tasks=[{'title':'数学训练','subject_id':'数学二','estimated_min':30},
           {'title':'其他训练','subject_id':'not-my-subject','estimated_min':20}]
    async def answer(*args):return {'content':'```yanshi_tasks\n'+json.dumps({'tasks':tasks},ensure_ascii=False)+'\n```'}
    monkeypatch.setattr(ai,'call_openai',answer)
    cid=client.post('/api/v1/ai/conversations',headers=friend,json={'scene':'kaoyan'}).json()['data']['id']
    reply=client.post('/api/v1/ai/chat',headers=friend,json={'conversation_id':cid,'scene':'plan','content':'明日计划'}).json()['data']
    saved=client.get(f'/api/v1/ai/conversations/{cid}',headers=friend).json()['data']
    assert saved['scene']=='plan'
    path=f'/api/v1/ai/messages/{reply["message_id"]}/import-tasks'
    payload={'confirmed':True,'selected':[0,1],'edits':[{'index':0,'title':'修正后的训练','subject_id':'数学二','estimated_min':40,'due_date':'2030-01-01','accept_criteria':'独立完成10题'}]}
    result=client.post(path,headers=friend,json=payload)
    assert result.status_code==200,result.text
    assert client.post(path,headers=friend,json=payload).json()['data']==result.json()['data']
    changed={**payload,'edits':[{**payload['edits'][0],'title':'不应二次修改'}]}
    assert client.post(path,headers=friend,json=changed).status_code==409
    with client.app.state.session_factory() as db:
        rows=[json.loads(db.get(LearningRecord,(me(client,friend),rid)).body) for rid in result.json()['data']['task_ids']]
    assert rows[0]['subjectId']=='my-math' and rows[0]['title']=='修正后的训练' and rows[0]['estimatedMin']==40
    assert rows[1]['subjectId']=='other'
