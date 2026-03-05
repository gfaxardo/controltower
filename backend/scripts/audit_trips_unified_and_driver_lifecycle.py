"""
PASO A2 + E — Auditoría DB: trips_all, trips_2026, trips_unified, Driver Lifecycle, parks.
Ejecutar: cd backend && python -m scripts.audit_trips_unified_and_driver_lifecycle
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run(cur, sql, params=None, default=None):
    """Ejecuta SQL. Si falla: default si se pasa, si no [{"_error": str(e)}]. Hace rollback en error para no abortar la transacción."""
    try:
        cur.execute(sql, params or ())
        return cur.fetchall()
    except Exception as e:
        try:
            cur.connection.rollback()
        except Exception:
            pass
        return default if default is not None else [{"_error": str(e)}]


def run_with_timeout(cur, conn, sql, params=None, timeout_ms=60000, default=None):
    """Ejecuta SQL con statement_timeout. Para queries que pueden ser pesadas (count acotado)."""
    try:
        cur.execute(f"SET LOCAL statement_timeout = '{timeout_ms}'")
        cur.execute(sql, params or ())
        return cur.fetchall()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return default if default is not None else [{"_error": str(e)}]
    finally:
        try:
            cur.execute("RESET statement_timeout")
        except Exception:
            pass

def main():
    from app.db.connection import get_db, init_db_pool, get_connection_info, log_connection_context
    from psycopg2.extras import RealDictCursor

    db, user, host, port = get_connection_info()
    print("=" * 70)
    print("AUDITORÍA DB — trips_unified + Driver Lifecycle")
    print(f"Config: db={db} user={user} host={host}:{port}")
    print("=" * 70)

    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        log_connection_context(cur)

        # Existencia tablas/vistas
        print("\n--- 1) Existencia de objetos ---")
        for schema, name, kind in [
            ("public", "trips_all", "table"),
            ("public", "trips_2026", "table"),
            ("public", "trips_unified", "view"),
            ("ops", "v_driver_lifecycle_trips_completed", "view"),
            ("ops", "mv_driver_lifecycle_base", "matview"),
            ("ops", "mv_driver_weekly_stats", "matview"),
        ]:
            if kind == "table":
                r = run(cur, """
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = %s AND table_name = %s
                """, (schema, name), [])
            elif kind == "view":
                r = run(cur, """
                    SELECT 1 FROM information_schema.views
                    WHERE table_schema = %s AND table_name = %s
                """, (schema, name), [])
            else:
                r = run(cur, """
                    SELECT 1 FROM pg_matviews WHERE schemaname = %s AND matviewname = %s
                """, (schema, name), [])
            exists = bool(r and len(r) > 0)
            print(f"  {schema}.{name} ({kind}): {'EXISTE' if exists else 'NO EXISTE'}")

        # Definition trips_unified
        print("\n--- 2) Definición public.trips_unified ---")
        r = run(cur, "SELECT definition FROM pg_views WHERE schemaname = 'public' AND viewname = 'trips_unified'", default=[])
        if r and len(r) > 0:
            defn = (r[0].get("definition") if hasattr(r[0], "get") else r[0][0]) or ""
            print("  (primeras 400 chars):", (defn[:400] + "..." if len(defn) > 400 else defn))
            print("  Usa UNION/corte 2026:", "union" in defn.lower() and ("2026" in defn or "trips_2026" in defn.lower()))
        else:
            print("  No existe la vista o no se pudo leer.")

        # Definition v_driver_lifecycle_trips_completed
        print("\n--- 3) v_driver_lifecycle_trips_completed lee de trips_unified ---")
        r = run(cur, "SELECT definition FROM pg_views WHERE schemaname = 'ops' AND viewname = 'v_driver_lifecycle_trips_completed'", default=[])
        if r and len(r) > 0 and not (isinstance(r[0], dict) and "_error" in r[0]):
            defn = (r[0].get("definition") if hasattr(r[0], "get") else r[0][0]) or ""
            uses_unified = "trips_unified" in defn
            uses_all = "trips_all" in defn
            print("  Lee de trips_unified:", uses_unified)
            print("  Lee de trips_all:", uses_all)
        else:
            print("  Vista no encontrada.")

        # MAX fechas
        print("\n--- 4) MAX(fecha_inicio_viaje) y freshness ---")
        r = run(cur, "SELECT MAX(fecha_inicio_viaje) AS mx FROM public.trips_all", default=None)
        if r and len(r) > 0 and not (isinstance(r[0], dict) and "_error" in r[0]) and r[0].get("mx"):
            print("  trips_all MAX(fecha_inicio_viaje):", r[0]["mx"])
        else:
            err = r[0].get("_error") if r and len(r) > 0 and isinstance(r[0], dict) else None
            print("  trips_all MAX(fecha_inicio_viaje):", f"ERROR: {err}" if err else "(vacío o error)")
        r = run(cur, "SELECT MAX(fecha_inicio_viaje) AS mx FROM public.trips_2026", default=None)
        if r and len(r) > 0 and not (isinstance(r[0], dict) and "_error" in r[0]):
            if r[0].get("mx"):
                print("  trips_2026 MAX(fecha_inicio_viaje):", r[0]["mx"])
            else:
                print("  trips_2026 MAX(fecha_inicio_viaje): (vacía)")
        else:
            err = r[0].get("_error") if r and len(r) > 0 and isinstance(r[0], dict) else None
            print("  trips_2026 MAX(fecha_inicio_viaje):", f"ERROR: {err}" if err else "(tabla no existe o vacía)")
        r = run(cur, "SELECT MAX(last_completed_ts) AS mx FROM ops.mv_driver_lifecycle_base", default=None)
        if r and len(r) > 0 and not (isinstance(r[0], dict) and "_error" in r[0]) and r[0].get("mx"):
            print("  mv_driver_lifecycle_base MAX(last_completed_ts):", r[0]["mx"])
        else:
            err = r[0].get("_error") if r and len(r) > 0 and isinstance(r[0], dict) else None
            print("  mv_driver_lifecycle_base MAX(last_completed_ts):", f"ERROR: {err}" if err else "(MV no existe o vacía)")

        # Counts y consistencia (sin full scans: reltuples aprox + count acotado 60d como fallback)
        print("\n--- 5) Counts (trips_all / trips_2026 / trips_unified) ---")

        def reltuples_approx(cur, schema: str, table: str):
            """Retorna (approx_count, error_msg). Usa pg_class.reltuples para evitar full scan."""
            r = run(cur, """
                SELECT c.reltuples::bigint AS n FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = %s AND c.relname = %s
            """, (schema, table), default=None)
            if not r or (isinstance(r[0], dict) and "_error" in r[0]):
                return None, (r[0].get("_error", "sin resultado") if r and isinstance(r[0], dict) else "sin resultado")
            n = r[0].get("n") if isinstance(r[0], dict) else r[0][0]
            if n is None or (isinstance(n, (int, float)) and n < 0):
                return None, "reltuples no analizado"
            try:
                return int(n), None
            except (TypeError, ValueError):
                return None, f"valor no numérico: {n}"

        def count_bounded_60d(cur, conn, table_ref: str):
            """COUNT acotado a últimos 60 días (timeout 60s). table_ref: 'trips_all', 'trips_2026' o 'trips_unified'."""
            r = run_with_timeout(cur, conn, f"""
                SELECT COUNT(*) AS c FROM public.{table_ref}
                WHERE fecha_inicio_viaje >= (CURRENT_DATE - 60)
            """, timeout_ms=60000, default=None)
            if not r or (isinstance(r[0], dict) and "_error" in r[0]):
                return None, (r[0].get("_error", "timeout/error")[:80] if r and isinstance(r[0], dict) else "error")
            c = r[0].get("c") if isinstance(r[0], dict) else r[0][0]
            return (int(c), None) if c is not None else (None, "sin resultado")

        # trips_all: reltuples (evita full scan)
        n_all, err_all = reltuples_approx(cur, "public", "trips_all")
        all_from_reltuples = not err_all
        if err_all:
            n_all, err_all = count_bounded_60d(cur, conn, "trips_all")
            if err_all:
                print("  trips_all: ERROR:", err_all)
            else:
                print("  trips_all (últimos 60d):", n_all, "(reltuples falló, usando count acotado)")
        else:
            print("  trips_all (aprox reltuples):", f"{n_all:,}")

        has_2026 = False
        r_check = run(cur, "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='trips_2026'", default=[])
        has_2026 = bool(r_check and len(r_check) > 0 and not (isinstance(r_check[0], dict) and "_error" in r_check[0]))

        n_2026, err_2026 = None, None
        two_from_reltuples = False
        if has_2026:
            n_2026, err_2026 = reltuples_approx(cur, "public", "trips_2026")
            if err_2026:
                n_2026, err_2026 = count_bounded_60d(cur, conn, "trips_2026")
                if not err_2026:
                    print("  trips_2026 (últimos 60d):", n_2026, "(reltuples falló)")
            else:
                two_from_reltuples = all_from_reltuples
        if not has_2026:
            print("  trips_2026: (tabla no existe)")
        elif err_2026:
            print("  trips_2026: ERROR:", err_2026)
        else:
            print("  trips_2026 (aprox reltuples):", f"{n_2026:,}" if n_2026 is not None else "?")

        # trips_unified: suma reltuples solo si ambos vinieron de reltuples; si no, count acotado
        n_uni, err_uni = None, None
        if two_from_reltuples and n_all is not None and n_2026 is not None:
            n_uni = n_all + n_2026
            print("  trips_unified (aprox suma partes):", f"~{n_uni:,}", "(corte fecha puede variar)")
        elif all_from_reltuples and n_all is not None and not has_2026:
            n_uni = n_all
            print("  trips_unified (aprox = trips_all):", f"~{n_uni:,}")
        else:
            n_uni, err_uni = count_bounded_60d(cur, conn, "trips_unified")
            if err_uni:
                print("  trips_unified: ERROR:", err_uni)
            else:
                print("  trips_unified (últimos 60d):", n_uni, "(fallback count acotado)")

        if n_all is not None and n_uni is not None and not err_uni:
            if not has_2026:
                print("  Consistencia (sin trips_2026): unified ~ all:", "OK" if abs((n_uni or 0) - (n_all or 0)) < 2 else "REVISAR")
            else:
                print("  Consistencia (con trips_2026): unified ~ suma partes (corte fecha); revisar manual si hay solapamiento.")

        # Unicidad weekly_stats (acotado a últimas 12 sem si MV existe)
        print("\n--- 6) Unicidad mv_driver_weekly_stats ---")
        r = run(cur, """
            SELECT driver_key, week_start, COUNT(*) AS cnt
            FROM ops.mv_driver_weekly_stats
            WHERE week_start >= (CURRENT_DATE - 84)::date
            GROUP BY driver_key, week_start
            HAVING COUNT(*) > 1
        """, default=None)
        if not r:
            print("  Filas duplicadas: (sin resultado)")
        elif isinstance(r[0], dict) and "_error" in r[0]:
            print("  Filas duplicadas: ERROR:", r[0]["_error"][:80], "(MV no existe?)")
        else:
            dupes = len(r)
            print("  Filas duplicadas (driver_key, week_start, últimas 12 sem):", dupes, "OK" if dupes == 0 else "ROTO")

        # Parks coverage
        print("\n--- 7) Parks (dim.dim_park) ---")
        r = run(cur, "SELECT COUNT(*) AS c FROM dim.dim_park", default=[])
        if r and r[0].get("c") is not None:
            print("  dim.dim_park COUNT:", r[0]["c"])
        else:
            print("  dim.dim_park: (no existe o error)")
        r = run(cur, "SELECT column_name FROM information_schema.columns WHERE table_schema = 'dim' AND table_name = 'dim_park' AND column_name IN ('park_name','park_id','name')", default=[])
        if r:
            print("  Columnas nombre:", [x.get("column_name") or x[0] for x in r])

        cur.close()

    print("\n" + "=" * 70)
    print("Fin auditoría. Revisar PASO A checklist en docs/DIAGNOSTICO_ESTADO_DRIVER_LIFECYCLE.md")
    print("=" * 70)

if __name__ == "__main__":
    main()
