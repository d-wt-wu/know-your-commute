from logging.config import fileConfig

from alembic import context

from commute.db.connection import database_engine
from commute.db.schema import metadata

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def run_migrations_online():
    # Tests may supply an explicit connection. CLI always reads DATABASE_URL.
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = database_engine(purpose="writer")
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Use an explicit PostgreSQL connection to apply or inspect migrations.")
else:
    run_migrations_online()
