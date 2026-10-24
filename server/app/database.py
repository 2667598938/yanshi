from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def begin_development_transaction(db):
    """SQLite 没有行锁，显式 BEGIN IMMEDIATE 串行化写事务，避免同步并发写冲突。"""
    if db.get_bind().dialect.name == 'sqlite':
        db.connection().exec_driver_sql('BEGIN IMMEDIATE')


def make_database(url):
    sqlite = url.startswith('sqlite:')
    if sqlite and ':memory:' not in url:
        Path(url.removeprefix('sqlite:///')).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={'check_same_thread': False, 'timeout': 15} if sqlite else {},
    )
    if sqlite:
        @event.listens_for(engine, 'connect')
        def configure(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA journal_mode=WAL')
    sessions = sessionmaker(engine, expire_on_commit=False)
    return engine, sessions
