from app.tests.test_community import ADMIN, h, make_member
from app.tests.conftest import login


def test_post_revision_replay_conflict_and_deleted_mirror(client):
    ah = h(login(client, **ADMIN)['access_token'])
    make_member(client, ah, 'writer@test.com', 'writer')
    own = h(login(client, 'writer@test.com', 'Friend2028')['access_token'])
    post = client.post('/api/v1/posts', headers=own,
        json={'content': 'original', 'client_id': 'client-post-001'}).json()['data']
    pid = post['id']
    payload = {'content': 'edited', 'expected_revision': 1}
    assert client.put(f'/api/v1/posts/{pid}', headers=ah, json=payload).status_code == 403
    assert client.put(f'/api/v1/posts/{pid}', headers=own, json=payload).json()['data']['revision'] == 2
    assert client.put(f'/api/v1/posts/{pid}', headers=own, json=payload).json()['data']['revision'] == 2
    r = client.put(f'/api/v1/posts/{pid}', headers=own,
                   json={'content': 'other device stale', 'expected_revision': 1})
    assert r.status_code == 409 and r.json()['data']['current']['content'] == 'edited'
    assert client.delete(f'/api/v1/posts/{pid}', headers=own).status_code == 200
    mirror = client.get('/api/v1/posts/mirror', headers=own).json()['data']['items']
    assert mirror[0]['deleted_at'] and mirror[0]['content'] == '' and mirror[0]['revision'] == 3
    replay = client.post('/api/v1/posts', headers=own,
        json={'content': 'original', 'client_id': 'client-post-001'}).json()['data']
    assert replay['id'] == pid and replay['deleted_at']
    assert client.get('/api/v1/posts/mirror', headers=ah).json()['data']['items'] == []


def test_favorite_tombstone_conflict_and_full_mirror(client):
    ah = h(login(client, **ADMIN)['access_token'])
    client.put('/api/v1/admin/members/1', headers=ah,
               json={'vip_action': 'permanent', 'note': 'test permanent grant'})
    rid = client.post('/api/v1/resources', headers=ah, json={
        'title': 'study material', 'url': 'https://example.com/share/secret'}).json()['data']['id']
    url = f'/api/v1/resources/{rid}/favorite'
    for state, revision, expected in ((True, 1, 0), (False, 2, 1), (True, 3, 2)):
        result = client.put(url, headers=ah, json={'favorited': state, 'expected_revision': expected})
        assert result.status_code == 200 and result.json()['data']['revision'] == revision
    stale = client.put(url, headers=ah, json={'favorited': False, 'expected_revision': 1})
    assert stale.status_code == 409 and stale.json()['data']['current']['revision'] == 3
    assert client.put(url, headers=ah, json={'favorited': False, 'expected_revision': 3}).status_code == 200
    state = client.get('/api/v1/resources/favorite-mirror', headers=ah).json()['data']['items'][0]
    assert not state['favorited'] and state['revision'] == 4
    assert client.get('/api/v1/resources/favorites', headers=ah).json()['data'] == []


def test_direct_profile_changes_advance_sync_revision(client):
    ah = h(login(client, **ADMIN)['access_token'])
    assert client.put('/api/v1/users/me', headers=ah, json={'nickname': 'new profile'}).status_code == 200
    record = next(r for r in client.get('/api/v1/sync/records', headers=ah).json()['data']['records'] if r['id'] == 'profile')
    assert record['revision'] == 1 and record['record']['value']['nickname'] == 'new profile'
    client.put('/api/v1/admin/members/1', headers=ah, json={'nickname': 'admin edited'})
    stale = client.post('/api/v1/sync/commands', headers=ah, json={'operationId': 'stale-profile',
        'changes': [{'id': 'profile', 'expectedRevision': 1, 'record': record['record']}]})
    assert stale.status_code == 409
    assert client.get('/api/v1/auth/me', headers=ah).json()['data']['nickname'] == 'admin edited'
