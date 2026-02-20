"""
PASO 4 FIX UNMAPPED E2E — Diagnóstico, fix (join solo park_id+real_tipo_servicio + de-mojibake),
checks automáticos y export opcional de unmapped.
Sin pasos manuales. statement_timeout alto donde toque.
"""
import sys
import os
import subprocess
import csv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXPORTS_DIR = os.path.join(BACKEND_DIR, "exports")
STMT_TIMEOUT = "300s"


def _fix_mojibake(s: str) -> str:
    """Intentar reparar mojibake UTF-8 leído como Latin-1 (econÃ³mico -> económico)."""
    if not s or "\u00c3" not in s:
        return s
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def _run_sql(cur, sql: str, desc: str, timeout: str = STMT_TIMEOUT):
    try:
        cur.execute(f"SET statement_timeout = '{timeout}'")
        cur.execute(sql)
        return cur.fetchall(), None
    except Exception as e:
        return None, str(e)


def main():
    os.chdir(BACKEND_DIR)
    from app.db.connection import get_db, init_db_pool

    init_db_pool()

    print("========== PASO 4 FIX UNMAPPED — DIAGNÓSTICO ==========\n")

    with get_db() as conn:
        cur = conn.cursor()

        # 1) Counts rápidos (sin vistas pesadas al inicio)
        cur.execute("SET statement_timeout = '30s'")
        cur.execute("SELECT COUNT(*) FROM ops.lob_homologation_final")
        n_homolog = cur.fetchone()[0]
        print(f"  ops.lob_homologation_final: {n_homolog} filas")

        cur.execute("""
            SELECT park_id, real_tipo_servicio, plan_lob_name, country, city
            FROM ops.lob_homologation_final
            LIMIT 5
        """)
        sample_h = cur.fetchall()
        print("  Sample homologation (park_id, real_tipo_servicio, plan_lob_name, country, city):")
        for row in sample_h:
            print("   ", row)

        # Detección de problemas
        cur.execute("""
            SELECT COUNT(*) FROM ops.lob_homologation_final
            WHERE real_tipo_servicio LIKE '%Ã%' OR plan_lob_name LIKE '%Ã%'
        """)
        mojibake_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ops.lob_homologation_final WHERE COALESCE(TRIM(country),'') = ''")
        empty_country = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM ops.lob_homologation_final WHERE COALESCE(TRIM(city),'') = ''")
        empty_city = cur.fetchone()[0]
        print(f"\n  Filas con posible mojibake (Ã): {mojibake_count}")
        print(f"  Filas con country vacío: {empty_country}")
        print(f"  Filas con city vacío: {empty_city}")

        # 2) De-mojibake en tabla (transaccional): corregir plan_lob_name in-place; real_tipo_servicio vía DELETE+INSERT
        if mojibake_count > 0:
            print("\n  Aplicando de-mojibake en ops.lob_homologation_final...")
            cur.execute("SELECT country, city, park_id, park_name, real_tipo_servicio, plan_lob_name, confidence, notes FROM ops.lob_homologation_final")
            rows = cur.fetchall()
            for r in rows:
                country, city, park_id, park_name, rt, pl, conf, notes = r
                rt2 = _fix_mojibake((rt or "").strip()) or rt
                pl2 = _fix_mojibake((pl or "").strip()) or (pl or "").strip()
                if rt2 != rt or pl2 != (pl or ""):
                    cur.execute("""
                        DELETE FROM ops.lob_homologation_final
                        WHERE (country IS NOT DISTINCT FROM %s) AND (city IS NOT DISTINCT FROM %s)
                          AND park_id = %s AND real_tipo_servicio = %s
                    """, (country, city, park_id, rt))
                    cur.execute("""
                        INSERT INTO ops.lob_homologation_final
                        (country, city, park_id, park_name, real_tipo_servicio, plan_lob_name, confidence, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (country, city, park_id, real_tipo_servicio) DO UPDATE SET
                        plan_lob_name = EXCLUDED.plan_lob_name, confidence = EXCLUDED.confidence, notes = EXCLUDED.notes
                    """, (country or "", city or "", park_id, park_name, rt2, pl2 or "UNMAPPED", conf, notes))
            conn.commit()
            print("  De-mojibake aplicado.")

        cur.close()

    # 3) Aplicar migración 037 (vista con join solo park_id + real_tipo_servicio)
    print("\n========== Aplicando migración 037 (join park_id + real_tipo_servicio) ==========\n")
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR, capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        print(r.stderr or r.stdout)
        sys.exit(1)

    # 4) Checks finales (con timeout alto)
    print("\n========== CHECKS FINALES ==========\n")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SET statement_timeout = '{STMT_TIMEOUT}'")

        cur.execute("SELECT COUNT(*) FROM ops.lob_homologation_final")
        total_h = cur.fetchone()[0]
        print(f"  COUNT(*) ops.lob_homologation_final: {total_h}")

        rows, err = _run_sql(cur, """
            SELECT COUNT(*) FROM ops.v_real_lob_resolved_final WHERE resolved_lob = 'UNMAPPED'
        """, "unmapped", timeout="120s")
        if err:
            print(f"  [Timeout/error] COUNT UNMAPPED: {err}")
            unmapped = -1
        else:
            unmapped = rows[0][0] if rows else -1
            print(f"  COUNT(*) WHERE resolved_lob='UNMAPPED': {unmapped}")

        rows2, err2 = _run_sql(cur, "SELECT COUNT(*) FROM ops.v_plan_vs_real_final", "v_plan_vs_real", timeout="120s")
        if err2:
            print(f"  [Timeout/error] COUNT v_plan_vs_real_final: {err2}")
            n_final = -1
        else:
            n_final = rows2[0][0] if rows2 else -1
            print(f"  COUNT(*) v_plan_vs_real_final: {n_final}")

        print("\n  Top 10 variance_trips DESC:")
        var_desc, ed = _run_sql(cur, """
            SELECT country, city, lob, plan_trips, real_trips, variance_trips
            FROM ops.v_plan_vs_real_final
            ORDER BY variance_trips DESC NULLS LAST
            LIMIT 10
        """, "var_desc", timeout="120s")
        if var_desc:
            for row in var_desc:
                print("   ", row)
        else:
            print("   ", ed)

        print("\n  Top 10 variance_trips ASC:")
        var_asc, ea = _run_sql(cur, """
            SELECT country, city, lob, plan_trips, real_trips, variance_trips
            FROM ops.v_plan_vs_real_final
            ORDER BY variance_trips ASC NULLS LAST
            LIMIT 10
        """, "var_asc", timeout="120s")
        if var_asc:
            for row in var_asc:
                print("   ", row)
        else:
            print("   ", ea)

        # 5) Export unmapped si hay
        if unmapped is not None and unmapped > 0:
            out_path = os.path.join(EXPORTS_DIR, "unmapped_real_rows.csv")
            os.makedirs(EXPORTS_DIR, exist_ok=True)
            rows_u, _ = _run_sql(cur, """
                SELECT country, city, park_id, park_name, real_tipo_servicio, real_trips, first_seen_date, last_seen_date
                FROM ops.v_real_lob_resolved_final
                WHERE resolved_lob = 'UNMAPPED'
                ORDER BY real_trips DESC NULLS LAST
                LIMIT 500
            """, "unmapped_rows", timeout="120s")
            if rows_u:
                with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f, delimiter=",")
                    w.writerow(["country", "city", "park_id", "park_name", "real_tipo_servicio", "real_trips", "first_seen_date", "last_seen_date"])
                    w.writerows(rows_u)
                print(f"\n  Exportado: {out_path} ({len(rows_u)} filas)")

        cur.close()

    # Resumen éxito
    print("\n========== RESUMEN ==========")
    ok = total_h > 0 and (unmapped < 20 if unmapped >= 0 else True)
    if unmapped >= 0:
        print(f"  UNMAPPED: {unmapped} (objetivo < 20)")
    print(f"  Éxito: {'Sí' if ok else 'Revisar'}\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
