"""动态帖子与二级评论。"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from ..deps import audit, get_current_user, get_db
from ..errors import ApiError, ok
from ..models import Comment, Post, User
from ..schemas.community import CommentInput, PostInput
from ..serializers import iso
from ..services.messages import create_message
from ..time import utcnow

router = APIRouter(prefix='/api/v1', tags=['community'])


def author_dict(user):
    if not user:
        return None
    return {'id': user.id, 'nickname': user.nickname, 'avatar_key': user.avatar_key or ''}


def post_dict(row, author, comment_count, current_user):
    return {
        'id': row.id, 'content': row.content,
        'author': author_dict(author),
        'comment_count': int(comment_count),
        'mine': row.user_id == current_user.id,
        'can_delete': row.user_id == current_user.id or current_user.role == 'admin',
        'created_at': iso(row.created_at),
    }


def comment_dict(row, author, reply_to, post, current_user):
    can_delete = (row.user_id == current_user.id or post.user_id == current_user.id
                  or current_user.role == 'admin')
    return {
        'id': row.id, 'parent_id': row.parent_id,
        'reply_to': reply_to.nickname if reply_to else '',
        'author': author_dict(author),
        'content': row.content,
        'mine': row.user_id == current_user.id,
        'can_delete': can_delete,
        'created_at': iso(row.created_at),
    }


def _comment_counts(db, ids):
    if not ids:
        return {}
    rows = db.execute(
        select(Comment.post_id, func.count()).where(
            Comment.post_id.in_(ids), Comment.deleted_at.is_(None)
        ).group_by(Comment.post_id)).all()
    return {pid: int(n) for pid, n in rows}


@router.get('/posts')
def list_posts(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(select(Post).where(
        Post.deleted_at.is_(None)).order_by(Post.id.desc()).limit(50)).all()
    authors = {u.id: u for u in db.scalars(select(User).where(
        User.id.in_([r.user_id for r in rows]))).all()}
    counts = _comment_counts(db, [r.id for r in rows])
    return ok([post_dict(r, authors.get(r.user_id), counts.get(r.id, 0), user) for r in rows])


@router.get('/posts/mine')
def my_posts(user=Depends(get_current_user), db=Depends(get_db)):
    rows = db.scalars(select(Post).where(
        Post.user_id == user.id, Post.deleted_at.is_(None)
    ).order_by(Post.id.desc()).limit(50)).all()
    counts = _comment_counts(db, [r.id for r in rows])
    return ok([post_dict(r, user, counts.get(r.id, 0), user) for r in rows])


@router.get('/posts/{pid}')
def get_post(pid: int, user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(Post, pid)
    if not row or row.deleted_at:
        raise ApiError(404, 40401, '帖子不存在或已删除')
    author = db.get(User, row.user_id)
    counts = _comment_counts(db, [pid])
    return ok(post_dict(row, author, counts.get(pid, 0), user))


@router.post('/posts')
def create_post(body: PostInput, request: Request, user=Depends(get_current_user),
                db=Depends(get_db)):
    if body.client_id:
        existing = db.scalar(select(Post).where(
            Post.user_id == user.id, Post.client_id == body.client_id,
            Post.deleted_at.is_(None)))
        if existing:
            counts = _comment_counts(db, [existing.id])
            return ok(post_dict(existing, user, counts.get(existing.id, 0), user))
    row = Post(user_id=user.id, content=body.content.strip(), client_id=body.client_id or None)
    db.add(row)
    audit(db, request, 'post.create', user_id=user.id)
    try:
        db.commit()
    except IntegrityError:
        # 并发重试：同一 client_id 已存在时直接返回已落库帖子
        db.rollback()
        existing = db.scalar(select(Post).where(
            Post.user_id == user.id, Post.client_id == body.client_id))
        if not existing:
            raise
        counts = _comment_counts(db, [existing.id])
        return ok(post_dict(existing, user, counts.get(existing.id, 0), user))
    db.refresh(row)
    return ok(post_dict(row, user, 0, user))


@router.delete('/posts/{pid}')
def delete_post(pid: int, request: Request, reason: str = '',
                user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(Post, pid)
    if not row or row.deleted_at:
        raise ApiError(404, 40401, '帖子不存在')
    is_owner = row.user_id == user.id
    if not is_owner and user.role != 'admin':
        raise ApiError(403, 40301, '只能删除自己的帖子')
    row.deleted_at = utcnow()
    db.execute(update(Comment).where(Comment.post_id == pid).values(deleted_at=utcnow()))
    if not is_owner:
        author = db.get(User, row.user_id)
        if author:
            create_message(db, author, 'content', '帖子已被管理员删除',
                           '你的帖子因违规被删除。' + (f'原因：{reason}' if reason else ''),
                           link='/posts')
    audit(db, request, 'post.delete', user_id=user.id, detail=str(pid))
    db.commit()
    return ok()


@router.get('/posts/{pid}/comments')
def list_comments(pid: int, user=Depends(get_current_user), db=Depends(get_db)):
    post = db.get(Post, pid)
    if not post or post.deleted_at:
        raise ApiError(404, 40401, '帖子不存在')
    rows = db.scalars(select(Comment).where(
        Comment.post_id == pid, Comment.deleted_at.is_(None)
    ).order_by(Comment.id)).all()
    users = {u.id: u for u in db.scalars(select(User).where(
        User.id.in_({r.user_id for r in rows} | {r.reply_to_user_id for r in rows
                                                   if r.reply_to_user_id}))).all()}
    return ok([comment_dict(r, users.get(r.user_id),
                            users.get(r.reply_to_user_id), post, user) for r in rows])


@router.post('/posts/{pid}/comments')
def create_comment(pid: int, body: CommentInput, request: Request,
                   user=Depends(get_current_user), db=Depends(get_db)):
    post = db.get(Post, pid)
    if not post or post.deleted_at:
        raise ApiError(404, 40401, '帖子不存在')
    parent_id = None
    reply_to = None
    if body.parent_id:
        parent = db.get(Comment, body.parent_id)
        if not parent or parent.post_id != pid or parent.deleted_at:
            raise ApiError(404, 40401, '回复的评论不存在')
        # 最多二级：对二级评论的回复仍挂到其父评论下
        parent_id = parent.parent_id or parent.id
        reply_to = parent.user_id
    row = Comment(post_id=pid, user_id=user.id, parent_id=parent_id,
                  reply_to_user_id=reply_to, content=body.content.strip())
    db.add(row)
    audit(db, request, 'comment.create', user_id=user.id, detail=str(pid))
    db.commit()
    db.refresh(row)
    reply_user = db.get(User, reply_to) if reply_to else None
    return ok(comment_dict(row, user, reply_user, post, user))


@router.delete('/comments/{cid}')
def delete_comment(cid: int, request: Request, reason: str = '',
                   user=Depends(get_current_user), db=Depends(get_db)):
    row = db.get(Comment, cid)
    if not row or row.deleted_at:
        raise ApiError(404, 40401, '评论不存在')
    post = db.get(Post, row.post_id)
    is_owner = row.user_id == user.id
    can = is_owner or (post and post.user_id == user.id) or user.role == 'admin'
    if not can:
        raise ApiError(403, 40301, '无权删除该评论')
    row.deleted_at = utcnow()
    if row.parent_id is None:
        db.execute(update(Comment).where(
            Comment.post_id == row.post_id, Comment.parent_id == row.id
        ).values(deleted_at=utcnow()))
    if user.role == 'admin' and not is_owner:
        author = db.get(User, row.user_id)
        if author:
            create_message(db, author, 'content', '评论已被管理员删除',
                           '你的评论因违规被删除。' + (f'原因：{reason}' if reason else ''),
                           link=f'/posts/{row.post_id}')
    audit(db, request, 'comment.delete', user_id=user.id, detail=str(cid))
    db.commit()
    return ok()
