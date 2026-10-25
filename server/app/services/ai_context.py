"""只读本账号业务数据的有界摘要；不读取DOM、文件系统或组员记录。"""
import json
from datetime import timedelta
from sqlalchemy import select, func
from ..models import LearningRecord, RoomPresence
from ..time import utcnow


def bounded_int(value, upper):
    try: return max(0,min(upper,int(value or 0)))
    except (TypeError,ValueError,OverflowError): return 0


def account_context(db, user_id):
    today=(utcnow()+timedelta(hours=8)).date()
    heat={ (today-timedelta(days=i)).isoformat():0 for i in range(30,-1,-1) }
    tasks={'pending':[], 'completed':[]}; totals={'pending':0,'completed':0}
    rows=db.scalars(select(LearningRecord).where(LearningRecord.user_id==user_id,LearningRecord.deleted==0,
        func.json_extract(LearningRecord.body,'$.type').in_(['task','session']))).all()
    for row in rows:
        value=json.loads(row.body)
        if value.get('type')=='session' and value.get('date') in heat:
            heat[value['date']]+=bounded_int(value.get('actualSec'),10800)
        elif value.get('type')=='task':
            state='completed' if value.get('done') else 'pending';totals[state]+=1
            if len(tasks[state])<12:
                tasks[state].append({'title':str(value.get('title',''))[:100],
                    'due_date':str(value.get('dueDate',''))[:10],
                    'estimated_min':bounded_int(value.get('estimatedMin'),1440)})
    presence=db.scalar(select(RoomPresence).where(RoomPresence.user_id==user_id)
        .order_by(RoomPresence.last_heartbeat_at.desc()).limit(1))
    active=bool(presence and (utcnow()-presence.last_heartbeat_at).total_seconds()<=90 and presence.status!='offline')
    result={'source':'本人已同步账号数据（只读摘要，不含组员数据或任何密钥）',
        'beijing_date':today.isoformat(),'tasks':tasks,'task_counts':totals,
        'self_status':presence.status if active else 'offline',
        'today_focus_seconds':heat[today.isoformat()], 'heatmap':heat,
        'task_list_truncated':any(totals[k]>len(tasks[k]) for k in tasks)}
    # 固定最多24条任务、31天统计；不发送原始数据库、附件或凭据。
    return result


TASK_INSTRUCTION='''需要生成可导入的任务计划时，在回复末尾额外提供一个yanshi_tasks代码块，内容为JSON对象：
{"tasks":[{"title":"任务名称","due_date":"YYYY-MM-DD","estimated_min":30,"subject_id":"other","accept_criteria":"完成标准"}]}。
最多30条；任务仅是建议，必须由用户预览并手动确认导入，你不能自动新增或修改任何系统数据。不需要生成计划时无需此块。'''
