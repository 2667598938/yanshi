from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import Settings
from app.database import Base
import app.models  # noqa: F401  确保所有模型已注册到 metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = Settings()
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.database_url, target_metadata=target_metadata,
        render_as_batch=True, compare_type=True, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            render_as_batch=True, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
