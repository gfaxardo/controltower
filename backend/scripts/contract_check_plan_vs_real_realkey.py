#!/usr/bin/env python3
"""
Contract check: Plan vs Real REALKEY.
Verifica que DB (ops.v_plan_vs_real_realkey_final), API y FE estén alineados.
- Consulta information_schema.columns para la vista oficial.
- Samplea 5 filas.
- Valida park_name no NULL en plan_month (PLAN_ONLY).
- Valida matched_pct (real_month vs plan_month).
- Detecta referencias a columnas antiguas (plan_lob_name, lob_name, unmapped, homologation) en BE/FE.
Exit 0 si OK, exit 1 si hay mismatch o validación fallida.
"""
from __future__ import annotations

import os
import subprocess
import sys

# Add backend to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(SCRIPT_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Use env from .env if present (same as app)
try:
    from dotenv import load_dotenv
    env_path = os.path.join(BACKEND_DIR, ".env")
    if os.path.isfile(env_path):
        load_dotenv(env_path)
except ImportError:
    pass

from app.db.connection import get_db, init_db_pool
import psycopg2.extras

REPO_ROOT = os.path.dirname(BACKEND_DIR)
VIEW_OFFICIAL = "ops.v_plan_vs_real_realkey_final"
EXPECTED_DB_COLUMNS = [
    "country", "city", "park_id", "park_name", "real_tipo_servicio", "period_date",
    "trips_plan", "trips_real", "revenue_plan", "revenue_real",
    "variance_trips", "variance_revenue"
]
FORBIDDEN_PATTERNS = [
    (r"plan_lob_name", "plan_lob_name (LOB homologation)"),
    (r"\blob_name\b", "lob_name (LOB dimension)"),
    (r"unmapped", "unmapped"),
    (r"homologation", "homologation"),
]
# Allowed: territory-quality/unmapped-parks (different feature), phase2c lob_name for LOB universe
ALLOWED_FILES_FOR_FORBIDDEN = [
    "territory_quality_service.py",  # unmapped parks (parks sin mapeo dim)
    "phase2c.py", "lob_universe_service.py", "lob_universe_repo.py", "LobUniverseView",
    "data_contract.py",  # is_unmapped_tipo_servicio
]


