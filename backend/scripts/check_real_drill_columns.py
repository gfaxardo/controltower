"""Comprueba que real_drill_dim_fact y mv_real_drill_dim_agg tienen las columnas de segmentación (mig 106)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db

COLS = ('active_drivers', 'cancel_only_drivers', 'activity_drivers', 'cancel_only_pct')

def main():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'real_drill_dim_fact'
            AND column_name IN ('active_drivers','cancel_only_drivers','activity_drivers','cancel_only_pct')
            ORDER BY 1
        """)
        fact_cols = [r[0] for r in cur.fetchall()]
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'ops' AND table_name = 'mv_real_drill_dim_agg'
            AND column_name IN ('active_drivers','cancel_only_drivers','activity_drivers','cancel_only_pct')
            ORDER BY 1
        """)
        view_cols = [r[0] for r in cur.fetchall()]
    print("Columnas en ops.real_drill_dim_fact:", fact_cols)
    print("Columnas en ops.mv_real_drill_dim_agg (vista):", view_cols)
    ok = set(fact_cols) >= set(COLS) and set(view_cols) >= set(COLS)
    print("OK (mig 106 aplicada)" if ok else "Faltan columnas")
    return 0 if ok else 1

if __name__ == "__main__":
    sys.exit(main())
