import logging
import threading
from contextlib import contextmanager
from typing import Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

from app.settings import settings

logger = logging.getLogger(__name__)

connection_pool = None

# --- Cancelación al cerrar el cliente (AbortController / socket cerrado) ---
# run_in_executor no interrumpe el hilo; registramos conexiones activas por thread id y
# desde la corrutina FastAPI llamamos conn.cancel() → PostgreSQL corta la query (como pg_cancel_backend).
_cancel_lock = threading.Lock()
_conn_stack_by_thread: dict[int, list] = {}


def register_active_pg_connection(conn) -> None:
    if conn is None:
        return
    tid = threading.get_ident()
    with _cancel_lock:
        _conn_stack_by_thread.setdefault(tid, []).append(conn)


def unregister_active_pg_connection(conn) -> None:
    if conn is None:
        return
    tid = threading.get_ident()
    with _cancel_lock:
        st = _conn_stack_by_thread.get(tid)
        if st and st and st[-1] is conn:
            st.pop()
        if st is not None and len(st) == 0:
            del _conn_stack_by_thread[tid]


def cancel_pg_queries_for_thread(tid: int) -> None:
    """Envía cancelación al backend de Postgres para las conexiones activas de ese hilo worker."""
    with _cancel_lock:
        conns = list(_conn_stack_by_thread.get(tid, ()))
    for c in reversed(conns):
        try:
            if c is not None and not c.closed:
                c.cancel()
                logger.info("Cliente desconectado: cancel() enviado a PostgreSQL (tid=%s)", tid)
        except Exception as e:
            logger.debug("cancel_pg_queries_for_thread: %s", e)


def clear_pg_registrations_for_thread(tid: int) -> None:
    with _cancel_lock:
        _conn_stack_by_thread.pop(tid, None)


def _get_connection_params():
    """Parámetros unificados: DB_* desde settings (misma fuente que DATABASE_URL en .env)."""
    params = {
        "host": settings.DB_HOST or "localhost",
        "port": settings.DB_PORT or 5432,
        "database": settings.DB_NAME or "yego_integral",
        "user": settings.DB_USER or "",
        "password": settings.DB_PASSWORD or "",
    }
    # Rol yego_user suele tener statement_timeout=15s; forzar 180s en cada conexión del pool
    # para que endpoints pesados (p. ej. real-lob/drill) no se corten.
    params["options"] = "-c statement_timeout=180000"
    return params


def get_connection_info():
    """Retorna (db, user, host, port) para logging. No requiere conexión."""
    p = _get_connection_params()
    return p["database"], p["user"], p["host"], p["port"]


def log_connection_context(cur):
    """Imprime current_database, current_user, current_schema y to_regclass para diagnóstico."""
    try:
        cur.execute("SELECT current_database() AS db, current_user AS usr, current_schema() AS sch")
        r = cur.fetchone()
        db = r["db"] if hasattr(r, "get") else (r[0] if r else "?")
        usr = r["usr"] if hasattr(r, "get") else (r[1] if r and len(r) > 1 else "?")
        sch = r["sch"] if hasattr(r, "get") else (r[2] if r and len(r) > 2 else "?")
        print(f"DB: {db} | user: {usr} | schema: {sch}")
        cur.execute("SELECT to_regclass('ops.mv_driver_lifecycle_base') AS base, to_regclass('ops.mv_driver_weekly_stats') AS weekly")
        r2 = cur.fetchone()
        base = r2["base"] if hasattr(r2, "get") else (r2[0] if r2 else None)
        weekly = r2["weekly"] if hasattr(r2, "get") else (r2[1] if r2 and len(r2) > 1 else None)
        print(f"to_regclass: ops.mv_driver_lifecycle_base={base} | ops.mv_driver_weekly_stats={weekly}")
    except Exception as e:
        print(f"[WARN] log_connection_context: {e}")


def init_db_pool():
    """Pool unificado: usa DATABASE_URL (parseado) o DB_* según settings."""
    global connection_pool
    try:
        params = _get_connection_params()
        connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1, maxconn=10, **params
        )
        logger.info("Pool de conexiones inicializado correctamente")
    except Exception as e:
        logger.error(f"Error al inicializar pool de conexiones: {e}")
        raise

