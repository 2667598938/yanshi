import uuid
import time

import pytest

from app.tests.test_sync import headers, send


def write(client, headers, kind, value, revision=0):
    rid = 'learning-settings' if kind == 'preferences' else 'profile'
    record = {'id': rid, 'key': rid, 'type': kind, 'value': value}
    return send(client, headers, uuid.uuid4().hex, [{'id': rid, 'expectedRevision': revision, 'record': record}])


def test_profile_sync_updates_only_editable_fields_and_is_versioned(client):
    h = headers(client)
    result = write(client, h, 'profile', {'nickname': '同步昵称', 'privacy_mode': True})
    assert result.status_code == 200, result.text
    user = client.get('/api/v1/auth/me', headers=h)
    assert user.json()['data']['nickname'] == '同步昵称'
    assert user.json()['data']['privacy_mode'] is False  # 隐私只能由在线账号接口修改
    assert write(client, h, 'profile', {'nickname': '旧版本'}).status_code == 409


@pytest.mark.parametrize('kind,value', [
    ('profile', {'role': 'admin'}), ('profile', {'vip_until': '2099-01-01'}),
    ('preferences', {'longBreakEvery': 9}), ('preferences', {'focusMin': 4}),
    ('preferences', {'apiKey': 'secret'}),
])
def test_preferences_rejects_privilege_fields_and_bad_ranges(client, kind, value):
    h = headers(client)
    assert write(client, h, kind, value).status_code == 400


def test_learning_preferences_defaults_and_long_break_boundary(client):
    h = headers(client)
    response = write(client, h, 'preferences', {'longBreakEvery': 8})
    assert response.status_code == 200, response.text
    saved = response.json()['data']['changed'][0]['record']['value']
    assert saved == {'focusMin': 25, 'shortBreakMin': 5, 'longBreakMin': 15, 'longBreakEvery': 8}


def test_email_three_requests_per_five_minutes(client, monkeypatch):
    now = time.time()
    monkeypatch.setattr('app.services.persistent_transient.time.time', lambda: now)
    for index in range(3):
        now += 61
        result = client.post('/api/v1/auth/email-code', json={'email': 'window@test.com', 'scene': 'login'})
        assert result.status_code == 200, result.text
    now += 61
    assert client.post('/api/v1/auth/email-code', json={'email': 'window@test.com', 'scene': 'login'}).status_code == 429


def test_qq_numeric_policy_is_configurable(client):
    client.app.state.settings.auth_email_domains = 'qq.com'
    assert client.post('/api/v1/auth/email-code', json={'email': 'alias@qq.com', 'scene': 'login'}).status_code == 400
    assert client.post('/api/v1/auth/email-code', json={'email': '12345678@qq.com', 'scene': 'login'}).status_code == 200
    client.app.state.settings.auth_qq_numeric_only = False
    assert client.post('/api/v1/auth/email-code', json={'email': 'alias@qq.com', 'scene': 'login'}).status_code == 200
