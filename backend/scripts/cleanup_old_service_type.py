"""
Limpia filas de breakdown='service_type' con dimension_key que ya no debería existir
tras la normalización canónica (072). Luego el backfill las re-creará con la clave normalizada.
"""
import os, sys
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.db.connection import _get_connection_params
import psycopg2
from psycopg2.extras import RealDictCursor

def main():
    conn = psycopg2.connect(**dict(_get_connection_params()), connect_timeout=15)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Mostrar antes
    cur.execute("""
        SELECT dimension_key, SUM(trips) AS total_trips
        FROM ops.real_drill_dim_fact
        WHERE breakdown = 'service_type'
        GROUP BY dimension_key
        ORDER BY total_trips DESC
    """)
    print("=== ANTES ===")
    for r in cur.fetchall():
        print(f"  {r['dimension_key']!r:40s} trips={r['total_trips']}")

    # Borrar TODAS las filas de breakdown='service_type' para que el backfill las recree limpias
    cur.execute("DELETE FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type'")
    deleted = cur.rowcount
    print(f"\nEliminadas {deleted} filas con breakdown='service_type'")

    conn.commit()

    # Verificar
    cur.execute("""
        SELECT COUNT(*) AS n FROM ops.real_drill_dim_fact WHERE breakdown = 'service_type'
    """)
    print(f"Filas restantes con breakdown='service_type': {cur.fetchone()['n']}")

    cur.close()
    conn.close()
    print("\nListo. Ahora ejecutar backfill para repoblar.")

if __name__ == "__main__":
    main()
