"""励志区「大雪深埋」：用户投稿 + 管理员审核 + 通过后公开展示。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import select, update

from ..deps import audit, get_admin, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import Attachment, Inspiration, User
from ..schemas.community import InspirationInput, InspirationReview
from ..serializers import iso
from ..services.messages import create_message
from ..time import utcnow

router = APIRouter(prefix='/api/v1', tags=['inspiration'])

STATUS_LABEL = {'pending': '待审核', 'approved': '已通过', 'rejected': '已驳回'}


def item_dict(row, user=None, with_user=False):
    data = {
        'id': row.id, 'content': row.content, 'image_key': row.image_key or '',
        'status': row.status, 'status_label': STATUS_LABEL.get(row.status, row.status),
        'review_note': row.review_note or '',
        'created_at': iso(row.created_at),
        'reviewed_at': iso(row.reviewed_at),
    }
    if with_user and user:
        data['user'] = {'id': user.id, 'nickname': user.nickname}
    return data


@router.get('/inspirations')
def approved_inspirations(db=Depends(get_db)):
    rows = db.scalars(select(Inspiration).where(
        Inspiration.status == 'approved').order_by(Inspiration.id.desc()).limit(30)).all()
    return ok([item_dict(r) for r in rows])


@router.get('/inspirations/mine')
def my_inspirations(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(select(Inspiration).where(
        Inspiration.user_id == user.id).order_by(Inspiration.id.desc())).all()
    return ok([item_dict(r) for r in rows])


@router.post('/inspirations')
def submit_inspiration(body: InspirationInput, request: Request,
                       user=Depends(get_current_user), db=Depends(get_db)):
    pending = db.scalar(select(Inspiration.id).where(
        Inspiration.user_id == user.id, Inspiration.status == 'pending'))
    if pending:
        raise ApiError(409, 40901, '已有投稿在审核中，请等待结果')
    image_key = body.image_key.strip()
    if image_key:
        attachment = db.scalar(select(Attachment).where(
            Attachment.object_key == image_key,
            Attachment.uploader_id == user.id,
            Attachment.biz_type == 'inspiration',
            Attachment.deleted_at.is_(None)))
        if attachment is None:
            raise ApiError(400, 40001, '请使用本人上传的励志配图')
    row = Inspiration(user_id=user.id, content=body.content.strip(),
                      image_key=image_key, status='pending')
    db.add(row)
    audit(db, request, 'inspiration.submit', user_id=user.id)
    db.commit()
    db.refresh(row)
    return ok(item_dict(row))


@router.get('/admin/inspirations')
def admin_list(status: str = 'pending', db=Depends(get_db),
               _admin=Depends(get_admin)):
    query = select(Inspiration, User).join(User, Inspiration.user_id == User.id)
    if status != 'all':
        if status not in STATUS_LABEL:
            raise ApiError(400, 40001, '未知的审核状态')
        query = query.where(Inspiration.status == status)
    rows = db.execute(query.order_by(Inspiration.id.desc()).limit(100)).all()
    return ok([item_dict(r, u, with_user=True) for r, u in rows])


@router.post('/admin/inspirations/{iid}/review')
def review_inspiration(iid: int, body: InspirationReview, request: Request,
                       db=Depends(get_db), admin=Depends(get_admin)):
    row = db.get(Inspiration, iid)
    if not row:
        raise ApiError(404, 40401, '投稿不存在')
    if row.status != 'pending':
        raise ApiError(400, 40001, '该投稿已处理')
    if body.action == 'reject' and len(body.note.strip()) < 5:
        raise ApiError(400, 40001, '驳回原因至少5字')
    claimed = db.execute(update(Inspiration).where(Inspiration.id == iid,
        Inspiration.status == 'pending').values(
            status='approved' if body.action == 'approve' else 'rejected',
            review_note=body.note.strip(), reviewed_by=admin.id, reviewed_at=utcnow())).rowcount
    if claimed != 1:
        raise ApiError(400, 40001, '该投稿已被处理，请刷新')
    row.status = 'approved' if body.action == 'approve' else 'rejected'
    row.review_note = body.note.strip()
    row.reviewed_by = admin.id
    row.reviewed_at = utcnow()
    author = db.get(User, row.user_id)
    if row.status == 'approved':
        title = '励志投稿已通过'
        content = '你的投稿已通过审核，已加入「大雪深埋」轮播。'
    else:
        title = '励志投稿被驳回'
        content = f'你的投稿未通过审核。原因：{row.review_note or "未填写"}'
    create_message(db, author, 'content', title, content, link='/inspirations',
                   dedupe_key=f'inspiration:{iid}', email=True,
                   settings=request.app.state.settings)
    audit(db, request, 'admin.review_inspiration', user_id=row.user_id,
          detail=f'{iid} {row.status}')
    db.commit()
    return ok(item_dict(row, author, with_user=True))
