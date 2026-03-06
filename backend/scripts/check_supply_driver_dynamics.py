#!/usr/bin/env python3
"""
Verificación Driver Supply Dynamics: config, MVs, refresh log, freshness, consistencia.
Incluye: ops.driver_segment_config (y seed), MVs alerting, supply_refresh_log, unicidad mv_driver_segments_weekly.
Uso: cd backend && python -m scripts.check_supply_driver_dynamics
Exit 0 = OK, 1 = fallo.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    from app.db.connection import init_db_pool, get_db
    from psycopg2.extras import RealDictCursor

    init_db_pool()
    failed = False

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        print("=== CHECK DRIVER SUPPLY DYNAMICS ===\n")

        # Tabla de configuración de segmentos (065)
        try:
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = 'ops' AND table_name = 'driver_segment_config'"
            )
            if cur.fetchone()["n"] == 0:
                print("FAIL: missing ops.driver_segment_config")
                failed = True
            else:
                cur.execute("SELECT segment_code, min_trips_week, max_trips_week FROM ops.driver_segment_config WHERE is_active ORDER BY ordering")
                rows = cur.fetchall()
                if len(rows) < 5:
                    print(f"FAIL: driver_segment_config seed incompleta (esperados 5 segmentos, hay {len(rows)})")
                    failed = True
                else:
                    print("OK: ops.driver_segment_config exists, seed >= 5 rows")
        except Exception as e:
            print(f"FAIL: driver_segment_config — {e}")
            failed = True

        # Objetos usados por overview-enhanced, composition, migration, alerts
        objects = [
            ("ops.mv_supply_weekly", "matview"),
            ("ops.mv_supply_monthly", "matview"),
            ("ops.mv_supply_segments_weekly", "matview"),
            ("ops.mv_driver_segments_weekly", "matview"),
            ("ops.mv_supply_segment_anomalies_weekly", "matview"),
            ("ops.mv_supply_alerts_weekly", "matview"),
        ]
        for name, kind in objects:
            try:
                schema, obj = name.split(".")
                if kind == "matview":
                    cur.execute(
                        "SELECT 1 FROM pg_matviews WHERE schemaname = %s AND matviewname = %s",
                        (schema, obj),
                    )
                if cur.fetchone():
                    print(f"OK: exists {name}")
                else:
                    print(f"FAIL: missing {name}")
                    failed = True
            except Exception as e:
                print(f"FAIL: {name} — {e}")
                failed = True

        # Unicidad esperada mv_driver_segments_weekly (week_start, park_id, driver_key)
        try:
            cur.execute("""
                SELECT week_start, park_id, driver_key, COUNT(*) AS c
                FROM ops.mv_driver_segments_weekly
                GROUP BY week_start, park_id, driver_key
                HAVING COUNT(*) > 1
                LIMIT 1
            """)
            dup = cur.fetchone()
            if dup:
                print("FAIL: mv_driver_segments_weekly tiene duplicados (week_start, park_id, driver_key)")
                failed = True
            else:
                print("OK: mv_driver_segments_weekly unicidad (week, park, driver)")
        except Exception as e:
            print(f"FAIL: unicidad driver segments — {e}")
            failed = True

        # supply_refresh_log (066) — opcional para que el check no falle si 066 no aplicada
        try:
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'ops' AND table_name = 'supply_refresh_log'"
            )
            if cur.fetchone():
                cur.execute("SELECT COUNT(*) AS n FROM ops.supply_refresh_log")
                n = cur.fetchone()["n"]
                print(f"OK: ops.supply_refresh_log exists ({n} rows)")
            else:
                print("SKIP: ops.supply_refresh_log not present (migración 066)")
        except Exception as e:
            print(f"SKIP: supply_refresh_log — {e}")

        # Freshness: que get_supply_freshness pueda responder (MAX week, status)
        try:
            cur.execute("SELECT MAX(week_start) AS w FROM ops.mv_supply_segments_weekly")
            w = cur.fetchone()["w"]
            print(f"OK: freshness data (last_week_available from segments): {w}")
        except Exception as e:
            print(f"FAIL: freshness query — {e}")
            failed = True

        # Al menos un park y una semana en segments
        try:
            cur.execute(
                "SELECT COUNT(*) AS n FROM ops.mv_supply_segments_weekly WHERE park_id IS NOT NULL"
            )
            n = cur.fetchone()["n"]
            print(f"OK: mv_supply_segments_weekly rows (park not null): {n}")
        except Exception as e:
            print(f"FAIL: count segments — {e}")
            failed = True

        # Churn: advertir si en las últimas semanas siempre churned=0 y reactivated=0 (puede ser dato o vista)
        try:
            cur.execute("""
                SELECT SUM(churned) AS total_churned, SUM(reactivated) AS total_reactivated, COUNT(*) AS rows_
                FROM ops.mv_supply_weekly
                WHERE week_start >= (SELECT MAX(week_start) FROM ops.mv_supply_weekly) - 90
            """)
            r = cur.fetchone()
            if r and r["rows_"] and r["rows_"] > 0:
                tc, tr = r["total_churned"] or 0, r["total_reactivated"] or 0
                if tc == 0 and tr == 0:
                    print("WARN: churned y reactivated son 0 en las últimas ~12 semanas. Revisar ops.v_driver_weekly_churn_reactivation si se esperan valores no nulos.")
                else:
                    print(f"OK: churn/reactivation no nulos (churned_sum={tc}, reactivated_sum={tr} en últimas semanas)")
            else:
                print("SKIP: sin filas en mv_supply_weekly para validar churn")
        except Exception as e:
            print(f"SKIP: validación churn — {e}")

        # Formato semana: comprobar que week_start existe y es fecha (Sx-YYYY se genera en API)
        try:
            cur.execute("SELECT MIN(week_start) AS wmin, MAX(week_start) AS wmax FROM ops.mv_supply_segments_weekly")
            r = cur.fetchone()
            if r and r["wmin"]:
                print(f"OK: semanas en segments (min={r['wmin']}, max={r['wmax']}); formato Sx-YYYY en respuestas API")
            else:
                print("SKIP: sin semanas en mv_supply_segments_weekly")
        except Exception as e:
            print(f"SKIP: semanas — {e}")

        # EXPLAIN ANALYZE SELECT * FROM mv_driver_segments_weekly LIMIT 1000 — tiempo de ejecución
        exec_time_ms_threshold = 1000.0
        try:
            cur.execute("EXPLAIN (ANALYZE true, FORMAT text) SELECT * FROM ops.mv_driver_segments_weekly LIMIT 1000")
            raw = cur.fetchall()
            explain_rows = [(r[0] if isinstance(r, (list, tuple)) else (r.get("QUERY PLAN") if isinstance(r, dict) else list(r.values())[0])) for r in raw]
            explain_text = "\n".join(explain_rows)
            import re
            match = re.search(r"Execution Time:\s*([\d.]+)\s*ms", explain_text)
            if match:
                exec_ms = float(match.group(1))
                print(f"OK: EXPLAIN ANALYZE mv_driver_segments_weekly LIMIT 1000 — Execution Time: {exec_ms:.1f} ms")
                if exec_ms > exec_time_ms_threshold:
                    print(f"WARN: tiempo de ejecución supera umbral razonable ({exec_time_ms_threshold:.0f} ms). Revisar índices o uso de JOIN vs función.")
            else:
                print("SKIP: no se pudo extraer Execution Time de EXPLAIN ANALYZE")
        except Exception as e:
            print(f"WARN: EXPLAIN ANALYZE mv_driver_segments_weekly — {e}")

        cur.close()

    print("\n" + ("FAIL" if failed else "OK") + " (check_supply_driver_dynamics)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
