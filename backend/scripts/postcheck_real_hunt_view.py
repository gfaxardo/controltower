"""
Post-check ops.v_real_universe_by_park_for_hunt: top 30 y validar park_name != park_id.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import get_db, init_db_pool

def main():
    init_db_pool()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '120s'")

        print("=== Top 30 (real_trips DESC) ===\n")
        cur.execute("""
            SELECT park_id, park_name, country, city, real_tipo_servicio, real_trips
            FROM ops.v_real_universe_by_park_for_hunt
            ORDER BY real_trips DESC NULLS LAST
            LIMIT 30
        """)
        for r in cur.fetchall():
            print(f"  {r[1]!r} | {r[2]} | {r[3]} | {r[4]!r} | {r[5]}")

        print("\n=== Total y name_equals_id ===\n")
        cur.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN park_name = park_id::text OR park_name = park_id THEN 1 ELSE 0 END) AS name_equals_id
            FROM ops.v_real_universe_by_park_for_hunt
        """)
        row = cur.fetchone()
        total = row[0] or 0
        name_equals_id = row[1] or 0
        print(f"  total: {total}")
        print(f"  park_name = park_id (filas): {name_equals_id}")
        if total > 0:
            pct = 100.0 * (total - name_equals_id) / total
            print(f"  park_name humano (distinto de id): {pct:.1f}%")
        cur.close()

if __name__ == "__main__":
    main()
