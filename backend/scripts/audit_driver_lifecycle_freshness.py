#!/usr/bin/env python3
"""
Auditoría de freshness: Driver Lifecycle.
Compara MAX(last_completed_ts) en MV vs MAX(completion_ts) en trips_all.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor


def main():
    init_db_pool()

    with get_db() as conn:
        conn.autocommit = True
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SET statement_timeout = '600s'")  # 10 min para auditoría (trips_all grande)

        print("=== 1) Columnas timestamp en trips_all ===")
        cur.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'trips_all'
              AND data_type IN ('timestamp without time zone', 'timestamp with time zone', 'date')
            ORDER BY column_name
        """)
        for r in cur.fetchall():
            out = {k: str(v) if v is not None else None for k, v in (dict(r)).items()}
            print(" ", out)

        print("\n=== 2) Valores condicion (sample reciente, 2025+) ===")
        cur.execute("""
            SELECT condicion, COUNT(*) AS cnt
            FROM public.trips_all
            WHERE fecha_inicio_viaje >= '2025-01-01'
            GROUP BY condicion ORDER BY cnt DESC LIMIT 30
        """)
        for r in cur.fetchall():
            out = {k: str(v) if v is not None else None for k, v in (dict(r)).items()}
            print(" ", out)

        print("\n=== 3) Stats completion_ts (Completado, 2025+) ===")
        cur.execute("""
            SELECT
              MIN(fecha_finalizacion) AS min_fecha_finalizacion,
              MAX(fecha_finalizacion) AS max_fecha_finalizacion,
              MIN(fecha_inicio_viaje) AS min_fecha_inicio,
              MAX(fecha_inicio_viaje) AS max_fecha_inicio,
              MIN(COALESCE(fecha_finalizacion, fecha_inicio_viaje)) AS min_completion,
              MAX(COALESCE(fecha_finalizacion, fecha_inicio_viaje)) AS max_completion,
              COUNT(*) FILTER (WHERE fecha_finalizacion IS NULL) AS nulls_finalizacion,
              COUNT(*) AS total
            FROM public.trips_all
            WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
              AND fecha_inicio_viaje >= '2025-01-01'
        """)
        for r in cur.fetchall():
            out = {k: str(v) if v is not None else None for k, v in (dict(r)).items()}
            print(" ", out)

        print("\n=== 4) COMPARACIÓN ===")
        cur.execute("""
            SELECT MAX(COALESCE(fecha_finalizacion, fecha_inicio_viaje)) AS fuente_max
            FROM public.trips_all
            WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
        """)
        fuente = cur.fetchone()["fuente_max"]
        cur.execute("SELECT MAX(last_completed_ts) AS mv_max FROM ops.mv_driver_lifecycle_base")
        mv = cur.fetchone()["mv_max"]

        print("Fuente (trips_all):", fuente)
        print("MV (last_completed_ts):", mv)
        if fuente == mv:
            print("Resultado: OK (coinciden)")
        else:
            print("Resultado: DIFERENCIA")
            if fuente and mv:
                if fuente > mv:
                    print("  La fuente tiene datos más recientes. Posible: refresh pendiente o MV desactualizada.")
                else:
                    print("  La MV tiene datos más recientes que la fuente. Posible inconsistencia.")

        print("\n=== 5) Trips con completion_ts > MAX(mv) ===")
        cur.execute("""
            SELECT COUNT(*) AS n
            FROM public.trips_all
            WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
              AND COALESCE(fecha_finalizacion, fecha_inicio_viaje) > (SELECT MAX(last_completed_ts) FROM ops.mv_driver_lifecycle_base)
        """)
        n = cur.fetchone()["n"]
        print(" ", n, "trips")

        if n > 0:
            print("\n=== 6) Sample trips más recientes que MV ===")
            cur.execute("""
                SELECT conductor_id, fecha_inicio_viaje, fecha_finalizacion,
                       COALESCE(fecha_finalizacion, fecha_inicio_viaje) AS completion_ts
                FROM public.trips_all
                WHERE condicion = 'Completado' AND conductor_id IS NOT NULL AND fecha_inicio_viaje IS NOT NULL
                  AND COALESCE(fecha_finalizacion, fecha_inicio_viaje) > (SELECT MAX(last_completed_ts) FROM ops.mv_driver_lifecycle_base)
                ORDER BY COALESCE(fecha_finalizacion, fecha_inicio_viaje) DESC
                LIMIT 5
            """)
            for r in cur.fetchall():
                out = {k: str(v) if v is not None else None for k, v in (dict(r)).items()}
                print(" ", out)

        cur.close()


if __name__ == "__main__":
    main()
