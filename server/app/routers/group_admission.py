"""Retired global-group routes fail closed; room invitations replace them.

Historical invite/application rows remain for audit, never as sharing rights.
"""

from fastapi import APIRouter, Depends
from ..deps import get_current_user
from ..errors import ApiError

router = APIRouter(prefix="/api/v1/group-admission", tags=["retired-group-admission"])


@router.api_route(
    "/{legacy_path:path}", methods=["GET", "POST", "DELETE", "PUT", "PATCH"]
)
def retired(legacy_path: str, user=Depends(get_current_user)):
    raise ApiError(
        410, 41001, "全站小组已停用；请到自习室创建好友房间、凭码加入或提交入房申请"
    )
