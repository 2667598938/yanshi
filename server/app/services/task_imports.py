import json
from datetime import timezone
from sqlalchemy import select
from ..models import AITaskImport, AIMessage, AIConversation, LearningRecord, LearningOperation, User
from ..errors import ApiError
from .ai_tasks import proposals
from .sync import execute_commands, sync_write_lock

def owned_message(db,user,mid):
    m=db.get(AIMessage,mid)
    c=db.get(AIConversation,m.conversation_id) if m else None
    if not m or m.role!='assistant' or not c or c.user_id!=user.id:raise ApiError(404,40401,'消息不存在')
    return m

def status(db,uid,mid):
    receipt=db.get(AITaskImport,(uid,mid))
    if receipt:return receipt_state(receipt)
    old=db.get(LearningOperation,(uid,f'ai-task-import-{mid}'))
    return {'state':'imported','imported_count':len(json.loads(old.result)['changed']),'legacy':True} if old else {'state':'not_imported','imported_count':0}

def receipt_state(row):
    return {'state':'undone' if row.undo_result else 'imported','imported_count':len(json.loads(row.tasks)),
            'task_ids':[t['id'] for t in json.loads(row.tasks)],'undo':json.loads(row.undo_result) if row.undo_result else None}

def legacy_receipt(db,user,mid):
    old=db.get(LearningOperation,(user.id,f'ai-task-import-{mid}'))
    if not old:return None
    tasks=[{'id':c['id'],'revision':c['revision']} for c in json.loads(old.result)['changed']]
    row=AITaskImport(user_id=user.id,message_id=mid,selection='null',tasks=json.dumps(tasks));db.add(row)
    return row

def import_tasks(db,user,mid,selected):
    with sync_write_lock:
        # Serialize with normal sync writes and use a single transaction for records+receipt.
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        m=owned_message(db,user,mid)
        if json.loads(m.tool_trace or '{}').get('interrupted'):
            raise ApiError(400,40001,'该回答已中断，请重新生成完整任务计划后导入')
        tasks=proposals(m.content)
        if not tasks:raise ApiError(400,40001,'没有有效的结构化任务，请重新生成可导入计划')
        indexes=list(range(len(tasks))) if selected is None else selected
        if not indexes or len(set(indexes))!=len(indexes) or any(i<0 or i>=len(tasks) for i in indexes):raise ApiError(400,40001,'选择的任务无效')
        indexes=sorted(indexes)
        receipt=db.get(AITaskImport,(user.id,mid)) or legacy_receipt(db,user,mid)
        if receipt:
            if receipt.selection!='null' and json.loads(receipt.selection)!=indexes:raise ApiError(409,40901,'该回复已导入，不能换一组选项再次导入')
            db.commit();return receipt_state(receipt)
        stamp=int(m.created_at.replace(tzinfo=timezone.utc).timestamp()*1000)
        changes=[]
        for i in indexes:
            task=tasks[i];key=f'ai-task-{mid}-{i}'
            record={'id':key,'type':'task','title':task['title'],'subjectId':task['subject_id'] or 'other',
                'dueDate':task['due_date'],'estimatedMin':task['estimated_min'],'acceptCriteria':task['accept_criteria'],
                'phase':'custom','done':0,'doneAt':None,'createdAt':stamp,'source':'ai','source_message_id':mid}
            changes.append({'id':key,'expectedRevision':0,'record':record})
        receipt=AITaskImport(user_id=user.id,message_id=mid,selection=json.dumps(indexes),tasks='[]')
        def save(result):
            receipt.tasks=json.dumps(result['changed']);db.add(receipt)
        execute_commands(db,user.id,{'operationId':f'ai-import-v2-{mid}','changes':changes},before_commit=save)
        return receipt_state(receipt)

def undo_import(db,user,mid):
    with sync_write_lock:
        db.scalar(select(User).where(User.id==user.id).with_for_update())
        row=db.get(AITaskImport,(user.id,mid)) or legacy_receipt(db,user,mid)
        if not row:raise ApiError(404,40401,'导入记录不存在')
        if row.undo_result:return receipt_state(row)
        changes=[];kept=[]
        for item in json.loads(row.tasks):
            record=db.get(LearningRecord,(user.id,item['id']))
            if not record or record.deleted:
                kept.append({'id':item['id'],'reason':'已删除'});continue
            body=json.loads(record.body)
            if body.get('done') or record.revision!=item['revision']:
                kept.append({'id':item['id'],'reason':'已完成' if body.get('done') else '已修改'});continue
            changes.append({'id':item['id'],'expectedRevision':record.revision,'record':None})
        result={'deleted':len(changes),'kept':kept}
        def save(_):row.undo_result=json.dumps(result,ensure_ascii=False);db.add(row)
        execute_commands(db,user.id,{'operationId':f'ai-undo-v2-{mid}','changes':changes},before_commit=save)
        return receipt_state(row)
