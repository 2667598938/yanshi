"""AI 助教接口（独立 Tab）：VIP 自填 Key（BYOK）+ 服务端兜底 Key。"""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select

from ..deps import audit, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import AIConversation, AIMessage, UserAIKey
from ..schemas.ai import (
    AIKeyInput, AIModelsInput, ChatInput, ConversationCreate, ConversationUpdate,
)
from ..serializers import iso
from ..services import ai as ai_service
from ..services import ai_key as crypto
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
            'prompt_tokens': row.prompt_tokens, 'completion_tokens': row.completion_tokens,
            'latency_ms': row.latency_ms,
            'created_at': iso(row.created_at)}


def is_vip(user):
    return bool(user.vip_until and user.vip_until > utcnow())


def require_vip(user):
    if not is_vip(user):
        raise ApiError(403, 40301, '该功能需要 VIP')


def key_dict(row):
    return {'configured': row is not None,
            'provider': row.provider if row else 'deepseek',
            'base_url': row.base_url if row else '',
            'model': row.model if row else '',
            'key_mask': row.key_mask if row else '',
            'updated_at': iso(row.updated_at) if row else None}


def enc_secret(request):
    return request.app.state.settings.ai_key_enc_secret or request.app.state.secret


def get_owned_conversation(db, cid, user):
    row = db.get(AIConversation, cid)
    if not row or row.user_id != user.id:
        raise ApiError(404, 40401, '对话不存在')
    return row


@router.get('/scenes')
def scenes(user=Depends(get_current_user)):
    return ok([{'key': k, 'label': v} for k, v in SCENE_LABELS.items()])


