"""Member-scoped short-lived TURN credentials; the shared server secret stays private."""
import base64
import hashlib
import hmac
import json
import time


def ice_servers(settings, user_id):
    servers = json.loads(settings.room_ice_servers)
    if not isinstance(servers, list):
        raise ValueError('Invalid ICE server configuration')
    urls = [url.strip() for url in settings.room_turn_urls.split(',') if url.strip()]
    if urls and settings.room_turn_secret:
        if any(not url.startswith(('turn:', 'turns:')) for url in urls):
            raise ValueError('Invalid TURN URL')
        username = f'{int(time.time()) + settings.room_turn_ttl}:{user_id}'
        credential = base64.b64encode(hmac.new(settings.room_turn_secret.encode(), username.encode(), hashlib.sha1).digest()).decode()
        servers.append({'urls': urls, 'username': username, 'credential': credential})
    return servers
