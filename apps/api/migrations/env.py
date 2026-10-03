from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from f01.config import get_settings
from f01.db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata


def run_migrations() -> None:
    # Tests supply a dedicated connection; production credentials never enter INI files.
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(
            connection=connection, target_metadata=target_metadata, compare_type=True
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    url = get_settings().database_url
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(
        url, poolclass=pool.NullPool, hide_parameters=True, echo=False
    )
    try:
        with engine.connect() as bind:
            context.configure(
                connection=bind, target_metadata=target_metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
