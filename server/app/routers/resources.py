"""资料区：VIP 发布、后端脱敏、点赞、收藏、编辑删除。"""
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from ..deps import audit, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import Resource, ResourceFavorite, ResourceLike, User
from ..schemas.content import FavoriteState, ResourceInput, ResourceUpdate
from ..serializers import iso
from ..services import features as feature_service
from ..services.messages import create_message
from ..time import utcnow

router = APIRouter(prefix='/api/v1/resources', tags=['resources'])


def mask_url(url: str) -> str:
    """保留协议与域名，路径中间 6 位替换为 ******。"""
    parsed = urlparse(url)
    path = parsed.path or '/'
    if len(path) <= 8:
        masked = path[:1] + '******' if path else '/******'
    else:
        mid = len(path) // 2
        masked = path[:max(0, mid - 3)] + '******' + path[mid + 3:]
    return f'{parsed.scheme}://{parsed.netloc}{masked}'


def is_vip(user):
    return bool(user.vip_until and user.vip_until > utcnow())


def _resource_dict(row, owner, user, like_count, liked, favorited, full_link=None):
    vip = is_vip(user) if full_link is None else full_link
    return {
        'id': row.id,
        'title': row.title,
        'url': row.url if vip else mask_url(row.url),
        'code': row.code if vip else '',
        'masked': not vip,
        'category': row.category,
        'intro': row.intro,
        'owner': {'id': owner.id, 'nickname': owner.nickname} if owner else None,
        'like_count': like_count,
        'liked': liked,
        'favorited': favorited,
        'can_edit': bool(owner and (owner.id == user.id or user.role == 'admin')),
        'created_at': iso(row.created_at),
        'updated_at': iso(row.updated_at),
    }


def _lists(db, user, rows):
    ids = [r.id for r in rows]
    if not ids:
        return [], {}, set(), set()
    owners = {u.id: u for u in db.scalars(select(User).where(
        User.id.in_([r.user_id for r in rows]))).all()}
    counts = dict(db.execute(
        select(ResourceLike.resource_id, func.count()).where(
            ResourceLike.resource_id.in_(ids)).group_by(ResourceLike.resource_id)).all())
    liked = set(db.scalars(select(ResourceLike.resource_id).where(
        ResourceLike.user_id == user.id, ResourceLike.resource_id.in_(ids))).all())
    favorited = set(db.scalars(select(ResourceFavorite.resource_id).where(
        ResourceFavorite.user_id == user.id,
        ResourceFavorite.resource_id.in_(ids))).all())
    full_link = feature_service.has_feature(db, user, 'materials')
    payload = [_resource_dict(r, owners.get(r.user_id), user, int(counts.get(r.id, 0)),
                              r.id in liked, r.id in favorited, full_link)
               for r in rows]
    return payload, owners, liked, favorited


@router.get('')
def list_resources(q: str = '', category: str = '', user=Depends(get_current_user),
                   db=Depends(get_db)):
    query = select(Resource).where(Resource.deleted_at.is_(None))
    if q.strip():
        like = f'%{q.strip()}%'
        query = query.where((Resource.title.like(like)) | (Resource.intro.like(like)))
    if category.strip():
        query = query.where(Resource.category == category.strip())
    rows = db.scalars(query.order_by(Resource.id.desc()).limit(100)).all()
    payload, _, _, _ = _lists(db, user, rows)
    return ok(payload)


@router.get('/favorites')
def my_favorites(user=Depends(get_current_user), db=Depends(get_db)):
    favs = db.scalars(select(ResourceFavorite).where(
        ResourceFavorite.user_id == user.id).order_by(
        ResourceFavorite.id.desc()).limit(100)).all()
    ids = [f.resource_id for f in favs]
    if not ids:
        return ok([])
    rows = db.scalars(select(Resource).where(
        Resource.id.in_(ids), Resource.deleted_at.is_(None))).all()
    order = {rid: i for i, rid in enumerate(ids)}
    rows = sorted(rows, key=lambda r: order.get(r.id, 999))
    payload, _, _, _ = _lists(db, user, rows)
    return ok(payload)


