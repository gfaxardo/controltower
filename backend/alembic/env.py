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

from urllib.parse import quote_plus, urlparse, urlunparse
import logging
import json

logger = logging.getLogger(__name__)

def _dbg_log(msg: str, data: dict, hyp: str = ""):
    try:
        p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "debug-7a8d73.log")
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps({"sessionId":"7a8d73","message":msg,"data":data,"hypothesisId":hyp,"timestamp":__import__("time").time()*1000}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _url_ascii_safe(url: str) -> str:
    """Reconstruye la URL con user/password en percent-encoding (solo ASCII) para psycopg2 en Windows."""
    def force_ascii(s: str) -> str:
        """Convierte cualquier str a solo ASCII (percent-encoding UTF-8)."""
        out = []
        for c in s:
            if ord(c) < 128:
                out.append(c)
            else:
                for b in c.encode("utf-8"):
                    out.append(f"%{b:02X}")
        return "".join(out)

    try:
        if isinstance(url, bytes):
            try:
                url = url.decode("utf-8")
            except UnicodeDecodeError:
                url = url.decode("latin-1", errors="replace")
        p = urlparse(url)
        if not p.hostname:
            return force_ascii(url)
        user = quote_plus(p.username or "", safe="") if p.username else ""
        password = quote_plus(p.password or "", safe="") if p.password else ""
        netloc = f"{user}:{password}@{p.hostname}" + (f":{p.port}" if p.port else "")
        result = urlunparse((p.scheme, netloc, p.path or "", p.params, p.query, p.fragment))
        return force_ascii(result) if any(ord(c) > 127 for c in result) else result
    except Exception:
        return force_ascii(str(url))

def safe_encode(value: str) -> str:
    """Codifica de forma segura un valor para URL, manejando caracteres especiales."""
    if not value:
        return ''
    try:
        # Asegurar que el valor esté en formato string y en UTF-8 válido
        if isinstance(value, bytes):
            # Intentar decodificar desde diferentes codificaciones
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    value = value.decode(encoding)
                    break
                except (UnicodeDecodeError, AttributeError):
                    continue
            else:
                # Fallback: reemplazar caracteres inválidos
                value = value.decode('utf-8', errors='replace')
        
        # Si es string, asegurar que se pueda codificar en UTF-8
        if isinstance(value, str):
            try:
                # Verificar que se puede codificar en UTF-8
                value.encode('utf-8')
            except UnicodeEncodeError:
                # Intentar convertir desde otras codificaciones
                for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        # Asumir que el string está en esa codificación y convertir a UTF-8
                        value = value.encode(encoding).decode('utf-8')
                        break
                    except:
                        continue
                else:
                    # Fallback: reemplazar caracteres problemáticos
                    value = value.encode('utf-8', errors='replace').decode('utf-8')
        
        # quote_plus ya maneja la codificación URL correctamente
        return quote_plus(value)
    except Exception as e:
        logger.warning(f"Error al codificar valor: {e}")
        # Fallback: intentar codificar directamente
        try:
            # Último recurso: convertir a string y reemplazar caracteres problemáticos
            str_value = str(value)
            str_value = str_value.encode('utf-8', errors='replace').decode('utf-8')
            return quote_plus(str_value)
        except:
            return ''

if settings.DATABASE_URL:
    # URL con user/password en percent-encoding (solo ASCII) para evitar error de codificación en psycopg2
    database_url = _url_ascii_safe(settings.DATABASE_URL)
else:
    db_user = safe_encode(settings.DB_USER) if settings.DB_USER else ''
    db_password = safe_encode(settings.DB_PASSWORD) if settings.DB_PASSWORD else ''
    db_host = safe_encode(settings.DB_HOST) if settings.DB_HOST else 'localhost'
    db_port = settings.DB_PORT or 5432
    db_name = safe_encode(settings.DB_NAME) if settings.DB_NAME else ''
    
    database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    # Verificar que la URL final se puede codificar en UTF-8
    try:
        database_url.encode('utf-8')
    except UnicodeEncodeError:
        logger.error("ERROR: La URL de conexión contiene caracteres no válidos en UTF-8")
        logger.error("Verifica que el archivo .env esté en UTF-8 o usa DATABASE_URL directamente")
        raise

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
    def ensure_utf8_param(value):
        """Asegura que un parámetro esté en UTF-8 válido."""
        if not value:
            return value
        if isinstance(value, str):
            try:
                value.encode('utf-8')
                return value
            except UnicodeEncodeError:
                # Intentar convertir desde otras codificaciones
                for encoding in ['latin-1', 'cp1252', 'iso-8859-1']:
                    try:
                        # Asumir que está en esa codificación y convertir a UTF-8
                        return value.encode(encoding).decode('utf-8')
                    except:
                        continue
                # Fallback: reemplazar caracteres problemáticos
                return value.encode('utf-8', errors='replace').decode('utf-8')
        return str(value)
    
    # Evitar UnicodeDecodeError en psycopg2/libpq (Windows): DSN solo ASCII + limpiar env PG*
    import psycopg2

    # 1) Cargar DATABASE_URL desde .env con codificación explícita (bypass pydantic)
    def _load_database_url() -> str:
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if not os.path.isfile(env_path):
            return getattr(settings, "DATABASE_URL", "") or ""
        for enc in ("utf-8", "cp1252", "latin-1"):
            try:
                with open(env_path, "r", encoding=enc) as f:
                    for line in f:
                        s = line.strip()
                        if s.startswith("DATABASE_URL="):
                            val = s.split("=", 1)[1].strip()
                            if len(val) >= 2 and val[0] == val[-1] and val[0] in '"\'':
                                val = val[1:-1].replace('\\"', '"').replace("\\'", "'")
                            return val
            except Exception:
                continue
        return getattr(settings, "DATABASE_URL", "") or ""

    url_from_file = _load_database_url()
    raw_url = url_from_file or getattr(settings, "DATABASE_URL", "")
    # Forzar ASCII desde el origen (evita UnicodeDecodeError en psycopg2/libpq en Windows)
    def _force_ascii(s: str) -> str:
        if not s:
            return s
        out = []
        for c in s:
            if ord(c) < 128:
                out.append(c)
            else:
                for b in c.encode("utf-8"):
                    out.append(f"%{b:02X}")
        return "".join(out)
    raw_url = _force_ascii(raw_url)
    # #region agent log
    _dbg_log("raw_url source", {"from_file": bool(url_from_file), "raw_len": len(raw_url), "raw_has_non_ascii": any(ord(c) > 127 for c in raw_url) if raw_url else False}, "H2")
    # #endregion

    if not raw_url:
        # Construir URL desde variables individuales (password con quote_plus por &, +, etc.)
        raw_url = "postgresql://{user}:{password}@{host}:{port}/{database}".format(
            user=quote_plus(ensure_utf8_param(settings.DB_USER) or "", safe=""),
            password=quote_plus(ensure_utf8_param(settings.DB_PASSWORD) or "", safe=""),
            host=ensure_utf8_param(settings.DB_HOST) or "localhost",
            port=settings.DB_PORT or 5432,
            database=ensure_utf8_param(settings.DB_NAME) or "",
        )

    # Siempre usar DSN ASCII (nunca pasar password/user con acentos a psycopg2)
    dsn = _url_ascii_safe(raw_url)
    # #region agent log
    _dbg_log("after _url_ascii_safe", {"dsn_len": len(dsn), "dsn_has_non_ascii": any(ord(c) > 127 for c in dsn)}, "H1")
    # #endregion
    # Forzar 100% ASCII: cualquier char no-ASCII -> percent-encoding UTF-8
    def _to_ascii(s: str) -> str:
        out = []
        for c in s:
            if ord(c) < 128:
                out.append(c)
            else:
                for b in c.encode("utf-8"):
                    out.append(f"%{b:02X}")
        return "".join(out)
    dsn = _to_ascii(dsn)
    # #region agent log
    _dbg_log("after nuclear conversion", {"dsn_len": len(dsn), "dsn_has_non_ascii": any(ord(c) > 127 for c in dsn), "byte_at_85": ord(dsn[85]) if len(dsn) > 85 else None}, "H1|H5")
    # #endregion
    # Limpiar vars PG* para que libpq use solo nuestro DSN
    for k in list(os.environ):
        if k.upper() in (
            "PGPASSWORD", "PGHOST", "PGUSER", "PGDATABASE", "PGPORT", "DATABASE_URL",
            "PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGPASSFILE",
        ):
            os.environ.pop(k, None)
    # Usar parámetros explícitos (como app.db.connection) para evitar encoding en DSN (Windows)
    conn_kw = {
        "host": settings.DB_HOST or "localhost",
        "port": settings.DB_PORT or 5432,
        "user": settings.DB_USER or "",
        "password": settings.DB_PASSWORD or "",
        "dbname": settings.DB_NAME or "yego_integral",
        "client_encoding": "UTF8",
    }
    # #region agent log
    _dbg_log("before connect", {"conn_kw_keys": list(conn_kw.keys())}, "H1|H4|H5")
    # #endregion

    try:
        raw_conn = psycopg2.connect(**conn_kw)
        def creator():
            return raw_conn
        connectable = create_engine(
            'postgresql://',
            poolclass=pool.NullPool,
            creator=creator,
            connect_args={'client_encoding': 'UTF8'}
        )
        with connectable.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata
            )
            with context.begin_transaction():
                context.run_migrations()
        raw_conn.close()
    except Exception as e:
        # #region agent log
        _dbg_log("connect failed", {"error_type": type(e).__name__, "error_msg": str(e)[:200]}, "H4")
        # #endregion
        logger.error(f"Error al conectar: {e}")
        if not settings.DATABASE_URL:
            logger.error("Comprueba DB_HOST, DB_USER, DB_PASSWORD, DB_NAME o define DATABASE_URL en .env")
        raise


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
