"""
Ejecuta el audit de freshness y luego las consultas de evidencia (Fase G).
Salida: COUNT audit, últimas 20 filas, último checked_at por dataset.
Uso: cd backend && python -m scripts.run_freshness_evidence
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main() -> None:
    from app.db.connection import get_db, init_db_pool
    from psycopg2.extras import RealDictCursor

    init_db_pool()

    # 1) Ejecutar audit (subprocess para evitar problemas de import)
    print("=== 1) Ejecutando run_data_freshness_audit ===\n")
    import subprocess
    r = subprocess.run(
        [sys.executable, "-m", "scripts.run_data_freshness_audit"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        capture_output=False,
        timeout=300,
    )
    if r.returncode != 0:
        print("  [WARN] Audit script returned", r.returncode)

    # 2) Evidencia SQL
    print("\n=== 2) Evidencia SQL ===\n")
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        cur.execute("SELECT COUNT(*) AS n FROM ops.data_freshness_audit")
        n = cur.fetchone()["n"]
        print(f"SELECT COUNT(*) FROM ops.data_freshness_audit;\n  -> {n}\n")

        cur.execute("""
            SELECT id, dataset_name, source_object, derived_object, grain,
                   source_max_date, derived_max_date, expected_latest_date,
                   lag_days, missing_expected_days, status, alert_reason, checked_at
            FROM ops.data_freshness_audit
            ORDER BY checked_at DESC
            LIMIT 20
        """)
        rows = cur.fetchall()
        print("SELECT * FROM ops.data_freshness_audit ORDER BY checked_at DESC LIMIT 20;")
        for r in rows:
            print(f"  {r['dataset_name']} | source_max={r['source_max_date']} derived_max={r['derived_max_date']} expected={r['expected_latest_date']} | status={r['status']} | checked_at={r['checked_at']}")

        cur.execute("""
            SELECT dataset_name, MAX(checked_at) AS last_checked
            FROM ops.data_freshness_audit
            GROUP BY 1
            ORDER BY 1
        """)
        rows2 = cur.fetchall()
        print("\nSELECT dataset_name, MAX(checked_at) FROM ops.data_freshness_audit GROUP BY 1;")
        for r in rows2:
            print(f"  {r['dataset_name']} | {r['last_checked']}")

        cur.close()
    print("\n=== Fin evidencia ===")


if __name__ == "__main__":
    main()