@router.get('/mine')
def my_resources(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(select(Resource).where(
        Resource.user_id == user.id, Resource.deleted_at.is_(None)
    ).order_by(Resource.id.desc())).all()
    payload, _, _, _ = _lists(db, user, rows)
    return ok(payload)


@router.get('/{rid}')
def get_resource(rid: int, user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(Resource, rid)
    if not row or row.deleted_at:
        raise ApiError(404, 40401, '资料不存在')
    owner = db.get(User, row.user_id)
    payload, _, _, _ = _lists(db, user, [row])
    return ok(payload[0])


@router.post('')
def create_resource(body: ResourceInput, request: Request,
                    user=Depends(get_current_user), db=Depends(get_db)):
    if not is_vip(user):
        raise ApiError(403, 40301, '仅 VIP 可发布资料')
    now = utcnow()
    row = Resource(user_id=user.id, title=body.title.strip(), url=body.url.strip(),
                   code=body.code.strip(), category=body.category.strip(),
                   intro=body.intro.strip(), created_at=now, updated_at=now)
    db.add(row)
    audit(db, request, 'resource.create', user_id=user.id, detail=row.title)
    db.commit()
    db.refresh(row)
    return ok(_resource_dict(row, user, user, 0, False, False,
                             feature_service.has_feature(db, user, 'materials')))


@router.put('/{rid}')
def update_resource(rid: int, body: ResourceUpdate, request: Request,
                    user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(Resource, rid)
    if not row or row.deleted_at:
        raise ApiError(404, 40401, '资料不存在')
    if row.user_id != user.id and user.role != 'admin':
        raise ApiError(403, 40301, '只能编辑自己发布的资料')
    for key in ('title', 'url', 'code', 'category', 'intro'):
        value = getattr(body, key)
        if value is not None:
            setattr(row, key, value.strip())
    row.updated_at = utcnow()
    audit(db, request, 'resource.update', user_id=user.id, detail=str(rid))
    db.commit()
    owner = db.get(User, row.user_id)
    return ok(_resource_dict(row, owner, user, 0, False, False,
                             feature_service.has_feature(db, user, 'materials')))


@router.delete('/{rid}')
def delete_resource(rid: int, request: Request, reason: str = '',
                    user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(Resource, rid)
    if not row or row.deleted_at:
        raise ApiError(404, 40401, '资料不存在')
    is_owner = row.user_id == user.id
    if not is_owner and user.role != 'admin':
        raise ApiError(403, 40301, '只能删除自己发布的资料')
    reason = (reason or '').strip()
    if user.role == 'admin' and not is_owner and not reason:
        raise ApiError(400, 40001, '管理员删除内容必须填写原因')
    row.deleted_at = utcnow()
    if not is_owner:
        owner = db.get(User, row.user_id)
        if owner:
            create_message(db, owner, 'content', '资料已被管理员删除',
                           f'你的资料「{row.title}」因违规被删除。'
                           + (f'原因：{reason[:200]}' if reason else ''),
                           link='/resources')
    audit(db, request, 'resource.delete', user_id=user.id, detail=str(rid))
    db.commit()
    return ok()


@router.post('/{rid}/like')
def toggle_like(rid: int, request: Request, user=Depends(get_current_user),
                db=Depends(get_db)):
    row = db.get(Resource, rid)
    if not row or row.deleted_at:
        raise ApiError(404, 40401, '资料不存在')
    existing = db.scalar(select(ResourceLike).where(
        ResourceLike.resource_id == rid, ResourceLike.user_id == user.id))
    if existing:
        db.delete(existing)
        liked = False
    else:
        db.add(ResourceLike(resource_id=rid, user_id=user.id))
        liked = True
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        liked = True
    count = db.scalar(select(func.count()).select_from(ResourceLike).where(
        ResourceLike.resource_id == rid)) or 0
    return ok({'liked': liked, 'like_count': int(count)})


@router.post('/{rid}/favorite')
def toggle_favorite(rid: int, request: Request, user=Depends(get_current_user),
                    db=Depends(get_db)):
    row = db.get(Resource, rid)
    if not row or row.deleted_at:
        raise ApiError(404, 40401, '资料不存在')
    existing = db.scalar(select(ResourceFavorite).where(
        ResourceFavorite.resource_id == rid, ResourceFavorite.user_id == user.id))
    if existing:
        db.delete(existing)
        favorited = False
    else:
        db.add(ResourceFavorite(resource_id=rid, user_id=user.id))
        favorited = True
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        favorited = True
    return ok({'favorited': favorited})


@router.put('/{rid}/favorite')
def set_favorite(rid: int, body: FavoriteState, user=Depends(get_current_user),
                 db=Depends(get_db)):
    """离线同步用：显式设置收藏状态，重复提交幂等。"""
    row = db.get(Resource, rid)
    if not row or row.deleted_at:
        raise ApiError(404, 40401, '资料不存在')
    existing = db.scalar(select(ResourceFavorite).where(
        ResourceFavorite.resource_id == rid, ResourceFavorite.user_id == user.id))
    if body.favorited and not existing:
        db.add(ResourceFavorite(resource_id=rid, user_id=user.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    elif not body.favorited and existing:
        db.delete(existing)
        db.commit()
    return ok({'favorited': body.favorited})
