"""图片附件与院校库（v0.3-d）测试。"""
import json
from datetime import timedelta
from io import BytesIO

from PIL import Image
from sqlalchemy import select

from app.models import Attachment, LearningRecord, User
from app.tests.conftest import login, read_latest_code
from app.time import utcnow

ADMIN = {'email': 'admin@test.com', 'password': 'Admin2028'}


def ah(token):
    return {'Authorization': 'Bearer ' + token}


def register_friend(client, headers, email, name):
    invite = client.post('/api/v1/admin/invites', json={'remark': 'x'}, headers=headers).json()['data']['code']
    client.post('/api/v1/auth/email-code', json={'email': email, 'scene': 'register'})
    code = read_latest_code(client.app.state.settings.mail_directory)
    r = client.post('/api/v1/auth/register', json={
        'email': email, 'code': code, 'password': 'Friend2028', 'nickname': name,
        'invite_code': invite, 'accepted_terms': True})
    assert r.status_code == 200, r.text
    return ah(r.json()['data']['access_token'])


def jpeg_bytes(size=(800, 600), color=(120, 30, 40)):
    buf = BytesIO()
    Image.new('RGB', size, color).save(buf, 'JPEG', quality=90)
    buf.seek(0)
    return buf


def upload(client, url, headers, biz=None):
    files = {'file': ('a.jpg', jpeg_bytes(), 'image/jpeg')}
    if biz:
        url += '?biz=' + biz
    return client.post(url, headers=headers, files=files)


def test_orphan_reclaim_keeps_referenced_images_and_frees_quota(client):
    admin = login(client, **ADMIN)
    a = ah(admin['access_token'])
    f = register_friend(client, a, 'img-reclaim@test.com', '空间同学')
    used = upload(client, '/api/v1/attachments/image', f, biz='mistake').json()['data']['key']
    orphan = upload(client, '/api/v1/attachments/image', f, biz='mistake').json()['data']['key']
    with client.app.state.session_factory() as db:
        uid = db.scalar(select(User.id).where(User.email == 'img-reclaim@test.com'))
        db.add(LearningRecord(user_id=uid, id='mk-used', body=json.dumps({
            'type': 'mistake', 'content': '题目', 'images': [used], 'answerImages': [],
        }, ensure_ascii=False), revision=1, deleted=0, updated_at=utcnow()))
        for row in db.scalars(select(Attachment).where(
                Attachment.uploader_id == uid)).all():
            row.created_at = utcnow() - timedelta(hours=25)
        db.commit()

    summary = client.get('/api/v1/attachments/storage', headers=f).json()['data']
    assert summary['orphan_count'] == 1
    assert summary['orphan_bytes'] > 0
    reclaimed = client.post('/api/v1/attachments/reclaim', headers=f).json()['data']
    assert reclaimed['deleted'] == 1 and reclaimed['freed_bytes'] > 0

    assert client.get('/api/v1/attachments/view', params={'key': used}, headers=f).status_code == 200
    assert client.get('/api/v1/attachments/view', params={'key': orphan}, headers=f).status_code == 404
    assert client.get('/api/v1/attachments/storage', headers=f).json()['data']['orphan_count'] == 0


def test_avatar_upload_and_view_permission(client):
    admin = login(client, **ADMIN)
    a = ah(admin['access_token'])
    f = register_friend(client, a, 'img1@test.com', '图片同学')

    r = upload(client, '/api/v1/attachments/avatar', f)
    assert r.status_code == 200, r.text
    data = r.json()['data']
    assert data['width'] == 512 and data['height'] == 512
    assert data['key'].startswith('avatar/')
    key = data['key']

    # 本人可看
    mine = client.get('/api/v1/attachments/view', params={'key': key}, headers=f)
    assert mine.status_code == 200
    assert mine.headers['content-type'].startswith('image/jpeg')
    # 头像对其他成员可见
    other = client.get('/api/v1/attachments/view', params={'key': key}, headers=a)
    assert other.status_code == 200


