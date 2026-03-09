"""Diagnóstico completo de service_type para hardening Real LOB."""
import os, sys
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.db.connection import _get_connection_params
import psycopg2
from psycopg2.extras import RealDictCursor

def q(cur, title, sql, max_rows=50):
    print(f"\n{'='*60}\n{title}\n{'='*60}")
    try:
        cur.execute(sql)
        rows = cur.fetchall()
        for i, r in enumerate(rows):
            if i >= max_rows:
                print(f"... ({len(rows)} filas total)")
                break
            print(dict(r))
        if not rows:
            print("(sin resultados)")
    except Exception as e:
        print(f"ERROR: {e}")

def main():
    conn = psycopg2.connect(**dict(_get_connection_params()), connect_timeout=15)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SET statement_timeout = '60000'")

    # 1. Test validated_service_type con valores reales
    print("\n" + "="*60 + "\nTEST validated_service_type()\n" + "="*60)
    tests = ['Económico','comfort+','tuk-tuk','Taxi Moto','mensajería',
             'focos led para auto, moto','express','confort+','Confort','moto',
             'Tuk-Tuk','tuk tuk','economy','delivery-express','cargo',
             'Exprés','start','confort','xl','premier']
    for v in tests:
        cur.execute("SELECT ops.validated_service_type(%s) AS result", (v,))
        r = cur.fetchone()
        print(f"  {v!r:40s} -> {r['result']}")

    # 2. Top dimension_key en service_type (trips)
    q(cur, "TOP SERVICE_TYPE dimension_key (por trips)", """
        SELECT dimension_key, SUM(trips) AS total_trips, COUNT(*) AS n_rows
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'service_type'
        GROUP BY dimension_key
        ORDER BY total_trips DESC
        LIMIT 30
    """)

    # 3. Top LOB
    q(cur, "TOP LOB dimension_key (por trips)", """
        SELECT dimension_key, SUM(trips) AS total_trips, COUNT(*) AS n_rows
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'lob'
        GROUP BY dimension_key
        ORDER BY total_trips DESC
        LIMIT 20
    """)

    # 4. UNCLASSIFIED share
    q(cur, "UNCLASSIFIED SHARE en service_type", """
        SELECT
            SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) AS unclassified_trips,
            SUM(trips) AS total_trips,
            ROUND(100.0 * SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) / NULLIF(SUM(trips), 0), 2) AS pct_unclassified
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'service_type'
    """)

    # 5. UNCLASSIFIED share en LOB
    q(cur, "UNCLASSIFIED SHARE en LOB", """
        SELECT
            SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) AS unclassified_trips,
            SUM(trips) AS total_trips,
            ROUND(100.0 * SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) / NULLIF(SUM(trips), 0), 2) AS pct_unclassified
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'lob'
    """)

    # 6. Top raw tipo_servicio en trips (últimos 90 días) — qué hay realmente upstream
    q(cur, "TOP tipo_servicio RAW (últimos 90d, v_trips_real_canon)", """
        SELECT TRIM(COALESCE(tipo_servicio::text,'')) AS raw_val,
               COUNT(*) AS trips
        FROM ops.v_trips_real_canon
        WHERE condicion = 'Completado'
          AND fecha_inicio_viaje >= (CURRENT_DATE - 90)::date
          AND tipo_servicio IS NOT NULL
        GROUP BY TRIM(COALESCE(tipo_servicio::text,''))
        ORDER BY trips DESC
        LIMIT 40
    """, 40)

    # 7. Raw values que HOY caen en UNCLASSIFIED
    q(cur, "TOP RAW que validated_service_type() manda a UNCLASSIFIED (últimos 90d)", """
        SELECT TRIM(COALESCE(tipo_servicio::text,'')) AS raw_val,
               ops.validated_service_type(tipo_servicio::text) AS validated,
               COUNT(*) AS trips
        FROM ops.v_trips_real_canon
        WHERE condicion = 'Completado'
          AND fecha_inicio_viaje >= (CURRENT_DATE - 90)::date
          AND tipo_servicio IS NOT NULL
          AND ops.validated_service_type(tipo_servicio::text) = 'UNCLASSIFIED'
        GROUP BY TRIM(COALESCE(tipo_servicio::text,'')), ops.validated_service_type(tipo_servicio::text)
        ORDER BY trips DESC
        LIMIT 40
    """, 40)

    # 8. Raw values con tildes/espacios/guiones
    q(cur, "RAW con tildes, espacios o guiones (últimos 90d)", """
        SELECT TRIM(COALESCE(tipo_servicio::text,'')) AS raw_val,
               ops.validated_service_type(tipo_servicio::text) AS validated,
               COUNT(*) AS trips
        FROM ops.v_trips_real_canon
        WHERE condicion = 'Completado'
          AND fecha_inicio_viaje >= (CURRENT_DATE - 90)::date
          AND tipo_servicio IS NOT NULL
          AND (TRIM(tipo_servicio::text) ~ '[[:space:]]'
               OR TRIM(tipo_servicio::text) ~ '-'
               OR TRIM(tipo_servicio::text) ~ '[^a-zA-Z0-9_ -]')
        GROUP BY TRIM(COALESCE(tipo_servicio::text,'')), ops.validated_service_type(tipo_servicio::text)
        ORDER BY trips DESC
        LIMIT 40
    """, 40)

    # 9. Mapping LOB actual
    q(cur, "canon.map_real_tipo_servicio_to_lob_group (tabla mapping)", """
        SELECT * FROM canon.map_real_tipo_servicio_to_lob_group
        ORDER BY real_tipo_servicio
    """, 50)

    # 10. Duplicados potenciales en dimension_key (service_type)
    q(cur, "DUPLICADOS POTENCIALES service_type (variantes similares)", """
        SELECT dimension_key, SUM(trips) AS total_trips
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'service_type'
        GROUP BY dimension_key
        ORDER BY dimension_key
    """)

    cur.close()
    conn.close()
    print("\n=== DIAGNÓSTICO COMPLETO ===")

if __name__ == "__main__":
    main()
