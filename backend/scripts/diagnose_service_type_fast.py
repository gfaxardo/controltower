"""Diagnóstico rápido de service_type — solo desde fact tables (sin v_trips_real_canon)."""
import os, sys
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.db.connection import _get_connection_params
import psycopg2
from psycopg2.extras import RealDictCursor

def q(cur, title, sql, max_rows=60):
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
    cur.execute("SET statement_timeout = '30000'")

    # 1. Test validated_service_type con valores reales
    print("\n" + "="*60 + "\nTEST validated_service_type()\n" + "="*60)
    tests = ['Económico','comfort+','tuk-tuk','Taxi Moto','mensajería',
             'focos led para auto, moto','express','confort+','Confort','moto',
             'Tuk-Tuk','tuk tuk','economy','delivery-express','cargo',
             'Exprés','start','confort','xl','premier','confort+',
             'Envíos','Standard','Premier','mensajería']
    for v in tests:
        cur.execute("SELECT ops.validated_service_type(%s) AS result", (v,))
        r = cur.fetchone()
        print(f"  {v!r:40s} -> {r['result']}")

    # 2. Top dimension_key service_type (por trips)
    q(cur, "TOP SERVICE_TYPE dimension_key (por trips)", """
        SELECT dimension_key, SUM(trips) AS total_trips, COUNT(*) AS n_rows
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'service_type'
        GROUP BY dimension_key
        ORDER BY total_trips DESC
        LIMIT 40
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

    # 4. UNCLASSIFIED share service_type
    q(cur, "UNCLASSIFIED SHARE en service_type", """
        SELECT
            SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) AS uncl_trips,
            SUM(trips) AS total_trips,
            ROUND(100.0 * SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) / NULLIF(SUM(trips), 0), 2) AS pct_uncl
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'service_type'
    """)

    # 5. UNCLASSIFIED share LOB
    q(cur, "UNCLASSIFIED SHARE en LOB", """
        SELECT
            SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) AS uncl_trips,
            SUM(trips) AS total_trips,
            ROUND(100.0 * SUM(CASE WHEN dimension_key = 'UNCLASSIFIED' THEN trips ELSE 0 END) / NULLIF(SUM(trips), 0), 2) AS pct_uncl
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'lob'
    """)

    # 6. Mapping LOB actual
    q(cur, "canon.map_real_tipo_servicio_to_lob_group", """
        SELECT * FROM canon.map_real_tipo_servicio_to_lob_group
        ORDER BY real_tipo_servicio
    """)

    # 7. Top raw tipo_servicio (muestra rápida desde trips_all LIMIT)
    q(cur, "TOP tipo_servicio RAW (trips_all, sample 500k)", """
        SELECT TRIM(LOWER(tipo_servicio::text)) AS raw_val, COUNT(*) AS n
        FROM (
            SELECT tipo_servicio FROM public.trips_all
            WHERE condicion = 'Completado' AND tipo_servicio IS NOT NULL
            ORDER BY fecha_inicio_viaje DESC
            LIMIT 500000
        ) s
        GROUP BY TRIM(LOWER(tipo_servicio::text))
        ORDER BY n DESC
        LIMIT 40
    """)

    # 8. Todos los dimension_key service_type (para ver variantes/duplicados)
    q(cur, "TODAS las dimension_key service_type (ordenadas alfa)", """
        SELECT dimension_key, SUM(trips) AS total_trips
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'service_type'
        GROUP BY dimension_key
        ORDER BY dimension_key
    """)

    cur.close()
    conn.close()
    print("\n=== DIAGNÓSTICO RÁPIDO COMPLETO ===")

if __name__ == "__main__":
    main()
