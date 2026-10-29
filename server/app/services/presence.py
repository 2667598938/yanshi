import json
from datetime import timedelta
from datetime import timezone
from sqlalchemy import select, delete
from ..models import DevicePresence, RoomPresence, RoomMember, Room
from ..time import utcnow
from ..errors import ApiError

WINDOW=90

def active_devices(db,uid):
    return db.scalars(select(DevicePresence).where(DevicePresence.user_id==uid,
        DevicePresence.status!='offline',DevicePresence.heartbeat_at>=utcnow()-timedelta(seconds=WINDOW))).all()

def primary(devices):
    return max(devices,key=lambda d:({'focusing':3,'resting':2}.get(d.status,1),bool(d.room_id),d.entered_at,d.heartbeat_at)) if devices else None

def room_devices(db,uid,devices):
    valid=set(db.scalars(select(Room.id).join(RoomMember,RoomMember.room_id==Room.id).where(RoomMember.user_id==uid,Room.dissolved_at.is_(None))).all())
    return [d for d in devices if d.room_id in valid]

def project_rooms(db,uid):
    p=primary(room_devices(db,uid,active_devices(db,uid)))
    rid=p.room_id if p else None
    rows=db.scalars(select(RoomPresence).where(RoomPresence.user_id==uid)).all()
    row=next((r for r in rows if r.room_id==rid),None)
    if rid and not row:
        row=RoomPresence(room_id=rid,user_id=uid);db.add(row);rows.append(row)
    for row in rows:
        if not p or row.room_id!=rid:
            row.status='offline';row.focus_started_at=None
        else:
            values=json.loads(p.detail)
            for key in ['subject_client_id','subject_name','activity_type','mode','focus_started_at']: setattr(row,key,values.get(key))
            row.status=p.status;row.last_heartbeat_at=p.heartbeat_at

def update_presence(db,user,body):
    now=utcnow()
    db.execute(delete(DevicePresence).where(DevicePresence.user_id==user.id,DevicePresence.heartbeat_at<now-timedelta(days=1)))
    device=db.get(DevicePresence,(user.id,body.device_id))
    if not device:
        count=len(db.scalars(select(DevicePresence).where(DevicePresence.user_id==user.id)).all())
        if count>=50:raise ApiError(429,42901,'活动设备过多，请稍后重试')
        device=DevicePresence(user_id=user.id,device_id=body.device_id,entered_at=now);db.add(device)
    rid=body.room_id
    if rid:
        room=db.get(Room,rid)
        member=db.scalar(select(RoomMember.id).where(RoomMember.user_id==user.id,RoomMember.room_id==rid))
        if not room or room.dissolved_at or not member:rid=None
    if body.status=='offline':rid=None
    if device.room_id!=rid:device.entered_at=now
    device.room_id=rid;device.status=body.status;device.heartbeat_at=now
    detail=body.model_dump(exclude={'device_id','room_id'})
    if body.status!='focusing':detail['focus_started_at']=None
    elif body.focus_elapsed_sec is not None:
        # Project an effective clock anchor, excluding all pauses. Never use it
        # to create or update a historical learning record.
        detail['focus_started_at']=int(now.replace(tzinfo=timezone.utc).timestamp()*1000)-body.focus_elapsed_sec*1000
    device.detail=json.dumps(detail,ensure_ascii=False)
    db.flush();project_rooms(db,user.id);db.commit()
    return {'status':body.status,'roomId':rid}

def member_state(db,viewer,owner):
    if owner.is_private_mode and viewer.id!=owner.id:
        return {'status':'private','statusText':'隐私中','isOnline':None,'roomId':None,'roomName':None}
    devices=active_devices(db,owner.id)
    p=primary(devices)
    location=primary(room_devices(db,owner.id,devices))
    if not p:return {'status':'offline','statusText':'离线','isOnline':False,'roomId':None,'roomName':None}
    room=db.get(Room,location.room_id) if location else None
    if room and (room.dissolved_at or not db.scalar(select(RoomMember.id).where(RoomMember.room_id==room.id,RoomMember.user_id==owner.id))):room=None
    rid,name=None,None
    if room:
        readable=room.visibility=='public' or db.scalar(select(RoomMember.id).where(RoomMember.room_id==room.id,RoomMember.user_id==viewer.id))
        if readable:rid,name=room.id,room.name
        else:name='私密自习室'
    label={'focusing':'专注中','resting':'休息中','away':'暂离 · 后台'}.get(p.status,'在线')
    if not room:label+=' · 未在自习室'
    return {'status':p.status,'statusText':label,'isOnline':True,'roomId':rid,'roomName':name}
