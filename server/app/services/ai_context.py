"""Bounded, owner-only context. UTF-8 byte budget conservatively bounds token input."""
import json
from datetime import timedelta
from sqlalchemy import select,func
from ..models import LearningRecord, RoomPresence
from ..time import utcnow
from .presence import primary,active_devices

def bounded_int(value,upper):
    try:return max(0,min(upper,int(value or 0)))
    except (TypeError,ValueError,OverflowError):return 0

def account_context(db,user_id,budget=1200):
    now=utcnow();today=(now+timedelta(hours=8)).date();heat={};pending=[];completed=[];recent_done=0;overdue=0;today_count=0
    rows=db.scalars(select(LearningRecord).where(LearningRecord.user_id==user_id,LearningRecord.deleted==0,
        func.json_extract(LearningRecord.body,'$.type').in_(['task','session']))).all()
    for row in rows:
        v=json.loads(row.body)
        if v.get('type')=='session':
            day=str(v.get('date',''))
            if (today-timedelta(days=29)).isoformat()<=day<=today.isoformat():heat[day]=heat.get(day,0)+bounded_int(v.get('actualSec'),10800)
            if day==today.isoformat() and v.get('status')=='done':today_count+=1
        else:
            item={'title':str(v.get('title',''))[:70],'due':str(v.get('dueDate',''))[:10],
                  'min':bounded_int(v.get('estimatedMin'),1440),'criteria':str(v.get('acceptCriteria',''))[:80]}
            if v.get('done'):
                try: completed_at=int(v.get('doneAt') or 0)
                except (ValueError,TypeError,OverflowError): completed_at=0
                completed.append((completed_at,item))
                try:
                    from datetime import datetime,timezone
                    day=datetime.fromtimestamp(int(v.get('doneAt') or 0)/1000,timezone(timedelta(hours=8))).date()
                    item['completed_on']=day.isoformat() if v.get('doneAt') else ''
                    if today-timedelta(days=6)<=day<=today:recent_done+=1
                except (ValueError,TypeError,OverflowError,OSError):item['completed_on']=''
            else:
                pending.append(item)
                if item['due'] and item['due']<today.isoformat():overdue+=1
    pending.sort(key=lambda t:t['due'] or '9999')
    completed.sort(key=lambda pair:pair[0],reverse=True)
    device=primary(active_devices(db,user_id))
    status=device.status if device else 'offline'
    if not device:
        legacy=db.scalar(select(RoomPresence).where(RoomPresence.user_id==user_id).order_by(RoomPresence.last_heartbeat_at.desc()).limit(1))
        if legacy and legacy.status!='offline' and (now-legacy.last_heartbeat_at).total_seconds()<=90:status=legacy.status
    result={'source':'本人已同步账号摘要；只读，不含组员/密钥','date':today.isoformat(),
        'tasks':{'pending':pending[:20],'completed':[item for _,item in completed[:3]]},'task_counts':{'pending':len(pending),'completed':len(completed),'overdue_pending':overdue},
        'recent_7_days':{'completed':recent_done},'self_status':status,
        'today_focus_seconds':heat.get(today.isoformat(),0),'today_pomodoros':today_count,
        'heatmap':{'days':30,'active_days':sum(sec>0 for sec in heat.values()),'seconds':sum(heat.values())},
        'task_list_truncated':len(pending)>20 or len(completed)>3}
    # One UTF-8 byte per estimated token is deliberately conservative across providers.
    cap=max(600,min(12000,budget))-160
    while len(json.dumps(result,ensure_ascii=False,separators=(',',':')).encode())>cap:
        # Preserve both recent accomplishments and pending work when space allows.
        pool=max(result['tasks'].values(),key=len)
        if not pool:break
        pool.pop();result['task_list_truncated']=True
    return result

TASK_INSTRUCTION='''当用户要求计划、安排任务或把回复转换为任务时，必须直接生成可导入任务，不要只说等待确认。需要生成可导入的任务计划时，在回复末尾额外提供一个yanshi_tasks代码块，内容为JSON对象：
{"tasks":[{"title":"任务名称","due_date":"YYYY-MM-DD","estimated_min":30,"subject_id":"other","accept_criteria":"完成标准"}]}。
最多30条；任务仅是建议，必须由用户预览并手动确认导入，你不能自动新增或修改任何系统数据。不需要生成计划时无需此块。'''
