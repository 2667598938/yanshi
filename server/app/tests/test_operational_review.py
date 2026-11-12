import json
import logging
from datetime import datetime
from unittest.mock import Mock

from sqlalchemy import select

from app.config import Settings
from app.models import EmailJob, LearningRecord, Message, User
from app.services.maintenance import enqueue_daily_reminders


def test_public_registration_defaults_and_capacity(client):
    defaults = Settings(_env_file=None)
    assert defaults.auth_email_domains == ''
    assert not defaults.auth_qq_numeric_only
    assert defaults.account_max_users == 300
    settings = client.app.state.settings
    settings.account_max_users = 1
    response = client.get('/api/v1/config/public')
    assert response.json()['data']['registration_slots'] == 0
    assert len(response.headers['x-request-id']) == 32
    settings.account_max_users = 300
    assert client.get('/api/v1/config/public').json()['data']['registration_slots'] == 299


def test_production_video_rooms_require_turn():
    settings = Settings(_env_file=None, environment='production', features='text_room,av_room')
    assert settings.enabled_features == ['text_room']
    settings.room_turn_urls = 'turn:relay.example.test:3478'
    assert settings.enabled_features == ['text_room']
    settings.room_turn_secret = 'fixture-secret'
    assert settings.enabled_features == ['text_room', 'av_room']


def test_csp_report_records_directive_without_private_fields(client, monkeypatch):
    endpoint = '/api/v1/csp-report'
    log = Mock()
    monkeypatch.setattr(logging.getLogger('uvicorn.error'), 'info', log)
    response = client.post(endpoint, headers={'Content-Type': 'application/csp-report'}, json={
        'csp-report': {'effective-directive': 'script-src-elem', 'document-uri': 'https://example.test/private-fixture'},
    })
    assert response.status_code == 204
    entries = [json.loads(call.args[0]) for call in log.call_args_list]
    assert {'event': 'csp_report', 'directive': 'script-src-elem'} in entries
    assert 'private-fixture' not in json.dumps(entries)
    assert client.post(endpoint, json={}).status_code == 415
    assert client.post(endpoint, headers={'Content-Type': 'application/csp-report'}, content=b'x' * 8193).status_code == 413


def test_daily_reminders_are_opt_in_and_idempotent(client, monkeypatch):
    settings = client.app.state.settings
    settings.smtp_host = 'smtp.example.test'
    settings.smtp_user = 'sender@example.test'
    settings.smtp_password = 'fixture-only'
    sessions = client.app.state.session_factory
    with sessions() as db:
        for index, opted_in in enumerate((True, False)):
            user = User(email=f'reminder-{index}@example.test', nickname='提醒', password_hash='fixture')
            db.add(user)
            db.flush()
            db.add(LearningRecord(user_id=user.id, id='learning-settings',
                body=json.dumps({'value': {'dailyReminder': opted_in}})))
        db.commit()
    monkeypatch.setattr('app.services.maintenance.utcnow', lambda: datetime(2026, 11, 12, 12))
    enqueue_daily_reminders(sessions, settings)
    enqueue_daily_reminders(sessions, settings)
    with sessions() as db:
        messages = db.scalars(select(Message).where(Message.kind == 'study')).all()
        jobs = db.scalars(select(EmailJob)).all()
        assert len(messages) == len(jobs) == 1
        assert jobs[0].recipient == 'reminder-0@example.test'
