import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from app.settings import settings
import logging

logger = logging.getLogger(__name__)

connection_pool = None


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
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error en transacción de base de datos: {e}")
        raise
    finally:
        if conn:
            connection_pool.putconn(conn)


@contextmanager
def get_db_drill():
    """
    Conexión dedicada para el Real LOB drill, con statement_timeout=0 en el startup.
    El pool puede no aplicar options si el rol fuerza 15s; esta conexión nueva sí envía options.
    """
    params = _get_connection_params()
    params["options"] = "-c statement_timeout=0"
    conn = None
    try:
        conn = psycopg2.connect(**params)
        # #region agent log
        try:
            import os, json, time
            _lp = os.path.join(os.path.dirname(__file__), "..", "..", "..", "debug-1c8c83.log")
            with open(_lp, "a", encoding="utf-8") as _f:
                _f.write(json.dumps({"sessionId": "1c8c83", "timestamp": int(time.time() * 1000), "location": "connection.py:get_db_drill", "message": "drill connection opened", "data": {}, "hypothesisId": "H4"}) + "\n")
        except Exception:
            pass
        # #endregion
        logger.info("Drill connection opened (options=statement_timeout=0)")
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error en transacción de base de datos (drill): {e}")
        raise
    finally:
        if conn:
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

