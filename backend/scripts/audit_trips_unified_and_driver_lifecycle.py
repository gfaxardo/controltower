"""
PASO A2 + E — Auditoría DB: trips_all, trips_2026, trips_unified, Driver Lifecycle, parks.
Ejecutar: cd backend && python -m scripts.audit_trips_unified_and_driver_lifecycle
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run(cur, sql, params=None, default=None):
    try:
        cur.execute(sql, params or ())
        return cur.fetchall()
    except Exception as e:
        return default if default is not None else [("ERROR", str(e))]

def main():
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    print("=" * 70)
    print("AUDITORÍA DB — trips_unified + Driver Lifecycle (yego_integral / conexión configurada)")
    print("=" * 70)

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

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
        if r and len(r) > 0:
            defn = (r[0].get("definition") if hasattr(r[0], "get") else r[0][0]) or ""
            uses_unified = "trips_unified" in defn
            print("  Lee de trips_unified:", uses_unified)
            if not uses_unified:
                print("  Lee de trips_all:", "trips_all" in defn)
        else:
            print("  Vista no encontrada.")

        # MAX fechas
        print("\n--- 4) MAX(fecha_inicio_viaje) y freshness ---")
        r = run(cur, "SELECT MAX(fecha_inicio_viaje) AS mx FROM public.trips_all", default=[])
        if r and r[0].get("mx"):
            print("  trips_all MAX(fecha_inicio_viaje):", r[0]["mx"])
        else:
            print("  trips_all MAX(fecha_inicio_viaje): (vacío o error)")
        r = run(cur, "SELECT MAX(fecha_inicio_viaje) AS mx FROM public.trips_2026", default=[])
        if r and len(r) > 0 and r[0].get("mx"):
            print("  trips_2026 MAX(fecha_inicio_viaje):", r[0]["mx"])
        else:
            print("  trips_2026: (tabla no existe o vacía)")
        r = run(cur, "SELECT MAX(last_completed_ts) AS mx FROM ops.mv_driver_lifecycle_base", default=[])
        if r and r[0].get("mx"):
            print("  mv_driver_lifecycle_base MAX(last_completed_ts):", r[0]["mx"])
        else:
            print("  mv_driver_lifecycle_base: (MV no existe o vacía)")

        # Counts y consistencia
        print("\n--- 5) Counts (trips_all / trips_2026 / trips_unified) ---")
        r = run(cur, "SELECT COUNT(*) AS c FROM public.trips_all", default=[])
        n_all = r[0]["c"] if r and r[0].get("c") is not None else None
        print("  trips_all COUNT:", n_all)
        has_2026 = any(1 for _ in run(cur, "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='trips_2026'", default=[]))
        n_2026 = None
        if has_2026:
            r = run(cur, "SELECT COUNT(*) AS c FROM public.trips_2026", default=[])
            n_2026 = r[0]["c"] if r and r[0].get("c") is not None else None
        print("  trips_2026 COUNT:", n_2026 if n_2026 is not None else "(tabla no existe)")
        r = run(cur, "SELECT COUNT(*) AS c FROM public.trips_unified", default=[])
        n_uni = r[0]["c"] if r and r[0].get("c") is not None else None
        print("  trips_unified COUNT:", n_uni)
        if n_all is not None and n_uni is not None:
            if not has_2026:
                print("  Consistencia (sin trips_2026): unified = all:", "OK" if n_uni == n_all else "REVISAR")
            else:
                print("  Consistencia (con trips_2026): unified sin duplicados (corte fecha); revisar manual si hay solapamiento.")

        # Unicidad weekly_stats
        print("\n--- 6) Unicidad mv_driver_weekly_stats ---")
        r = run(cur, """
            SELECT driver_key, week_start, COUNT(*) AS cnt
            FROM ops.mv_driver_weekly_stats
            GROUP BY driver_key, week_start
            HAVING COUNT(*) > 1
        """, default=[])
        dupes = len(r) if r else 0
        print("  Filas duplicadas (driver_key, week_start):", dupes, "OK" if dupes == 0 else "ROTO")

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
