import uuid

from app.tests.test_sync import headers, send, task


def test_incremental_cursor_includes_update_and_delete_and_idempotent_replay(client):
    h = headers(client)
    baseline = client.get('/api/v1/sync/records', headers=h).json()['data']
    assert baseline['cursor'] == 0
    changes = [{'id': 'cursor-task', 'expectedRevision': 0, 'record': task('cursor-task')}]
    operation = uuid.uuid4().hex
    assert send(client, h, operation, changes).status_code == 200
    first = client.get('/api/v1/sync/records?since=0', headers=h).json()['data']
    assert first['cursor'] > 0 and len(first['records']) == 1
    send(client, h, operation, changes)
    replay = client.get(f'/api/v1/sync/records?since={first["cursor"]}', headers=h).json()['data']
    assert replay['records'] == [] and replay['cursor'] == first['cursor']
    send(client, h, uuid.uuid4().hex, [{'id': 'cursor-task', 'expectedRevision': 1, 'record': None}])
    deleted = client.get(f'/api/v1/sync/records?since={first["cursor"]}', headers=h).json()['data']
    assert deleted['records'] == [{'id': 'cursor-task', 'record': None, 'revision': 2}]
    assert deleted['serverTime'] > 1700000000000


def test_cursor_ahead_of_restored_server_returns_full_snapshot(client):
    h = headers(client)
    send(client, h, uuid.uuid4().hex, [{'id': 'restored', 'expectedRevision': 0, 'record': task('restored')}])
    result = client.get('/api/v1/sync/records?since=999999', headers=h).json()['data']
    assert result['records'][0]['id'] == 'restored'
    assert client.get('/api/v1/sync/records?since=-1', headers=h).status_code == 400
