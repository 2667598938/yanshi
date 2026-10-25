from alembic.script import ScriptDirectory
from sqlalchemy import text
from ..config import BASE_DIR


def database_ready(engine):
    try:
        expected = ScriptDirectory(str(BASE_DIR / 'alembic')).get_current_head()
        with engine.connect() as connection:
            actual = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one_or_none()
        return bool(actual == expected)
    except Exception:
        return False
