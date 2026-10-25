"""腾讯云短信 SendSms (2021-01-11)，TC3签名；仅开发环境允许控制台适配。"""
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
import httpx
from ..errors import ApiError


def tencent_headers(settings, payload, timestamp):
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d')
    host, content_type = 'sms.tencentcloudapi.com', 'application/json; charset=utf-8'
    signed = 'content-type;host'
    canonical = '\n'.join(('POST', '/', '', f'content-type:{content_type}\nhost:{host}\n', signed,
                           hashlib.sha256(payload).hexdigest()))
    scope = f'{date}/sms/tc3_request'
    to_sign = '\n'.join(('TC3-HMAC-SHA256', str(timestamp), scope, hashlib.sha256(canonical.encode()).hexdigest()))
    def sign(key, message): return hmac.new(key, message.encode(), hashlib.sha256).digest()
    key = sign(sign(sign(('TC3' + settings.sms_secret_key).encode(), date), 'sms'), 'tc3_request')
    signature = hmac.new(key, to_sign.encode(), hashlib.sha256).hexdigest()
    return {'Authorization': f'TC3-HMAC-SHA256 Credential={settings.sms_secret_id}/{scope}, SignedHeaders={signed}, Signature={signature}',
        'Content-Type': content_type, 'Host': host, 'X-TC-Action': 'SendSms',
        'X-TC-Version': '2021-01-11', 'X-TC-Region': settings.sms_region, 'X-TC-Timestamp': str(timestamp)}


def send_sms(settings, phone, code):
    if not settings.sms_provider or settings.sms_provider == 'console':
        if settings.environment == 'production': raise ApiError(503, 50301, '短信服务尚未配置')
        print(f'[SMS] {phone}: 登录验证码 {code}，5分钟内有效')
        return
    if settings.sms_provider != 'tencent': raise ApiError(503, 50301, '不支持的短信服务商配置')
    if not all((settings.sms_secret_id, settings.sms_secret_key, settings.sms_sdk_app_id,
                settings.sms_sign_name, settings.sms_template_id)):
        raise ApiError(503, 50301, '腾讯云短信配置不完整')
    number = phone if phone.startswith('+') else '+86' + phone
    payload = json.dumps({'PhoneNumberSet': [number], 'SmsSdkAppId': settings.sms_sdk_app_id,
        'SignName': settings.sms_sign_name, 'TemplateId': settings.sms_template_id,
        'TemplateParamSet': [code]}, ensure_ascii=False, separators=(',', ':')).encode()
    try:
        response = httpx.post('https://sms.tencentcloudapi.com/', content=payload,
            headers=tencent_headers(settings, payload, int(time.time())), timeout=15, trust_env=False)
        data = response.json().get('Response', {})
        statuses = data.get('SendStatusSet', [])
        if response.status_code != 200 or data.get('Error') or len(statuses) != 1 or statuses[0].get('Code') != 'Ok':
            raise ApiError(502, 50201, '短信发送失败，请稍后重试或使用邮箱登录')
    except (httpx.HTTPError, ValueError, AttributeError, TypeError):
        raise ApiError(502, 50201, '短信服务连接失败，请稍后重试') from None
