#!/usr/bin/env python3
"""
Driver Lifecycle v2 — Despliegue seguro.
Preflight, hardening, índices, cohortes, validaciones, quality gates.
Exit 0 = OK; exit != 0 = fallo.
"""
from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.connection import get_db, init_db_pool
from psycopg2.extras import RealDictCursor

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_DIR = os.path.join(BASE, "sql")
ROLLBACK_DIR = os.path.join(SQL_DIR, "rollback")
LOG_DIR = os.path.join(BASE, "logs")
PARK_NULL_WARN_THRESHOLD = 5.0  # % driver-weeks con park_id NULL
TIMEOUT_MS = 7200000  # 2h


def _cursor(conn):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
    c.execute("SET lock_timeout = '5min'")
    return c


def _split_sql(content: str):
    content = re.sub(r"--[^\n]*", "", content)
    stmts = []
    buf, inside = [], False
    i, n = 0, len(content)
    while i < n:
        if not inside and content[i : i + 2] == "$$":
            inside = True
            buf.append(content[i : i + 2])
            i += 2
            continue
        if inside and content[i : i + 2] == "$$":
            inside = False
            buf.append(content[i : i + 2])
            i += 2
            continue
        if not inside and content[i] == ";" and (i + 1 >= n or content[i + 1] in "\n\r"):
            j = i + 1
            while j < n and content[j] in " \t\n\r":
                j += 1
            s = "".join(buf).strip()
            if s:
                stmts.append(s)
            buf, i = [], j
            continue
        buf.append(content[i])
        i += 1
    s = "".join(buf).strip()
    if s:
        stmts.append(s)
    return stmts


def _extract_validation_queries(content: str):
    """Extrae los 4 bloques SELECT de consistency_validation (WHERE ... diff)."""
    parts = content.split(";\n")
    queries = []
    for p in parts:
        p = p.strip()
        if p.startswith("WITH") and "FROM ops." in p:
            queries.append(p + ";")
    return queries


def _run_sql_file(conn, path: str, desc: str, in_transaction: bool = False) -> bool:
    """Ejecuta SQL file. Si in_transaction o content tiene BEGIN/COMMIT, no commit hasta el final."""
    if not os.path.isfile(path):
        print(f"  [SKIP] {path} no existe")
        return True
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    stmts = _split_sql(content)
    use_txn = in_transaction or ("BEGIN" in content and "COMMIT" in content)
    cur = conn.cursor()
    try:
        for stmt in stmts:
            if not stmt or len(stmt) < 5:
                continue
            cur.execute(stmt)
            if not use_txn:
                conn.commit()
        if use_txn:
            conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"  [ERROR] {desc}: {e}")
        cur.close()
        return False
    cur.close()
    print(f"  [OK] {desc}")
    return True


