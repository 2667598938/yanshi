"""进程内临时状态（4 人版不依赖 Redis）：限流计数、验证码、登录锁定。

接口与 Redis 版保持一致，未来若需要可替换为 Redis 实现而不改业务代码。
"""
import hashlib
import secrets
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage

from ..errors import ApiError


class TransientStore:
    def __init__(self):
        self.data = {}
        self.lock = threading.RLock()

    def get(self, key):
        with self.lock:
            item = self.data.get(key)
            if not item or item[1] <= time.time():
                self.data.pop(key, None)
                return None
            return item[0]

    def set(self, key, value, ttl):
        with self.lock:
            self.data[key] = (str(value), time.time() + ttl)

    def consume(self, key):
        with self.lock:
            value = self.get(key)
            self.data.pop(key, None)
            return value

    def set_once(self, key, value, ttl):
        with self.lock:
            if self.get(key) is not None:
                return False
            self.set(key, value, ttl)
            return True

    def count(self, key, ttl):
        with self.lock:
            old = self.data.get(key)
            value = int(self.get(key) or 0) + 1
            self.data[key] = (str(value), old[1] if old and old[1] > time.time() else time.time() + ttl)
            return value

    def limit(self, key, maximum, ttl):
        if self.count(key, ttl) > maximum:
            raise ApiError(429, 42901, '操作过于频繁，请稍后再试')


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def deliver(settings, email, subject, text):
    """发送邮件：配置了 SMTP 则真发；开发环境写本地文件并（可选）打印到控制台。"""
    if settings.smtp_host:
        msg = EmailMessage()
        msg['From'] = settings.smtp_from or settings.smtp_user
        msg['To'] = email
        msg['Subject'] = subject
        msg.set_content(text)
        try:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port,
                                 timeout=10, context=ssl.create_default_context()) as smtp:
                if settings.smtp_user:
                    smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        except Exception:
            raise ApiError(502, 50201, '邮件暂时无法发送，请稍后重试') from None
    elif settings.environment in ('development', 'test'):
        settings.mail_directory.mkdir(parents=True, exist_ok=True)
        (settings.mail_directory / (secrets.token_hex(16) + '.txt')).write_text(
            f'To: {email}\nSubject: {subject}\n\n{text}', encoding='utf-8')
        if settings.mail_console:
            print(f'\n================ 邮件（开发模式）================\n'
                  f'收件人: {email}\n{text}\n================================================')
    else:
        raise ApiError(502, 50201, '邮件服务未配置')
