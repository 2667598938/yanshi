"""共享数据库中的验证码、限流和一次性票据；重启/多进程仍保持原子消费。"""
import threading
import time
import secrets
from contextlib import contextmanager
from sqlalchemy import select
from ..database import begin_development_transaction
from ..models import TransientState
from ..errors import ApiError
from . import ai_key


class PersistentTransientStore:
    def __init__(self, session_factory, secret):
        self.sessions, self.secret, self.lock = session_factory, secret, threading.RLock()

    @contextmanager
    def transaction(self):
        with self.lock, self.sessions() as db:
            begin_development_transaction(db)
            if db.get_bind().dialect.name != 'sqlite':
                from sqlalchemy import update
                from ..models import User
                db.execute(update(User).where(User.role == 'admin').values(token_version=User.token_version))
            try:
                yield db
                db.commit()
            except Exception:
                db.rollback()
                raise

    def _row(self, db, key):
        return db.scalar(select(TransientState).where(TransientState.state_key == key).with_for_update())

    def _get(self, db, key):
        row = self._row(db, key)
        if not row or row.expires_at <= time.time(): return None
        return ai_key.decrypt(self.secret, row.value_cipher, key)

    def _set(self, db, key, value, ttl):
        row = self._row(db, key)
        if row is None:
            row = TransientState(state_key=key); db.add(row)
        row.value_cipher = ai_key.encrypt(self.secret, str(value), key)
        row.expires_at = time.time() + ttl
        db.flush()

    def get(self, key):
        with self.transaction() as db: return self._get(db, key)

    def set(self, key, value, ttl):
        with self.transaction() as db: self._set(db, key, value, ttl)

    def consume(self, key):
        with self.transaction() as db:
            value = self._get(db, key)
            row = self._row(db, key)
            if row: db.delete(row)
            return value

    def set_once(self, key, value, ttl):
        with self.transaction() as db:
            if self._get(db, key) is not None: return False
            self._set(db, key, value, ttl)
            return True

    def count(self, key, ttl):
        with self.transaction() as db:
            row = self._row(db, key)
            value = int(self._get(db, key) or 0) + 1
            remaining = row.expires_at - time.time() if row and row.expires_at > time.time() else ttl
            self._set(db, key, value, remaining)
            return value

    def limit(self, key, maximum, ttl):
        if self.count(key, ttl) > maximum: raise ApiError(429, 42901, '操作过于频繁，请稍后再试')

    def verify(self, key, value_digest, max_attempts=5):
        with self.transaction() as db:
            stored = self._get(db, key)
            if not stored: return False
            attempts_key = key + ':attempts'
            valid = secrets.compare_digest(stored, value_digest)
            attempts = int(self._get(db, attempts_key) or 0) + 1
            if valid or attempts >= max_attempts:
                for entry in (key, attempts_key):
                    row = self._row(db, entry)
                    if row: db.delete(row)
            else: self._set(db, attempts_key, attempts, 300)
            return valid