@router.get('/enabled')
def enabled(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    key_row = db.get(UserAIKey, user.id)
    return ok({'enabled': bool(key_row) or request.app.state.settings.ai_enabled,
               'byok': key_row is not None, 'vip': is_vip(user)})


# ---------------------------------------------------------------- AI Key（VIP）
@router.get('/key')
def get_key(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    require_vip(user)
    return ok(key_dict(db.get(UserAIKey, user.id)))


@router.put('/key')
def save_key(body: AIKeyInput, request: Request, user=Depends(get_current_user),
             db=Depends(get_db)):
    require_vip(user)
    base_url = ai_service.resolve_base_url(body.provider, body.base_url)
    model = body.model.strip() or ai_service.default_model(body.provider)
    cipher_text = crypto.encrypt(enc_secret(request), body.api_key.strip(), str(user.id))
    row = db.get(UserAIKey, user.id)
    if row is None:
        row = UserAIKey(user_id=user.id)
        db.add(row)
    row.provider = body.provider
    row.base_url = base_url
    row.model = model
    row.key_cipher = cipher_text
    row.key_mask = crypto.mask(body.api_key)
    row.updated_at = utcnow()
    audit(db, request, 'ai.save_key', user_id=user.id, detail=body.provider)
    db.commit()
    db.refresh(row)
    return ok(key_dict(row))


@router.delete('/key')
def delete_key(request: Request, user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(UserAIKey, user.id)
    if row:
        db.delete(row)
        audit(db, request, 'ai.delete_key', user_id=user.id)
        db.commit()
    return ok(key_dict(None))


@router.post('/models')
async def models(body: AIModelsInput, request: Request, user=Depends(get_current_user),
                 db=Depends(get_db)):
    require_vip(user)
    key_row = db.get(UserAIKey, user.id)
    api_key = body.api_key.strip()
    if not api_key and key_row:
        api_key = crypto.decrypt(enc_secret(request), key_row.key_cipher, str(user.id))
    if not api_key:
        raise ApiError(400, 40001, '请先填写 API Key')
    base_url = ai_service.resolve_base_url(
        body.provider, body.base_url or (key_row.base_url if key_row else ''))
    items = await ai_service.fetch_models(base_url, api_key)
    fallback = not items
    if fallback and ai_service.default_model(body.provider):
        items = [ai_service.default_model(body.provider)]
    return ok({'models': items, 'fallback': fallback, 'provider': body.provider})


@router.post('/chat')
async def chat(body: ChatInput, request: Request, user=Depends(get_current_user),
               db=Depends(get_db)):
    request.app.state.transient.limit(f'ai-chat:{user.id}', 20, 60)
    key_row = db.get(UserAIKey, user.id)
    if key_row:
        require_vip(user)

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
    if key_row:
        api_key = crypto.decrypt(enc_secret(request), key_row.key_cipher, str(user.id))
        result = await ai_service.call_openai(
            key_row.base_url or ai_service.resolve_base_url(key_row.provider),
            api_key, key_row.model or ai_service.default_model(key_row.provider),
            messages, request.app.state.settings.ai_max_tokens)
        reply = result['content']
    else:
        reply = await ai_service.call_ark(request.app.state.settings, messages)
        result = {'content': reply, 'prompt_tokens': None,
                  'completion_tokens': None, 'latency_ms': None}

    out = {'reply': reply, 'scene': body.scene,
           'prompt_tokens': result['prompt_tokens'],
           'completion_tokens': result['completion_tokens'],
           'latency_ms': result['latency_ms']}
    if convo:
        db.add(AIMessage(conversation_id=convo.id, role='assistant', content=reply,
                         prompt_tokens=result['prompt_tokens'],
                         completion_tokens=result['completion_tokens'],
                         latency_ms=result['latency_ms']))
        convo.updated_at = utcnow()
        db.commit()
        out['conversation_id'] = convo.id
        out['title'] = convo.title
    return ok(out)


@router.post('/chat/stream')
async def chat_stream(body: ChatInput, request: Request, user=Depends(get_current_user),
                      db=Depends(get_db)):
    """SSE 流式对话：逐字返回 delta，结束时落库并回传会话信息。"""
    request.app.state.transient.limit(f'ai-chat:{user.id}', 20, 60)
    key_row = db.get(UserAIKey, user.id)
    if key_row:
        require_vip(user)

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

    def sse(payload):
        return 'data: ' + json.dumps(payload, ensure_ascii=False) + '\n\n'

    async def gen():
        reply = ''
        usage = {}
        latency = None
        chunk = {}
        try:
            if key_row:
                stream = ai_service.stream_openai(
                    key_row.base_url or ai_service.resolve_base_url(key_row.provider),
                    crypto.decrypt(enc_secret(request), key_row.key_cipher, str(user.id)),
                    key_row.model or ai_service.default_model(key_row.provider),
                    messages, request.app.state.settings.ai_max_tokens)
            else:
                stream = ai_service.stream_ark(request.app.state.settings, messages)
            async for chunk in stream:
                if chunk.get('delta'):
                    reply += chunk['delta']
                    yield sse({'type': 'delta', 'text': chunk['delta']})
            if 'usage' in chunk:
                usage = chunk.get('usage') or {}
                latency = chunk.get('latency_ms')
        except ApiError as e:
            yield sse({'type': 'error', 'message': e.message})
            return
        except Exception:
            yield sse({'type': 'error', 'message': 'AI 服务异常，请稍后重试'})
            return

        prompt_tokens = usage.get('prompt_tokens')
        completion_tokens = usage.get('completion_tokens')
        out = {'type': 'done', 'reply': reply, 'scene': body.scene,
               'prompt_tokens': prompt_tokens, 'completion_tokens': completion_tokens,
               'latency_ms': latency}
        if convo:
            db.add(AIMessage(conversation_id=convo.id, role='assistant', content=reply,
                             prompt_tokens=prompt_tokens,
                             completion_tokens=completion_tokens, latency_ms=latency))
            convo.updated_at = utcnow()
            db.commit()
            out['conversation_id'] = convo.id
            out['title'] = convo.title
        yield sse(out)

    return StreamingResponse(
        gen(), media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


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
