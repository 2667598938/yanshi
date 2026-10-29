from contextlib import contextmanager
from sqlalchemy import select
from ..models import User
from ..database import begin_development_transaction


@contextmanager
def account_write(db, uid):
    from .sync import sync_write_lock

    with sync_write_lock:
        if (
            db.get_bind().dialect.name == "sqlite"
            and not db.connection().connection.driver_connection.in_transaction
        ):
            begin_development_transaction(db)
        db.scalar(select(User).where(User.id == uid).with_for_update())
        try:
            yield
        except Exception:
            db.rollback()
            raise
