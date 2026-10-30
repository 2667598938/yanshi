import base64
import hashlib
import hmac
from app.config import Settings
from app.services.room_ice import ice_servers


def test_turn_secret_stays_server_side_and_credentials_expire(monkeypatch):
    monkeypatch.setattr('app.services.room_ice.time.time',lambda:10000)
    settings=Settings(_env_file=None,room_turn_urls='turn:relay.example:3478?transport=udp',room_turn_secret='test-only-secret',room_turn_ttl=600)
    data=ice_servers(settings,42)
    assert data[-1]['username']=='10600:42'
    expected=base64.b64encode(hmac.new(b'test-only-secret',b'10600:42',hashlib.sha1).digest()).decode()
    assert data[-1]['credential']==expected
    assert 'test-only-secret' not in str(data)


def test_unconfigured_turn_keeps_stun_only():
    assert ice_servers(Settings(_env_file=None),42)==[{'urls':'stun:stun.l.google.com:19302'}]