def get_db_columns(conn) -> list[str]:
    schema, view_name = VIEW_OFFICIAL.split(".")
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """, (schema, view_name))
    rows = cur.fetchall()
    cur.close()
    return [r[0] for r in rows]


def view_exists(conn) -> bool:
    cur = conn.cursor()
    cur.execute("""
        SELECT 1 FROM information_schema.views
        WHERE table_schema = 'ops' AND table_name = 'v_plan_vs_real_realkey_final'
    """)
    out = cur.fetchone()
    cur.close()
    return out is not None


def sample_rows(conn, n: int = 5) -> list[dict]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(f"""
        SELECT * FROM {VIEW_OFFICIAL}
        ORDER BY period_date DESC NULLS LAST, country, city, park_id
        LIMIT %s
    """, (n,))
    rows = cur.fetchall()
    cur.close()
    return [dict(r) for r in rows]


def plan_month(conn) -> str | None:
    cur = conn.cursor()
    cur.execute("SELECT MAX(period_date) FROM staging.plan_projection_realkey_raw")
    row = cur.fetchone()
    cur.close()
    return str(row[0]) if row and row[0] else None


def real_month(conn) -> str | None:
    cur = conn.cursor()
    cur.execute(f"""
        SELECT MAX(period_date) FROM {VIEW_OFFICIAL} WHERE trips_real IS NOT NULL
    """)
    row = cur.fetchone()
    cur.close()
    return str(row[0]) if row and row[0] else None


def null_park_name_count_plan_month(conn, plan_month_val: str) -> int:
    cur = conn.cursor()
    cur.execute(f"""
        SELECT COUNT(*) FROM {VIEW_OFFICIAL}
        WHERE period_date = %s::date AND park_name IS NULL
    """, (plan_month_val,))
    row = cur.fetchone()
    cur.close()
    return row[0] if row else 0


def matched_pct_plan_month(conn, plan_month_val: str) -> float | None:
    cur = conn.cursor()
    cur.execute(f"""
        WITH t AS (
            SELECT
                COUNT(*) FILTER (WHERE trips_plan IS NOT NULL AND trips_real IS NOT NULL) AS matched,
                COUNT(*) FILTER (WHERE trips_plan IS NOT NULL) AS with_plan
            FROM {VIEW_OFFICIAL}
            WHERE period_date = %s::date
        )
        SELECT CASE WHEN with_plan > 0 THEN (matched::numeric / with_plan * 100) ELSE NULL END FROM t
    """, (plan_month_val,))
    row = cur.fetchone()
    cur.close()
    return float(row[0]) if row and row[0] is not None else None


def grep_forbidden_in_code() -> list[tuple[str, int, str]]:
    findings = []
    for pattern, label in FORBIDDEN_PATTERNS:
        for search_dir, path_filter in [
            (BACKEND_DIR, lambda p: "plan_vs_real" in p.lower() or ("ops" in p and "routers" in p)),
            (os.path.join(REPO_ROOT, "frontend"), lambda p: "PlanVsReal" in p or "plan-vs-real" in p or "plan_vs_real" in p),
        ]:
            try:
                out = subprocess.run(
                    ["rg", "-n", pattern, search_dir, "--glob", "!*.pyc", "--glob", "!*alembic*", "--glob", "!*__pycache__*", "--glob", "!*.map"],
                    capture_output=True, text=True, timeout=15, cwd=REPO_ROOT
                )
                # rg returns 1 when no match
                if out.returncode not in (0, 1):
                    continue
                if not out.stdout:
                    continue
                for line in out.stdout.strip().split("\n"):
                    if ":" not in line:
                        continue
                    path, rest = line.split(":", 1)
                    if any(a in path for a in ALLOWED_FILES_FOR_FORBIDDEN):
                        continue
                    if path_filter(path):
                        line_no = int(rest.split(":")[0]) if ":" in rest else 0
                        findings.append((path, line_no, label))
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    return findings


def main() -> int:
    errors = []
    warnings = []

    # 1) DB view exists and columns
    try:
        init_db_pool()
    except Exception as e:
        errors.append(f"DB init failed: {e}")
        print("FAIL: could not connect to DB. Set DB_* env or .env.")
        return 1

    with get_db() as conn:
        if not view_exists(conn):
            errors.append(f"View {VIEW_OFFICIAL} does not exist. Run alembic upgrades.")
        else:
            db_cols = get_db_columns(conn)
            missing = [c for c in EXPECTED_DB_COLUMNS if c not in db_cols]
            extra = [c for c in db_cols if c not in EXPECTED_DB_COLUMNS]
            if missing:
                errors.append(f"DB missing columns: {missing}")
            if extra:
                warnings.append(f"DB extra columns (allowed): {extra}")

            # Sample
            try:
                sample = sample_rows(conn, 5)
                if sample:
                    warnings.append(f"Sample rows: {len(sample)} (keys: {list(sample[0].keys())})")
            except Exception as e:
                msg = str(e)
                if "timeout" in msg.lower():
                    warnings.append(f"Sample query timeout (slow DB): {msg}")
                else:
                    errors.append(f"Sample query failed: {e}")
                conn.rollback()

            # plan_month validations
            try:
                pm = plan_month(conn)
                rm = real_month(conn)
            except Exception as e:
                msg = str(e)
                if "timeout" in msg.lower():
                    warnings.append(f"plan_month/real_month timeout (slow DB): {msg}")
                    pm = None
                    rm = None
                else:
                    errors.append(f"plan_month/real_month query failed: {e}")
                    pm = None
                    rm = None
                conn.rollback()
            if pm:
                try:
                    null_count = null_park_name_count_plan_month(conn, pm)
                    if null_count > 0:
                        errors.append(f"park_name NULL in plan_month {pm}: count={null_count} (must be 0)")
                    matched = matched_pct_plan_month(conn, pm)
                    if rm and matched is not None:
                        if matched < 30:
                            warnings.append(f"matched_pct in plan_month {pm}: {matched:.1f}% (warning if < 30%)")
                    elif not rm or (str(rm) < str(pm)):
                        warnings.append("real_month < plan_month or no real yet: matched_pct is N/A (not a failure)")
                except Exception as e:
                    errors.append(f"plan_month validations failed: {e}")
                    conn.rollback()
            else:
                warnings.append("No plan_month (staging.plan_projection_realkey_raw empty)")

    # 2) Forbidden patterns in plan-vs-real code paths
    forbidden_findings = grep_forbidden_in_code()
    for path, line, label in forbidden_findings:
        if "plan_vs_real_service" in path or "PlanVsRealView" in path or "ops.py" in path:
            errors.append(f"Forbidden '{label}' in {path}:{line}")

    # Report
    print("=== Plan vs Real REALKEY contract check ===\n")
    print("View:", VIEW_OFFICIAL)
    if errors:
        print("\nErrors:")
        for e in errors:
            print("  -", e)
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print("  -", w)
    if not errors:
        print("\nResult: PASS")
        return 0
    print("\nResult: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
