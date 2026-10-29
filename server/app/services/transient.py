"""验证码摘要与邮件投递工具。

共享临时状态由 persistent_transient.PersistentTransientStore 管理。
"""
import hashlib
import secrets
import smtplib
import ssl
from email.message import EmailMessage

from ..errors import ApiError


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
