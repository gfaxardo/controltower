"""
Ejecuta las validaciones SQL de la capa canónica service_type -> LOB y muestra resultados.

Uso: python -m scripts.validate_canonical_layer
"""
import sys
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def get_conn():
    from app.db.connection import _get_connection_params
    import psycopg2
    from psycopg2.extras import RealDictCursor
    params = dict(_get_connection_params())
    params["options"] = "-c application_name=ct_validate_canonical"
    conn = psycopg2.connect(**params)
    return conn.cursor(cursor_factory=RealDictCursor)


def main():
    cur = get_conn()

    print("=== A) UNCLASSIFIED en real_drill_dim_fact (service_type y lob) ===")
    cur.execute("""
        SELECT breakdown, dimension_key AS breakdown_value, SUM(trips) AS trips
        FROM ops.real_drill_dim_fact
        WHERE breakdown IN ('service_type','lob') AND dimension_key = 'UNCLASSIFIED'
        GROUP BY breakdown, dimension_key ORDER BY 1, 2
    """)
    rows = cur.fetchall()
    for r in rows:
        print(r)
    if not rows:
        print("(ninguna fila UNCLASSIFIED)")

    print("\n=== B) Top 20 tipos no mapeados (vista resuelta, últimos 90 días) ===")
    cur.execute("""
        SELECT tipo_servicio_norm, COUNT(*) AS trips
        FROM ops.v_real_trips_service_lob_resolved
        WHERE is_unclassified = true AND fecha_inicio_viaje::date >= current_date - 90
        GROUP BY tipo_servicio_norm ORDER BY trips DESC LIMIT 20
    """)
    for r in cur.fetchall():
        print(r)

    print("\n=== C) Mapeados activos (dim_real_service_type_lob) ===")
    cur.execute("SELECT service_type_norm, lob_group FROM canon.dim_real_service_type_lob WHERE is_active = true ORDER BY 1")
    for r in cur.fetchall():
        print(r)

    print("\n=== D) Conteo classified vs unclassified (últimos 90 días) ===")
    cur.execute("""
        SELECT
            CASE WHEN lob_group_resolved = 'UNCLASSIFIED' THEN 'unclassified' ELSE 'classified' END AS status,
            COUNT(*) AS trips
        FROM ops.v_real_trips_service_lob_resolved
        WHERE fecha_inicio_viaje::date >= current_date - 90
        GROUP BY 1
    """)
    for r in cur.fetchall():
        print(r)

    print("\n=== E) Monitor unmapped (v_real_service_type_unmapped_monitor) top 10 ===")
    try:
        cur.execute("""
            SELECT tipo_servicio_raw, tipo_servicio_norm, trips, first_seen_date, last_seen_date
            FROM ops.v_real_service_type_unmapped_monitor
            ORDER BY trips DESC LIMIT 10
        """)
        for r in cur.fetchall():
            print(r)
    except Exception as e:
        print("(vista no existe o error:", e, ")")

    cur.connection.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
