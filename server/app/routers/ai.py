"""AI 助教接口（独立 Tab）：场景化对话 + 历史会话，Key 仅服务端。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, select

from ..deps import audit, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import AIConversation, AIMessage
from ..schemas.ai import ChatInput, ConversationCreate, ConversationUpdate
from ..serializers import iso
from ..services import ai as ai_service
from ..time import utcnow

router = APIRouter(prefix='/api/v1/ai', tags=['ai'])

SCENE_LABELS = {
    'general': '通用问答',
    'kaoyan': '考研答疑',
    'essay': '作文批改',
    'plan': '计划生成',
    'review': '学习复盘',
}


def convo_dict(row):
    return {'id': row.id, 'title': row.title, 'scene': row.scene,
            'created_at': iso(row.created_at), 'updated_at': iso(row.updated_at)}


def msg_dict(row):
    return {'id': row.id, 'role': row.role, 'content': row.content,
            'created_at': iso(row.created_at)}


def get_owned_conversation(db, cid, user):
    row = db.get(AIConversation, cid)
    if not row or row.user_id != user.id:
        raise ApiError(404, 40401, '对话不存在')
    return row


@router.get('/scenes')
def scenes(user=Depends(get_current_user)):
    return ok([{'key': k, 'label': v} for k, v in SCENE_LABELS.items()])


@router.get('/enabled')
def enabled(request: Request, user=Depends(get_current_user)):
    return ok({'enabled': request.app.state.settings.ai_enabled})


@router.post('/chat')
async def chat(body: ChatInput, request: Request, user=Depends(get_current_user),
               db=Depends(get_db)):
    request.app.state.transient.limit(f'ai-chat:{user.id}', 20, 60)
    convo = None
    history = []
    if body.conversation_id:
        convo = get_owned_conversation(db, body.conversation_id, user)
        rows = db.scalars(select(AIMessage).where(
            AIMessage.conversation_id == convo.id).order_by(
            AIMessage.id.desc()).limit(ai_service.HISTORY_TURNS * 2)).all()
        rows.reverse()
        history = [{'role': r.role, 'content': r.content} for r in rows]
        db.add(AIMessage(conversation_id=convo.id, role='user', content=body.content))
        convo.updated_at = utcnow()
        if convo.title == '新对话':
            convo.title = body.content[:20]
        db.commit()

    messages = ai_service.build_messages(body.scene, history, body.content, body.context)
    reply = await ai_service.call_ark(request.app.state.settings, messages)

    result = {'reply': reply, 'scene': body.scene}
    if convo:
        db.add(AIMessage(conversation_id=convo.id, role='assistant', content=reply))
        convo.updated_at = utcnow()
        db.commit()
        result['conversation_id'] = convo.id
        result['title'] = convo.title
    return ok(result)


@router.get('/conversations')
def list_conversations(db=Depends(get_db), user=Depends(get_current_user)):
    rows = db.scalars(select(AIConversation).where(
        AIConversation.user_id == user.id).order_by(AIConversation.updated_at.desc())).all()
    return ok([convo_dict(r) for r in rows])


@router.post('/conversations')
def create_conversation(body: ConversationCreate, db=Depends(get_db),
                        user=Depends(get_current_user)):
    now = utcnow()
    row = AIConversation(user_id=user.id, title=body.title or '新对话',
                         scene=body.scene, created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    db.refresh(row)
    return ok(convo_dict(row))


@router.get('/conversations/{cid}')
def get_conversation(cid: int, db=Depends(get_db), user=Depends(get_current_user)):
    convo = get_owned_conversation(db, cid, user)
    msgs = db.scalars(select(AIMessage).where(
        AIMessage.conversation_id == cid).order_by(AIMessage.id)).all()
    return ok({**convo_dict(convo), 'messages': [msg_dict(m) for m in msgs]})


@router.put('/conversations/{cid}')
def update_conversation(cid: int, body: ConversationUpdate, db=Depends(get_db),
                        user=Depends(get_current_user)):
    convo = get_owned_conversation(db, cid, user)
    convo.title = body.title
    convo.updated_at = utcnow()
    db.commit()
    return ok(convo_dict(convo))


@router.delete('/conversations/{cid}')
def delete_conversation(cid: int, request: Request, db=Depends(get_db),
                        user=Depends(get_current_user)):
    convo = get_owned_conversation(db, cid, user)
    db.execute(delete(AIMessage).where(AIMessage.conversation_id == cid))
    db.delete(convo)
    audit(db, request, 'ai.delete_conversation', user_id=user.id, detail=str(cid))
    db.commit()
    return ok()