@contextmanager
def get_db():
    if connection_pool is None:
        init_db_pool()
    
    conn = None
    try:
        conn = connection_pool.getconn()
        register_active_pg_connection(conn)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        msg = str(e)
        if "does not exist" in msg.lower():
            logger.debug("Transacción: relación/vista no existe (ej. vista no creada aún): %s", msg[:200])
        else:
            logger.error(f"Error en transacción de base de datos: {e}")
        raise
    finally:
        if conn:
            unregister_active_pg_connection(conn)
            connection_pool.putconn(conn)


def _get_connection_with_timeout(timeout_ms: int):
    """Conexión nueva (fuera del pool) con statement_timeout fijado al conectar."""
    params = _get_connection_params()
    params["options"] = f"-c statement_timeout={timeout_ms}"
    return psycopg2.connect(**params)


def _audit_timeout_ms() -> int:
    """Timeout para auditoría (ms). Variable de entorno AUDIT_TIMEOUT_MS o AUDIT_STATEMENT_TIMEOUT_MS, default 600000."""
    import os
    return int(os.environ.get("AUDIT_TIMEOUT_MS", os.environ.get("AUDIT_STATEMENT_TIMEOUT_MS", "600000")))


@contextmanager
def get_db_audit(timeout_ms: Optional[int] = None):
    """
    Conexión dedicada para el script de auditoría (audit_control_tower.py).
    Usa timeout alto (default desde AUDIT_TIMEOUT_MS, 10 min) para vistas pesadas.
    Siempre cierra la conexión en finally; en excepción hace rollback antes de re-raise.
    """
    timeout_ms = timeout_ms if timeout_ms is not None else _audit_timeout_ms()
    conn = None
    try:
        conn = _get_connection_with_timeout(timeout_ms)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Error en transacción de auditoría: %s", e)
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_drill():
    """
    Conexión dedicada para el Real LOB drill, con statement_timeout=0 en el startup.
    El pool puede no aplicar options si el rol fuerza 15s; esta conexión nueva sí envía options.

    Tras SELECT muy largos el servidor o el balanceador puede cerrar el socket; los datos ya están
    leídos pero commit() fallaba con "connection already closed" y anulaba la respuesta (500).
    """
    params = _get_connection_params()
    params["options"] = "-c statement_timeout=0"
    conn = None
    body_exc: Optional[BaseException] = None
    try:
        conn = psycopg2.connect(**params)
        register_active_pg_connection(conn)
        logger.info("Drill connection opened (options=statement_timeout=0)")
        yield conn
    except BaseException as e:
        body_exc = e
        if conn and not conn.closed:
            try:
                conn.rollback()
            except psycopg2.Error:
                pass
        msg = str(e)
        if "does not exist" in msg.lower():
            logger.debug("Transacción (drill): relación/vista no existe: %s", msg[:200])
        else:
            logger.error(f"Error en transacción de base de datos (drill): {e}")
        raise
    finally:
        if conn:
            unregister_active_pg_connection(conn)
            if body_exc is None:
                try:
                    if not conn.closed:
                        conn.commit()
                except psycopg2.Error as ce:
                    logger.warning(
                        "get_db_drill: commit omitido (conexión cerrada o inestable tras lectura): %s",
                        ce,
                    )
            try:
                conn.close()
            except psycopg2.Error:
                pass

@contextmanager
def get_db_quick(timeout_ms: int = 12000):
    """
    Conexión dedicada con statement_timeout corto para queries de dashboard/UI.
    Falla rápido en lugar de bloquear minutos cuando la vista es pesada.
    """
    conn = None
    try:
        conn = _get_connection_with_timeout(timeout_ms)
        register_active_pg_connection(conn)
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        msg = str(e)
        if "does not exist" in msg.lower():
            logger.debug("Transacción (quick): relación/vista no existe: %s", msg[:200])
        else:
            logger.warning("Query excedió timeout (%dms): %s", timeout_ms, str(e)[:200])
        raise
    finally:
        if conn:
            unregister_active_pg_connection(conn)
            conn.close()