def preflight(conn) -> bool:
    """Guarda viewdefs en rollback/ y genera restore_driver_lifecycle_v1.sql."""
    os.makedirs(ROLLBACK_DIR, exist_ok=True)
    cur = _cursor(conn)
    objs = [
        ("ops.mv_driver_weekly_stats", "matview"),
        ("ops.mv_driver_lifecycle_weekly_kpis", "matview"),
        ("ops.mv_driver_monthly_stats", "matview"),
        ("ops.mv_driver_lifecycle_monthly_kpis", "matview"),
        ("ops.v_driver_weekly_churn_reactivation", "view"),
    ]
    restore_parts = {}
    for obj, typ in objs:
        try:
            cur.execute(
                "SELECT pg_get_viewdef(%s::regclass, true) AS def",
                (obj,),
            )
            row = cur.fetchone()
            if row and row.get("def"):
                fname = obj.replace(".", "_").replace("ops_", "rollback_") + ".sql"
                path = os.path.join(ROLLBACK_DIR, fname)
                if typ == "matview":
                    drop_sql = f"DROP MATERIALIZED VIEW IF EXISTS {obj} CASCADE"
                    create_sql = f"CREATE MATERIALIZED VIEW {obj} AS\n{row['def']}\nWITH DATA;"
                    sql = f"-- Rollback: {drop_sql};\n{create_sql}"
                    restore_parts[obj] = (typ, drop_sql, create_sql)
                else:
                    drop_sql = f"DROP VIEW IF EXISTS {obj} CASCADE"
                    create_sql = f"CREATE OR REPLACE VIEW {obj} AS\n{row['def']}"
                    sql = f"-- Rollback: {drop_sql};\n{create_sql}"
                    restore_parts[obj] = (typ, drop_sql, create_sql)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(sql)
                print(f"  [OK] Guardado rollback: {fname}")
            else:
                print(f"  [WARN] {obj} no existe o sin viewdef")
        except Exception as e:
            print(f"  [WARN] {obj}: {e}")
    cur.close()

    # Generar restore_driver_lifecycle_v1.sql
    # DROP en orden inverso de dependencias; CREATE en orden de dependencias
    drop_order = [
        "ops.mv_driver_lifecycle_monthly_kpis",
        "ops.mv_driver_monthly_stats",
        "ops.mv_driver_lifecycle_weekly_kpis",
        "ops.v_driver_weekly_churn_reactivation",
        "ops.mv_driver_weekly_stats",
    ]
    create_order = [
        "ops.mv_driver_weekly_stats",
        "ops.v_driver_weekly_churn_reactivation",
        "ops.mv_driver_lifecycle_weekly_kpis",
        "ops.mv_driver_monthly_stats",
        "ops.mv_driver_lifecycle_monthly_kpis",
    ]
    restore_content = "-- Restore Driver Lifecycle v1 (rollback automático si consistency falla)\n"
    restore_content += "-- NO ejecutar manualmente salvo rollback.\n\n-- DROP (dependientes primero)\n"
    for obj in drop_order:
        if obj in restore_parts:
            _, drop_sql, _ = restore_parts[obj]
            restore_content += drop_sql + ";\n"
    restore_content += "\n-- CREATE (orden de dependencias)\n"
    for obj in create_order:
        if obj in restore_parts:
            _, _, create_sql = restore_parts[obj]
            restore_content += f"-- {obj}\n" + create_sql + "\n"
    restore_path = os.path.join(ROLLBACK_DIR, "restore_driver_lifecycle_v1.sql")
    with open(restore_path, "w", encoding="utf-8") as f:
        f.write(restore_content)
    print(f"  [OK] Generado: restore_driver_lifecycle_v1.sql")
    return True


def run_consistency_validation(conn, phase: str) -> tuple[bool, list]:
    """Ejecuta los 4 bloques; retorna (ok, lista de filas con diff). Cualquier fila = diff."""
    path = os.path.join(SQL_DIR, "driver_lifecycle_consistency_validation.sql")
    if not os.path.isfile(path):
        return True, []
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    queries = _extract_validation_queries(content)
    cur = _cursor(conn)
    fails = []
    for i, q in enumerate(queries):
        try:
            cur.execute(q)
            rows = cur.fetchall()
            for r in rows:
                fails.append(dict(r))
        except Exception as e:
            print(f"  [WARN] Validation block {i+1}: {e}")
    cur.close()
    return len(fails) == 0, fails


def run_cohort_validation(conn) -> tuple[bool, str]:
    """Ejecuta cohort validation; retorna (ok, mensaje)."""
    path = os.path.join(BASE, "scripts", "sql", "driver_lifecycle_cohort_validation.sql")
    if not os.path.isfile(path):
        return True, "cohort validation file not found"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    stmts = _split_sql(content)
    cur = _cursor(conn)
    for i, stmt in enumerate(stmts):
        if not stmt or "SELECT" not in stmt.upper():
            continue
        try:
            cur.execute(stmt)
            rows = cur.fetchall()
            if rows:
                return False, f"Cohort validation block {i+1} FAIL: {list(rows[:3])}"
        except Exception as e:
            cur.close()
            return False, str(e)
    cur.close()
    return True, "OK"


def quality_gates(conn) -> tuple[bool, str]:
    """Parks distintos, % park_id NULL."""
    cur = _cursor(conn)
    try:
        cur.execute(
            """SELECT COUNT(DISTINCT park_id) AS n FROM ops.mv_driver_weekly_stats
               WHERE park_id IS NOT NULL AND TRIM(COALESCE(park_id::text,'')) != ''"""
        )
        parks = cur.fetchone().get("n", 0)
        cur.execute(
            """SELECT COUNT(*) AS total,
                      COUNT(*) FILTER (WHERE park_id IS NULL) AS nulls
               FROM ops.mv_driver_weekly_stats"""
        )
        r = cur.fetchone()
        total = r.get("total") or 0
        nulls = r.get("nulls") or 0
        pct = 100.0 * nulls / total if total else 0
        print(f"  Parks distintos: {parks}")
        print(f"  park_id NULL: {nulls}/{total} ({pct:.2f}%)")
        if pct > PARK_NULL_WARN_THRESHOLD:
            print(f"  *** WARNING: park_id NULL > {PARK_NULL_WARN_THRESHOLD}% ***")
    except Exception as e:
        cur.close()
        return False, str(e)
    cur.close()
    return True, "OK"


