"""用户 AI Key 加密：AES-256-GCM，密文含随机 nonce，AAD 绑定用户 ID。"""
import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _key(secret: str) -> bytes:
    return hashlib.sha256((secret or '').encode('utf-8')).digest()


def encrypt(secret: str, plaintext: str, aad: str) -> str:
    nonce = os.urandom(12)
    cipher = AESGCM(_key(secret))
    data = cipher.encrypt(nonce, plaintext.encode('utf-8'), aad.encode('utf-8'))
    return base64.b64encode(nonce + data).decode('ascii')


def decrypt(secret: str, cipher_text: str, aad: str) -> str:
    raw = base64.b64decode(cipher_text.encode('ascii'))
    nonce, data = raw[:12], raw[12:]
    return AESGCM(_key(secret)).decrypt(nonce, data, aad.encode('utf-8')).decode('utf-8')


def mask(key: str) -> str:
    key = (key or '').strip()
    if len(key) <= 8:
        return '••••••'
    return key[:3] + '...' + key[-4:]