def create_plan_schema():
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS plan;")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plan.plan_long_raw (
                    id SERIAL PRIMARY KEY,
                    period_type VARCHAR(10) NOT NULL DEFAULT 'month',
                    period VARCHAR(20) NOT NULL,
                    country VARCHAR(100),
                    city VARCHAR(100),
                    line_of_business VARCHAR(100),
                    metric VARCHAR(50) NOT NULL,
                    plan_value NUMERIC NOT NULL,
                    source_file_name VARCHAR(255),
                    uploaded_at TIMESTAMP DEFAULT NOW(),
                    file_hash VARCHAR(64),
                    CONSTRAINT plan_long_raw_unique UNIQUE(period_type, period, country, city, line_of_business, metric, file_hash)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plan.plan_long_valid (
                    id SERIAL PRIMARY KEY,
                    period_type VARCHAR(10) NOT NULL,
                    period VARCHAR(20) NOT NULL,
                    country VARCHAR(100),
                    city VARCHAR(100),
                    line_of_business VARCHAR(100),
                    metric VARCHAR(50) NOT NULL,
                    plan_value NUMERIC NOT NULL,
                    source_file_name VARCHAR(255),
                    uploaded_at TIMESTAMP DEFAULT NOW(),
                    file_hash VARCHAR(64),
                    CONSTRAINT plan_long_valid_unique UNIQUE(period_type, period, country, city, line_of_business, metric, file_hash)
                );
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plan.plan_long_out_of_universe (
                    id SERIAL PRIMARY KEY,
                    period_type VARCHAR(10) NOT NULL,
                    period VARCHAR(20) NOT NULL,
                    country VARCHAR(100),
                    city VARCHAR(100),
                    line_of_business VARCHAR(100),
                    metric VARCHAR(50) NOT NULL,
                    plan_value NUMERIC NOT NULL,
                    source_file_name VARCHAR(255),
                    uploaded_at TIMESTAMP DEFAULT NOW(),
                    file_hash VARCHAR(64),
                    reason TEXT,
                    CONSTRAINT plan_long_out_of_universe_unique UNIQUE(period_type, period, country, city, line_of_business, metric, file_hash)
                );
            """)
            
            # Agregar columna reason si no existe
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_schema = 'plan' 
                        AND table_name = 'plan_long_out_of_universe' 
                        AND column_name = 'reason'
                    ) THEN
                        ALTER TABLE plan.plan_long_out_of_universe ADD COLUMN reason TEXT;
                    END IF;
                END $$;
            """)
            
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint 
                        WHERE conname = 'plan_long_out_of_universe_unique'
                    ) THEN
                        ALTER TABLE plan.plan_long_out_of_universe 
                        ADD CONSTRAINT plan_long_out_of_universe_unique 
                        UNIQUE(period_type, period, country, city, line_of_business, metric, file_hash);
                    END IF;
                END $$;
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plan.plan_long_missing (
                    id SERIAL PRIMARY KEY,
                    period_type VARCHAR(10) NOT NULL,
                    period VARCHAR(20) NOT NULL,
                    country VARCHAR(100),
                    city VARCHAR(100),
                    line_of_business VARCHAR(100),
                    metric VARCHAR(50) NOT NULL,
                    source_file_name VARCHAR(255),
                    uploaded_at TIMESTAMP DEFAULT NOW(),
                    file_hash VARCHAR(64),
                    CONSTRAINT plan_long_missing_unique UNIQUE(period_type, period, country, city, line_of_business, metric, file_hash)
                );
            """)
            
            conn.commit()
            logger.info("Esquema plan y tablas creadas/verificadas correctamente")
        except Exception as e:
            conn.rollback()
            logger.error(f"Error al crear esquema plan: {e}")
            raise
        finally:
            cursor.close()

def create_ingestion_status_schema():
    """
    Crea la tabla bi.ingestion_status para rastrear el estado de ingesta de datos.
    """
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS bi;")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS bi.ingestion_status (
                    dataset_name TEXT PRIMARY KEY,
                    max_year INT,
                    max_month INT,
                    last_loaded_at TIMESTAMPTZ,
                    is_complete_2025 BOOLEAN DEFAULT FALSE
                );
            """)
            
            # Insertar registro inicial si no existe
            cursor.execute("""
                INSERT INTO bi.ingestion_status (dataset_name, max_year, max_month, is_complete_2025) 
                VALUES ('real_monthly_agg', 2025, 0, FALSE) 
                ON CONFLICT (dataset_name) DO NOTHING;
            """)
            
            conn.commit()
            logger.info("Esquema bi.ingestion_status creado/verificado correctamente")
        except Exception as e:
            conn.rollback()
            logger.error(f"Error al crear esquema ingestion_status: {e}")
            raise
        finally:
            cursor.close()