def test_mistake_image_only_owner(client):
    admin = login(client, **ADMIN)
    a = ah(admin['access_token'])
    f = register_friend(client, a, 'img2@test.com', '错题同学')

    r = upload(client, '/api/v1/attachments/image', f, biz='mistake')
    assert r.status_code == 200, r.text
    key = r.json()['data']['key']
    assert key.startswith('mistake/')

    assert client.get('/api/v1/attachments/view', params={'key': key}, headers=f).status_code == 200
    # 错题图对其他普通成员不可见
    g = register_friend(client, a, 'img2b@test.com', '旁观同学')
    assert client.get('/api/v1/attachments/view', params={'key': key}, headers=g).status_code == 404


def test_reject_non_image(client):
    admin = login(client, **ADMIN)
    f = register_friend(client, ah(admin['access_token']), 'img3@test.com', '坏图同学')
    files = {'file': ('a.jpg', BytesIO(b'not an image at all'), 'image/jpeg')}
    r = client.post('/api/v1/attachments/image?biz=mistake', headers=f, files=files)
    assert r.status_code == 400


def test_school_library_and_admin(client):
    admin = login(client, **ADMIN)
    a = ah(admin['access_token'])
    f = register_friend(client, a, 'img4@test.com', '择校同学')

    rows = client.get('/api/v1/schools', headers=f).json()['data']
    assert len(rows) == 7
    assert {s['key'] for s in rows} == {'tsinghua', 'pku', 'nju', 'fudan', 'sjtu', 'ustc', 'zju'}
    fudan = client.get('/api/v1/schools/fudan', headers=f).json()['data']
    assert fudan['name'] == '复旦大学'

    # 普通成员可维护自己的梦校，管理员的同名院校保持独立
    r = client.post('/api/v1/schools', headers=f,
                    json={'key': 'xjtu', 'name': '西安交通大学'})
    assert r.status_code == 200

    # 管理员新增自己的自定义院校
    r = client.post('/api/v1/admin/schools', headers=a,
                    json={'key': 'xjtu', 'name': '西安交通大学', 'short': '西交',
                          'info': {'cutoff': ''}})
    assert r.status_code == 200, r.text
    rows = client.get('/api/v1/schools', headers=f).json()['data']
    assert len(rows) == 8


def test_school_image_not_visible_to_others(client):
    """院校相册图片与错题图一样：仅上传者本人可见，其他成员 view 返回 404。"""
    admin = login(client, **ADMIN)
    a = ah(admin['access_token'])
    f = register_friend(client, a, 'sc1@test.com', '校图同学')

    r = upload(client, '/api/v1/attachments/image', f, biz='school')
    assert r.status_code == 200, r.text
    key = r.json()['data']['key']
    assert key.startswith('school/')

    assert client.get('/api/v1/attachments/view', params={'key': key}, headers=f).status_code == 200
    g = register_friend(client, a, 'sc2@test.com', '旁观同学')
    assert client.get('/api/v1/attachments/view', params={'key': key}, headers=g).status_code == 404


def test_cannot_delete_others_image(client):
    """成员 A 上传的图片，成员 B 删除 -> 404（不暴露归属），管理员可删。"""
    admin = login(client, **ADMIN)
    a = ah(admin['access_token'])
    f = register_friend(client, a, 'del1@test.com', '传图同学')
    g = register_friend(client, a, 'del2@test.com', '删图同学')

    r = upload(client, '/api/v1/attachments/image', f, biz='mistake')
    assert r.status_code == 200, r.text
    key = r.json()['data']['key']

    # B 删 A 的图 -> 404
    assert client.delete('/api/v1/attachments', params={'key': key}, headers=g).status_code == 404
    # 本人删除成功
    assert client.delete('/api/v1/attachments', params={'key': key}, headers=f).status_code == 200
