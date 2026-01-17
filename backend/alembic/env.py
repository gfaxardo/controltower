from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from urllib.parse import quote_plus

if settings.DATABASE_URL:
    database_url = settings.DATABASE_URL
else:
    db_user = quote_plus(settings.DB_USER) if settings.DB_USER else ''
    db_password = quote_plus(settings.DB_PASSWORD) if settings.DB_PASSWORD else ''
    database_url = f"postgresql://{db_user}:{db_password}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"

# Use attributes directly to avoid ConfigParser interpolation issues with special characters
config.attributes['sqlalchemy.url'] = database_url

target_metadata = None

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.attributes.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    url = config.attributes.get("sqlalchemy.url") or config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
