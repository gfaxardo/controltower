"""Aplica el fix de v_driver_lifecycle_trips_completed para que lea de trips_unified.
Ejecutar después de run_driver_lifecycle_build si este sobrescribió la vista con trips_all."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool, get_connection_info

db, user, host, port = get_connection_info()
print(f"Config: db={db} user={user} host={host}:{port}")
init_db_pool()
with get_db() as conn:
    cur = conn.cursor()
    cur.execute("DROP VIEW IF EXISTS ops.v_driver_lifecycle_trips_completed CASCADE")
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
        FROM public.trips_unified t
        WHERE t.condicion = 'Completado'
          AND t.conductor_id IS NOT NULL
          AND t.fecha_inicio_viaje IS NOT NULL
    """)
    conn.commit()
    print("OK: v_driver_lifecycle_trips_completed ahora lee de public.trips_unified")
