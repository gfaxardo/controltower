"""Módulo DB: conexión (psycopg2), engine SQLAlchemy y helpers."""
from app.db.connection import (
    get_db,
    init_db_pool,
    get_connection_info,
    log_connection_context,
)

__all__ = [
    "get_db",
    "init_db_pool",
    "get_engine",
    "get_database_url",
    "get_connection_info",
    "log_connection_context",
]


def get_database_url() -> str:
    """Retorna la URL de conexión desde settings."""
    from app.settings import settings
    return settings.database_url


def get_engine():
    """Retorna un engine de SQLAlchemy para la base de datos configurada."""
    from sqlalchemy import create_engine
    from app.settings import settings
    url = settings.database_url
    if not url or url == "postgresql://:":
        raise ValueError("DATABASE_URL o DB_* no configurados en .env")
    return create_engine(url, pool_pre_ping=True)
