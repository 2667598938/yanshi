"""Authenticated single-worker WebRTC signaling for small mesh rooms."""
import asyncio
import json
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select
from ..deps import decode
from ..models import Room, RoomMember, User
from ..errors import ApiError
from ..services.room import guard_room_type
from ..services.room_ice import ice_servers

router = APIRouter()
# Signaling holds no media or long-lived credentials. Each room has at most six connections.
connections = {}
RECHECK_INTERVAL=5

def authorize(socket, room_id, token):
    claims = decode(socket, token, 'access')
    with socket.app.state.session_factory() as db:
        db.info['settings'] = socket.app.state.settings
        user=db.get(User,int(claims['sub']))
        room=db.get(Room,room_id)
        if not user or user.status != 'active' or user.token_version != claims['ver']:
            raise ApiError(401,40101,'请重新登录')
        from ..services.session_security import require_active_session
        require_active_session(socket,db,claims)
        if not room or room.dissolved_at or room.room_type != 'av_room' or room.media_mode != 'mesh':
            raise ApiError(403,40301,'房间不支持音视频连接')
        guard_room_type(db,user,room)
        if not db.scalar(select(RoomMember.id).where(RoomMember.room_id==room_id,RoomMember.user_id==user.id,RoomMember.sharing_confirmed.is_(True))):
            raise ApiError(403,40301,'请先加入房间')
        return user.id,user.nickname

@router.websocket('/api/v1/rooms/{room_id}/media')
async def signaling(socket: WebSocket,room_id:int):
    settings=socket.app.state.settings
    if socket.headers.get('origin') != settings.public_origin:
        await socket.close(code=4403);return
    await socket.accept()
    uid=None;room_peers=None
    try:
        raw=await asyncio.wait_for(socket.receive_text(),timeout=10)
        if len(raw)>8192:raise ValueError('Oversized authentication')
        authentication=json.loads(raw)
        if not isinstance(authentication,dict):raise ValueError('Invalid authentication')
        token=authentication.get('token','')
        uid,nickname=await run_in_threadpool(authorize,socket,room_id,token)
        room_peers=connections.setdefault(room_id,{})
        if uid in room_peers or len(room_peers)>=6:
            await socket.close(code=4409);return
        peers=[{'id':key,'nickname':value[1]} for key,value in room_peers.items()]
        room_peers[uid]=(socket,nickname)
        # The peer list makes the newcomer the sole initiator for each connection, avoiding offer glare.
        await socket.send_json({'type':'welcome','id':uid,'peers':peers,'iceServers':ice_servers(settings,uid)})
        window=time.monotonic();count=0;last_message=window
        while True:
            try:raw=await asyncio.wait_for(socket.receive_text(),timeout=RECHECK_INTERVAL)
            except asyncio.TimeoutError:
                await run_in_threadpool(authorize,socket,room_id,token)
                if time.monotonic()-last_message>=60:raise ValueError('Media connection idle')
                continue
            last_message=time.monotonic()
            if len(raw)>65536:raise ValueError('Oversized signal')
            if time.monotonic()-window>10:window=time.monotonic();count=0
            count+=1
            if count>200:raise ValueError('Signaling rate exceeded')
            message=json.loads(raw)
            if not isinstance(message,dict):raise ValueError('Invalid signal')
            if message.get('type')=='auth':
                replacement=message.get('token','')
                verified_uid,_=await run_in_threadpool(authorize,socket,room_id,replacement)
                if verified_uid!=uid:raise ValueError('Cannot switch identity in a media connection')
                token=replacement
                await socket.send_json({'type':'auth-ok'})
                continue
            await run_in_threadpool(authorize,socket,room_id,token)
            if message.get('type')=='ping':
                await socket.send_json({'type':'pong'});continue
            if message.get('type') not in ('offer','answer','candidate'):raise ValueError('Unknown signal')
            target=room_peers.get(int(message.get('to',0)))
            if target and target[0] is not socket:
                try:await target[0].send_json({'type':message['type'],'from':uid,'nickname':nickname,'payload':message.get('payload')})
                except (RuntimeError,WebSocketDisconnect):pass
    except (ApiError,ValueError,KeyError,TypeError,asyncio.TimeoutError):
        await socket.close(code=4403)
    except WebSocketDisconnect:
        pass
    finally:
        if room_peers is not None and uid in room_peers and room_peers[uid][0] is socket:
            del room_peers[uid]
            for peer,_ in list(room_peers.values()):
                try:await peer.send_json({'type':'left','id':uid})
                except (RuntimeError,WebSocketDisconnect):pass
            if not room_peers:connections.pop(room_id,None)
