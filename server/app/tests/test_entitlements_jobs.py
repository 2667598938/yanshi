from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy import select

from app.models import User, Message, EmailJob, FeatureRequest
from app.services.maintenance import deliver_email_jobs, enqueue_expiry_notifications
from app.services.messages import create_message
from app.services.features import is_vip
from app.tests.conftest import login
from app.tests.test_rooms import make_member, h, ADMIN
from app.time import utcnow


def setup_user(client):
    owner = h(login(client, **ADMIN)['access_token'])
    member = make_member(client, owner, 'entitlement@test.com', '权益同学')
    return owner, member, h(login(client, 'entitlement@test.com', 'Friend2028')['access_token'])


def test_permanent_and_explicit_expiry_vip(client):
    owner, member, headers = setup_user(client)
    url = f'/api/v1/admin/members/{member["id"]}'
    result = client.put(url, headers=owner, json={'vip_action': 'permanent', 'note': '开通永久会员权益'})
    assert result.status_code == 200, result.text
    assert result.json()['data']['vip_permanent'] is True
    status = client.get('/api/v1/vip/status', headers=headers).json()['data']
    assert status['is_vip'] and status['vip_permanent'] and status['days_left'] is None
    end = utcnow() + timedelta(days=5)
    result = client.put(url, headers=owner, json={'vip_action': 'set_expiry', 'vip_until': end.isoformat() + 'Z', 'note': '调整到期时间测试'})
    assert result.status_code == 200 and result.json()['data']['vip_permanent'] is False
    assert client.get('/api/v1/vip/status', headers=headers).json()['data']['is_vip']
    assert client.put(url, headers=owner, json={'vip_action': 'set_expiry', 'note': '缺少日期需要拒绝'}).status_code == 400


def test_same_code_race_only_one_user_can_redeem(client):
    owner, member, first = setup_user(client)
    make_member(client, owner, 'entitlement2@test.com', '权益乙')
    second = h(login(client, 'entitlement2@test.com', 'Friend2028')['access_token'])
    code = client.post('/api/v1/admin/invites', headers=owner, json={'vip_days': 30}).json()['data']['code']
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(lambda headers: client.post('/api/v1/vip/redeem', headers=headers,
            json={'code': code}).status_code, [first, second]))
    assert sorted(statuses) == [200, 400]
    assert sum(client.get('/api/v1/vip/status', headers=headers).json()['data']['is_vip'] for headers in [first, second]) == 1


def test_two_codes_same_user_extend_without_lost_update(client):
    owner, _member, headers = setup_user(client)
    codes = [client.post('/api/v1/admin/invites', headers=owner, json={'vip_days': 30}).json()['data']['code'] for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda code: client.post('/api/v1/vip/redeem', headers=headers, json={'code': code}).status_code, codes))
    assert results == [200, 200]
    assert client.get('/api/v1/vip/status', headers=headers).json()['data']['days_left'] >= 60


def test_email_jobs_are_transactional_retryable_and_admin_visible(client, monkeypatch):
    owner, member, _headers = setup_user(client)
    factory, settings = client.app.state.session_factory, client.app.state.settings
    with factory() as db:
        user = db.get(User, member['id'])
        create_message(db, user, 'system', '回滚邮件', '不能发送', email=True, settings=settings)
        db.rollback()
    with factory() as db:
        assert db.scalar(select(EmailJob)) is None
        user = db.get(User, member['id'])
        create_message(db, user, 'system', '测试重试', '可重试通知', email=True, settings=settings)
        db.commit()
    def fail(*args): raise RuntimeError('smtp down')
    monkeypatch.setattr('app.services.maintenance.deliver', fail)
    deliver_email_jobs(factory, settings)
    with factory() as db:
        job = db.scalar(select(EmailJob))
        assert job.status == 'retry' and job.attempts == 1 and job.sent_at is None
        job.status, job.attempts = 'failed', 5
        job_id = job.id
        db.commit()
    assert client.post(f'/api/v1/admin/email-jobs/{job_id}/retry', headers=owner).status_code == 200
    sent = []
    monkeypatch.setattr('app.services.maintenance.deliver', lambda *args: sent.append(args[1]))
    deliver_email_jobs(factory, settings)
    assert sent == ['entitlement@test.com']
    assert client.get('/api/v1/admin/email-jobs?status=sent', headers=owner).json()['data'][0]['status'] == 'sent'
    assert client.post(f'/api/v1/admin/email-jobs/{job_id}/retry', headers=owner).status_code == 409


def test_expiry_notice_once_and_vip_auto_approval_expires(client):
    owner, member, headers = setup_user(client)
    client.put(f'/api/v1/admin/members/{member["id"]}', headers=owner,
        json={'vip_action': 'grant', 'vip_days': 1, 'note': '到期任务验证会员'})
    result = client.post('/api/v1/requests', headers=headers, json={'feature': 'ai', 'reason': '开通自动审批功能'})
    assert result.status_code == 200 and result.json()['data']['status'] == 'approved'
    with client.app.state.session_factory() as db:
        user = db.get(User, member['id']); user.vip_until = utcnow() - timedelta(seconds=1); db.commit()
        assert not is_vip(user)
    for _ in range(2): enqueue_expiry_notifications(client.app.state.session_factory, client.app.state.settings)
    with client.app.state.session_factory() as db:
        notices = db.scalars(select(Message).where(Message.title == 'VIP 已到期')).all()
        assert len(notices) == 1
        request = db.get(FeatureRequest, result.json()['data']['id'])
        assert request.status == 'revoked' and request.active_key is None
    assert client.post('/api/v1/requests', headers=headers,
        json={'feature': 'ai', 'reason': '到期后重新申请授权'}).status_code == 200


def test_rejection_requires_reason_and_concurrent_review_only_once(client):
    owner, _member, headers = setup_user(client)
    rid = client.post('/api/v1/requests', headers=headers,
        json={'feature': 'ai', 'reason': '需要使用学习助教'}).json()['data']['id']
    url = f'/api/v1/admin/requests/{rid}/review'
    assert client.post(url, headers=owner, json={'action': 'reject', 'note': '太短'}).status_code == 400
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(url, headers=owner,
            json={'action': 'approve', 'note': ''}).status_code, [1, 2]))
    assert sorted(results) == [200, 400]