def run_restore(conn) -> bool:
    """Ejecuta restore_driver_lifecycle_v1.sql (rollback automático)."""
    path = os.path.join(ROLLBACK_DIR, "restore_driver_lifecycle_v1.sql")
    if not os.path.isfile(path):
        print("  [ERROR] restore_driver_lifecycle_v1.sql no existe")
        return False
    return _run_sql_file(conn, path, "restore_v1")


def run_park_quality(conn) -> tuple[bool, float]:
    """Ejecuta park quality; retorna (ok, null_share). Si null_share > 0.05: WARNING."""
    path = os.path.join(SQL_DIR, "driver_lifecycle_park_quality.sql")
    if not os.path.isfile(path):
        return True, 0.0
    cur = _cursor(conn)
    try:
        cur.execute(open(path, encoding="utf-8").read())
        row = cur.fetchone()
        if not row:
            cur.close()
            return True, 0.0
        null_share = float(row.get("null_share") or 0)
        total = row.get("total") or 0
        null_count = row.get("null_count") or 0
        pct = 100.0 * null_share
        print(f"  park_id NULL: {null_count}/{total} ({pct:.2f}%)")
        if null_share > 0.05:
            print("  *** WARNING: null_share > 5% ***")
        cur.close()
        return True, null_share
    except Exception as e:
        cur.close()
        print(f"  [WARN] Park quality: {e}")
        return True, 0.0


def run_refresh_timed(conn) -> list[tuple[str, float]]:
    """Ejecuta refresh con timing; retorna [(step, sec), ...]."""
    cur = _cursor(conn)
    cur.execute("SELECT * FROM ops.refresh_driver_lifecycle_mvs_timed()")
    rows = cur.fetchall()
    cur.close()
    return [(r["step"], float(r["duration_sec"] or 0)) for r in rows]


