"""学习数据同步接口（本地优先）。"""
from fastapi import APIRouter, Depends, Request, Query

from ..deps import get_current_user, get_db
from ..errors import ok
from ..models import User
from ..schemas.sync import SyncCommand
from ..services import sync as sync_service

router = APIRouter(prefix='/api/v1/sync', tags=['sync'])


@router.get('/records')
def get_records(request: Request, since: int | None = Query(default=None, ge=0),
                db=Depends(get_db), user: User = Depends(get_current_user)):
    # 同步限流：每分钟 120 次（含拉取与提交）
    request.app.state.transient.limit(f'sync:r:{user.id}', 120, 60)
    return ok(sync_service.pull_records(db, user.id, since))


@router.post('/commands')
def post_commands(request: Request, body: SyncCommand, db=Depends(get_db),
                  user: User = Depends(get_current_user)):
    request.app.state.transient.limit(f'sync:w:{user.id}', 120, 60)
    command_dict = body.model_dump()
    return ok(sync_service.execute_commands(db, user.id, command_dict))
