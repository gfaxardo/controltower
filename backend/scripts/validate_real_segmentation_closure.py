"""
Validación de cierre de segmentación REAL (Fases 2 y 3).
- Fase 2: Conteos y distribución en ops.real_drill_dim_fact (active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct).
- Fase 3: Muestras y comprobación de fórmulas (activity = active + cancel_only, cancel_only_pct).
Sin rediseño; solo lectura.
"""
from __future__ import annotations

import sys
import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, BACKEND_DIR)

def run():
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    out = {"phase2": {}, "phase3": {"samples": [], "formula_ok": None, "errors": []}}

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # --- FASE 2 ---
        cur.execute("""
            SELECT
                COUNT(*) AS total_rows,
                COUNT(*) FILTER (WHERE activity_drivers IS NOT NULL AND activity_drivers > 0) AS with_activity_gt0,
                COUNT(*) FILTER (WHERE activity_drivers IS NULL) AS activity_null,
                COUNT(*) FILTER (WHERE activity_drivers = 0) AS activity_zero,
                COUNT(*) FILTER (WHERE active_drivers IS NULL) AS active_null,
                COUNT(*) FILTER (WHERE cancel_only_drivers IS NULL) AS cancel_only_null,
                COUNT(*) FILTER (WHERE cancel_only_pct IS NULL) AS cancel_only_pct_null
            FROM ops.real_drill_dim_fact
        """)
        out["phase2"]["counts"] = dict(cur.fetchone())

        cur.execute("""
            SELECT period_grain, country, breakdown,
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE activity_drivers > 0) AS with_seg
            FROM ops.real_drill_dim_fact
            GROUP BY period_grain, country, breakdown
            ORDER BY period_grain, country, breakdown
        """)
        out["phase2"]["by_grain_country_breakdown"] = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT period_grain, period_start,
                   COUNT(*) AS rows_per_period,
                   COUNT(*) FILTER (WHERE activity_drivers > 0) AS rows_with_seg
            FROM ops.real_drill_dim_fact
            GROUP BY period_grain, period_start
            ORDER BY period_grain, period_start
        """)
        out["phase2"]["by_period"] = [dict(r) for r in cur.fetchall()]

        # --- FASE 3: muestras ya pobladas y fórmulas ---
        cur.execute("""
            SELECT country, period_grain, period_start, segment, breakdown, dimension_key,
                   active_drivers, cancel_only_drivers, activity_drivers, cancel_only_pct
            FROM ops.real_drill_dim_fact
            WHERE activity_drivers IS NOT NULL AND activity_drivers > 0
            ORDER BY period_start DESC, country, breakdown
            LIMIT 20
        """)
        samples = [dict(r) for r in cur.fetchall()]
        out["phase3"]["samples"] = samples

        errors = []
        for row in samples:
            a = row.get("active_drivers") or 0
            c = row.get("cancel_only_drivers") or 0
            act = row.get("activity_drivers") or 0
            pct = row.get("cancel_only_pct")
            if act != a + c:
                errors.append({"row": row, "reason": f"activity_drivers ({act}) != active_drivers ({a}) + cancel_only_drivers ({c})"})
            if act > 0 and pct is not None:
                expected_pct = round(100.0 * c / act, 4)
                if abs(float(pct) - expected_pct) > 0.0001:
                    errors.append({"row": row, "reason": f"cancel_only_pct {pct} vs expected {expected_pct}"})
        out["phase3"]["formula_ok"] = len(errors) == 0
        out["phase3"]["errors"] = errors

        cur.close()

    return out


def main():
    result = run()
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["phase3"]["formula_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