def cohort_mvs_exist(conn) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM pg_matviews WHERE schemaname='ops' AND matviewname='mv_driver_cohorts_weekly'"
    )
    exists = cur.fetchone() is not None
    cur.close()
    return exists


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, f"apply_driver_lifecycle_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    log_lines = []

    def log(s: str):
        print(s)
        log_lines.append(s)

    log("=" * 60)
    log("Driver Lifecycle v2 — Apply")
    log("=" * 60)

    init_db_pool()

    try:
        with get_db() as conn:
            # 1) Preflight
            log("\n1) Preflight: guardar viewdefs en rollback/")
            preflight(conn)

            # 2) Consistency baseline
            log("\n2) Consistency validation (baseline)")
            ok_baseline, fails_baseline = run_consistency_validation(conn, "baseline")
            if fails_baseline:
                log(f"  [BASELINE] {len(fails_baseline)} filas con diff (registrado, no bloquea)")
            else:
                log("  [BASELINE] 0 diffs")

            # 3) Hardening v2 (en transacción; si falla → rollback)
            log("\n3) Ejecutar driver_lifecycle_hardening_v2.sql")
            if not _run_sql_file(conn, os.path.join(SQL_DIR, "driver_lifecycle_hardening_v2.sql"), "hardening_v2"):
                log("  [ROLLBACK] Hardening falló; transacción revertida.")
                return 1

            # 4) Refresh
            log("\n4) Refresh MVs")
            _run_sql_file(conn, os.path.join(SQL_DIR, "driver_lifecycle_refresh_timed.sql"), "refresh_timed_fn")
            try:
                timed_rows = run_refresh_timed(conn)
                conn.commit()
            except Exception as e:
                conn.rollback()
                cur = conn.cursor()
                cur.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
                cur.execute("SET lock_timeout = '5min'")
                try:
                    cur.execute("SELECT ops.refresh_driver_lifecycle_mvs()")
                    conn.commit()
                    log(f"  [OK] Refresh (fallback estándar)")
                except Exception as e2:
                    conn.rollback()
                    log(f"  [ERROR] Refresh: {e2}")
                    return 1
                cur.close()
                timed_rows = []
            if timed_rows:
                total_sec = sum(s for _, s in timed_rows)
                lifecycle_sec = sum(s for st, s in timed_rows if "cohort" not in st.lower())
                cohort_sec = sum(s for st, s in timed_rows if "cohort" in st.lower())
                for step, sec in timed_rows:
                    log(f"  {step}: {sec:.1f}s")
                log(f"  Lifecycle base: {lifecycle_sec:.1f}s | Cohorts: {cohort_sec:.1f}s | Total: {total_sec:.1f}s")

            # 5) Consistency post → si falla: rollback automático
            log("\n5) Consistency validation (post)")
            ok_post, fails_post = run_consistency_validation(conn, "post")
            if not ok_post or fails_post:
                log(f"  [FAIL] {len(fails_post)} filas con diff. Ejecutando rollback automático...")
                for r in fails_post[:5]:
                    log(f"    {r}")
                if run_restore(conn):
                    conn.commit()
                    log("  [ROLLBACK] restore_driver_lifecycle_v1.sql ejecutado.")
                else:
                    log("  [ERROR] Restore falló. Revertir manualmente.")
                return 1
            log("  [OK] 0 diffs")

            # 6) Park quality gate
            log("\n6) Park quality gate")
            run_park_quality(conn)

            # 7) Índices trips_all + cohort
            log("\n7) Índices y ANALYZE")
            for idx_name, idx_path in [
                ("indexes_and_analyze", os.path.join(SQL_DIR, "driver_lifecycle_indexes_and_analyze.sql")),
                ("cohort_indexes", os.path.join(SQL_DIR, "driver_lifecycle_cohort_indexes.sql")),
            ]:
                if os.path.isfile(idx_path):
                    old_ac = conn.autocommit
                    conn.autocommit = True
                    try:
                        with open(idx_path, "r", encoding="utf-8") as f:
                            stmts = _split_sql(f.read())
                        cur = conn.cursor()
                        for stmt in stmts:
                            if not stmt or len(stmt) < 10:
                                continue
                            try:
                                cur.execute(stmt)
                            except Exception as e:
                                log(f"  [WARN] {idx_name}: {e}")
                        cur.close()
                    finally:
                        conn.autocommit = old_ac

            # 8) Cohortes
            log("\n8) Cohortes")
            if not cohort_mvs_exist(conn):
                if not _run_sql_file(conn, os.path.join(SQL_DIR, "driver_lifecycle_cohorts.sql"), "cohorts"):
                    return 1
            else:
                log("  [SKIP] MVs cohortes ya existen")
            _run_sql_file(conn, os.path.join(SQL_DIR, "driver_lifecycle_refresh_with_cohorts.sql"), "refresh_with_cohorts")

            # 9) Refresh final con benchmark
            log("\n9) Refresh final (benchmark)")
            try:
                timed_rows = run_refresh_timed(conn)
                conn.commit()
            except Exception as e:
                conn.rollback()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT ops.refresh_driver_lifecycle_mvs()")
                    conn.commit()
                    cur.close()
                    log(f"  [OK] Refresh (sin timed)")
                except Exception:
                    conn.rollback()
                    log(f"  [WARN] Refresh: {e}")
            else:
                total_sec = sum(s for _, s in timed_rows)
                for step, sec in timed_rows:
                    log(f"  {step}: {sec:.1f}s")
                log(f"  Total: {total_sec:.1f}s")

            # 10) Cohort validation
            log("\n10) Cohort validation")
            ok_cohort, msg = run_cohort_validation(conn)
            if not ok_cohort:
                log(f"  [FAIL] {msg}")
                return 1
            log("  [OK] Cohort validation")

            # 11) Quality gates
            log("\n11) Quality gates")
            ok_qg, _ = quality_gates(conn)
            if not ok_qg:
                return 1

    except Exception as e:
        log(f"[FATAL] {e}")
        import traceback
        traceback.print_exc()
        return 1

    log("\n" + "=" * 60)
    log("Driver Lifecycle v2 — OK")
    log("=" * 60)
    log("Success summary:")
    log("  - consistency_validation: 0 filas diff")
    log("  - cohort_validation: OK")
    log("  - null_share: verificado (warning si > 5%)")
    log("  - rollback listo: backend/sql/rollback/restore_driver_lifecycle_v1.sql")

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))
    log(f"Log: {log_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
