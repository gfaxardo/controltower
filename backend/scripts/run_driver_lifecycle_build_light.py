#!/usr/bin/env python3
"""Solo schema + vista base (sin MVs) para probar conexión y SQL."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '60000'")
        cur.execute("CREATE SCHEMA IF NOT EXISTS ops;")
        conn.commit()
        print("OK: CREATE SCHEMA ops")
        cur.execute("DROP VIEW IF EXISTS ops.v_driver_lifecycle_trips_completed CASCADE")
        conn.commit()
        cur.execute("""
            CREATE VIEW ops.v_driver_lifecycle_trips_completed AS
            SELECT
              t.conductor_id,
              t.condicion,
              t.fecha_inicio_viaje AS request_ts,
              COALESCE(t.fecha_finalizacion, t.fecha_inicio_viaje) AS completion_ts,
              t.park_id,
              t.tipo_servicio,
              CASE WHEN t.pago_corporativo IS NOT NULL AND t.pago_corporativo > 0 THEN 'b2b' ELSE 'b2c' END AS segment
            FROM public.trips_all t
            WHERE t.condicion = 'Completado'
              AND t.conductor_id IS NOT NULL
              AND t.fecha_inicio_viaje IS NOT NULL
        """)
        conn.commit()
        print("OK: vista ops.v_driver_lifecycle_trips_completed")
        cur.close()
    print("Listo (solo schema + vista).")

if __name__ == "__main__":
    main()
