"""资料区：VIP 发布、后端脱敏、点赞、收藏、编辑删除。"""
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, update
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
    return feature_service.is_vip(user)


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
        ResourceFavorite.user_id == user.id, ResourceFavorite.active.is_(True),
        ResourceFavorite.resource_id.in_(ids))).all())
    full_link = feature_service.has_feature(db, user, 'materials')
    payload = [_resource_dict(r, owners.get(r.user_id), user, int(counts.get(r.id, 0)),
                              r.id in liked, r.id in favorited, full_link)
               for r in rows]
    revisions = dict(db.execute(select(ResourceFavorite.resource_id, ResourceFavorite.revision).where(
        ResourceFavorite.user_id == user.id, ResourceFavorite.resource_id.in_(ids))).all())
    for item in payload: item['favorite_revision'] = revisions.get(item['id'], 0)
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
        ResourceFavorite.user_id == user.id, ResourceFavorite.active.is_(True)).order_by(
        ResourceFavorite.id.desc())).all()
    ids = [f.resource_id for f in favs]
    if not ids:
        return ok([])
    rows = db.scalars(select(Resource).where(
        Resource.id.in_(ids), Resource.deleted_at.is_(None))).all()
    order = {rid: i for i, rid in enumerate(ids)}
    rows = sorted(rows, key=lambda r: order.get(r.id, 999))
    payload, _, _, _ = _lists(db, user, rows)
    return ok(payload)


@router.get('/favorite-mirror')
def favorite_mirror(after_id: int = 0, user=Depends(get_current_user), db=Depends(get_db)):
    states = db.scalars(select(ResourceFavorite).where(ResourceFavorite.user_id == user.id,
        ResourceFavorite.id > after_id).order_by(ResourceFavorite.id).limit(100)).all()
    ids = [s.resource_id for s in states]
    resources = db.scalars(select(Resource).where(Resource.id.in_(ids), Resource.deleted_at.is_(None))).all()
    payload, _, _, _ = _lists(db, user, resources)
    by_id = {r['id']: r for r in payload}
    return ok({'items': [{'resourceId': s.resource_id, 'revision': s.revision,
        'favorited': bool(s.active and s.resource_id in by_id), 'resource': by_id.get(s.resource_id)}
        for s in states], 'next': states[-1].id if len(states) == 100 else None})


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


def _set_favorite(rid, favorited, expected, user, db):
    row = db.get(Resource, rid)
    if not row or row.deleted_at: raise ApiError(404, 40401, '资料不存在')
    existing = db.scalar(select(ResourceFavorite).where(
        ResourceFavorite.resource_id == rid, ResourceFavorite.user_id == user.id))
    revision = existing.revision if existing else 0
    if existing and existing.active == favorited:
        return ok({'favorited': favorited, 'revision': revision})
    if expected is not None and expected != revision:
        raise ApiError(409, 40902, '收藏已在其他设备更新，请选择保留版本',
            data={'current': {'resourceId': rid, 'favorited': bool(existing and existing.active),
                              'revision': revision}})
    if existing:
        changed = db.execute(update(ResourceFavorite).where(ResourceFavorite.id == existing.id,
            ResourceFavorite.revision == revision).values(active=favorited,
                revision=ResourceFavorite.revision + 1)).rowcount
        if not changed:
            db.rollback()
            raise ApiError(409, 40902, '收藏状态已变化，请刷新后重试')
    else:
        db.add(ResourceFavorite(resource_id=rid, user_id=user.id, active=favorited))
    try: db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, 40902, '收藏状态已变化，请刷新后重试') from None
    return ok({'favorited': favorited, 'revision': revision + 1})


@router.post('/{rid}/favorite')
def toggle_favorite(rid: int, user=Depends(get_current_user), db=Depends(get_db)):
    existing = db.scalar(select(ResourceFavorite).where(
        ResourceFavorite.resource_id == rid, ResourceFavorite.user_id == user.id))
    return _set_favorite(rid, not bool(existing and existing.active),
                         existing.revision if existing else 0, user, db)


@router.put('/{rid}/favorite')
def set_favorite(rid: int, body: FavoriteState, user=Depends(get_current_user), db=Depends(get_db)):
    return _set_favorite(rid, body.favorited, body.expected_revision, user, db)
