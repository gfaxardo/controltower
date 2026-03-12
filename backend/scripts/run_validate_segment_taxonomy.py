#!/usr/bin/env python3
"""
Ejecuta las validaciones de backend/scripts/sql/validate_segment_taxonomy.sql
y muestra resultados. Uso: cd backend && python -m scripts.run_validate_segment_taxonomy
"""
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

try:
    from dotenv import load_dotenv
    p = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(p):
        load_dotenv(p)
except ImportError:
    pass

from app.db.connection import init_db_pool, get_db
from psycopg2.extras import RealDictCursor


QUERIES = [
    ("1) Distribución semanal por segmento", """
        SELECT week_start, segment_week AS segment_new, COUNT(*) AS drivers
        FROM ops.mv_driver_segments_weekly
        WHERE week_start >= (SELECT MAX(week_start) - 28 FROM ops.mv_driver_segments_weekly)
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2
    """),
    ("2) Masa Legend (180+)", """
        SELECT week_start, COUNT(*) FILTER (WHERE trips_completed_week >= 180) AS legend_drivers
        FROM ops.mv_driver_segments_weekly
        WHERE week_start >= (SELECT MAX(week_start) - 56 FROM ops.mv_driver_segments_weekly)
        GROUP BY 1
        ORDER BY 1 DESC
    """),
    ("3) Masa Elite (120-179)", """
        SELECT week_start, COUNT(*) FILTER (WHERE trips_completed_week BETWEEN 120 AND 179) AS elite_drivers
        FROM ops.mv_driver_segments_weekly
        WHERE week_start >= (SELECT MAX(week_start) - 56 FROM ops.mv_driver_segments_weekly)
        GROUP BY 1
        ORDER BY 1 DESC
    """),
    ("4) Top transiciones", """
        SELECT week_start, prev_segment_week AS segment_prev, segment_week AS segment_current,
               segment_change_type, COUNT(*) AS drivers
        FROM ops.mv_driver_segments_weekly
        WHERE park_id IS NOT NULL AND week_start >= (SELECT MAX(week_start) - 28 FROM ops.mv_driver_segments_weekly)
        GROUP BY 1, 2, 3, 4
        ORDER BY week_start DESC, drivers DESC
        LIMIT 20
    """),
    ("5) Same-to-same (stable)", """
        SELECT week_start, prev_segment_week AS segment_prev, segment_week AS segment_current, COUNT(*) AS drivers
        FROM ops.mv_driver_segments_weekly
        WHERE segment_week = prev_segment_week AND week_start >= (SELECT MAX(week_start) - 28 FROM ops.mv_driver_segments_weekly)
        GROUP BY 1, 2, 3
        ORDER BY week_start DESC, drivers DESC
        LIMIT 15
    """),
    ("6) Presencia Dormant", """
        SELECT week_start, COUNT(*) FILTER (WHERE segment_week = 'DORMANT') AS dormant_drivers
        FROM ops.mv_driver_segments_weekly
        WHERE week_start >= (SELECT MAX(week_start) - 56 FROM ops.mv_driver_segments_weekly)
        GROUP BY 1
        ORDER BY 1 DESC
    """),
    ("7) Config vigente (orden operativo)", """
        SELECT segment_code, segment_name, min_trips_week, max_trips_week, ordering
        FROM ops.driver_segment_config
        WHERE is_active AND effective_from <= CURRENT_DATE AND (effective_to IS NULL OR effective_to >= CURRENT_DATE)
        ORDER BY ordering ASC
    """),
]


def main():
    init_db_pool()
    print("=== VALIDATE SEGMENT TAXONOMY ===\n")
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        for name, sql in QUERIES:
            try:
                cur.execute(sql)
                rows = cur.fetchall()
                print(f"--- {name} ---")
                if not rows:
                    print("(sin filas)")
                else:
                    for r in rows:
                        print(dict(r))
                print()
            except Exception as e:
                print(f"--- {name} --- ERROR: {e}\n")
        cur.close()
    print("=== END ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
