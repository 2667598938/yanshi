"""生产环境AI出口仅允许管理员认可的HTTPS域名，防止BYOK被用于探测内网。"""
import ipaddress
from urllib.parse import urlsplit
from ..errors import ApiError

AI_HOSTS = {'api.deepseek.com', 'api.moonshot.cn', 'open.bigmodel.cn', 'api.siliconflow.cn',
            'api.openai.com', 'ark.cn-beijing.volces.com'}


def validate_ai_base(settings, base):
    try:
        url = urlsplit(base)
        if url.scheme not in ('https', 'http') or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError()
        port = url.port
    except ValueError:
        raise ApiError(400, 40001, 'AI服务地址格式无效') from None
    hostname = url.hostname.lower().rstrip('.')
    try: private = not ipaddress.ip_address(hostname).is_global
    except ValueError: private = hostname in ('localhost',) or hostname.endswith(('.localhost', '.local', '.internal'))
    if private and not (settings.environment != 'production' and settings.ai_allow_private_hosts):
        raise ApiError(400, 40001, 'AI服务地址不能指向本机或内网')
    if settings.environment == 'production':
        allowed = AI_HOSTS | {x.strip().lower() for x in settings.ai_custom_hosts.split(',') if x.strip()}
        if url.scheme != 'https' or port not in (None, 443) or hostname not in allowed:
            raise ApiError(400, 40001, '生产环境请使用已获管理员允许的HTTPS服务商地址')
    return base
