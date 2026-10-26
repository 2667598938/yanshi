import json
from datetime import date
from .public import config_get
from fastapi import APIRouter, Depends
from sqlalchemy import select
from ..deps import get_current_user, get_db
from ..models import User, TimeNode, LearningRecord, LearningChange
from ..errors import ok
from ..services.sync import sync_write_lock

router = APIRouter(prefix='/api/v1/time-nodes', tags=['time-nodes'])


@router.get('')
def nodes(user=Depends(get_current_user), db=Depends(get_db)):
    with sync_write_lock:
        db.refresh(user, with_for_update=True)
        if not user.time_nodes_initialized:
            try:
                exam_day=date.fromisoformat(user.exam_date or config_get(db,'exam_date','2027-12-25'))
            except (ValueError,TypeError):
                exam_day=date(2027,12,25)
            score_day=date(min(exam_day.year+1,9999),2,20)
            for key,name,day in [('exam','考研初试',exam_day.isoformat()),('score','初试出分',score_day.isoformat())]:
                record_id = f'time-node-{key}'
                if db.get(LearningRecord, (user.id,record_id)): continue
                value = dict(node_name=name,target_date=day,show_on_home=True,custom_msg='')
                db.add(TimeNode(user_id=user.id,id=record_id,**value))
                db.add(LearningRecord(user_id=user.id,id=record_id,body=json.dumps(
                    {'id':record_id,'type':'timeNode','value':value},ensure_ascii=False), revision=1,deleted=0))
                db.add(LearningChange(user_id=user.id,record_id=record_id,revision=1))
            user.time_nodes_initialized = True
            db.commit()
    records = db.scalars(select(LearningRecord).where(LearningRecord.user_id == user.id,
        LearningRecord.deleted == 0)).all()
    return ok([{'id':r.id,'_rev':r.revision, **json.loads(r.body)['value']} for r in records
               if json.loads(r.body).get('type') == 'timeNode'])
