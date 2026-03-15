#!/usr/bin/env python3
"""
CT-MV-PERFORMANCE-HARDENING — STEP 1-2: Detección de MVs pesadas.

Escanea MVs en ops.*, bi.*, plan.* y genera tabla de riesgo:
  mv_name, schema, estimated_rows, source_tables, refresh_cost_estimate, risk_level.

HIGH RISK si: agregación sobre viajes, join con múltiples dimensiones, o > 1M rows estimados.

Uso: cd backend && python scripts/detect_heavy_mvs.py
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

from app.db.connection import get_db, init_db_pool


SCHEMAS = ("ops", "bi", "plan")
CRITICAL_MVS = [
    "ops.mv_real_lob_month_v2",
    "ops.mv_real_lob_week_v2",
]


def run(cur) -> list[dict]:
    cur.execute("""
        SELECT
            m.schemaname AS schema_name,
            m.matviewname AS mv_name,
            COALESCE(c.reltuples, 0)::bigint AS estimated_rows,
            pg_size_pretty(pg_relation_size(c.oid)) AS size_pretty,
            LOWER(COALESCE(m.definition, '')) AS definition_lower
        FROM pg_matviews m
        JOIN pg_class c ON c.relname = m.matviewname AND c.relkind = 'm'
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = m.schemaname
        WHERE m.schemaname = ANY(%s)
        ORDER BY m.schemaname, m.matviewname
    """, (list(SCHEMAS),))
    return cur.fetchall()


def infer_source_tables(definition_lower: str) -> list[str]:
    """Extrae referencias a tablas/vistas típicas del definición."""
    out = []
    for token in ("from ", "join ", "v_real_trips", "trips", "plan_long", "real_monthly", "driver_", "supply_"):
        if token in (definition_lower or ""):
            out.append(token.strip())
    if "v_real_trips_with_lob" in (definition_lower or ""):
        out.append("v_real_trips_with_lob_v2")
    return list(dict.fromkeys(out))[:5]


def risk_level(row_estimate: int, definition_lower: str, schema: str, mv_name: str) -> str:
    is_trips = "trip" in (definition_lower or "") or "viaje" in (definition_lower or "") or "v_real_trips" in (definition_lower or "")
    is_heavy_agg = "group by" in (definition_lower or "") and ("count(" in (definition_lower or "") or "sum(" in (definition_lower or ""))
    many_joins = (definition_lower or "").count(" join ") >= 2
    if row_estimate and row_estimate > 1_000_000:
        return "HIGH"
    if full_name(schema, mv_name) in CRITICAL_MVS:
        return "HIGH"
    if is_trips and (is_heavy_agg or many_joins):
        return "HIGH"
    if row_estimate and row_estimate > 100_000:
        return "MEDIUM"
    return "LOW"


def full_name(schema: str, name: str) -> str:
    return f"{schema}.{name}"


def main():
    init_db_pool()
    rows = []
    with get_db() as conn:
        cur = conn.cursor()
        for r in run(cur):
            schema = r[0]
            mv_name = r[1]
            est_rows = r[2] or 0
            size_pretty = r[3] or ""
            def_lower = r[4] or ""
            source_tables = infer_source_tables(def_lower)
            if not source_tables:
                source_tables = ["(def)"]
            cost_estimate = "heavy" if est_rows > 500_000 else ("medium" if est_rows > 50_000 else "light")
            rl = risk_level(est_rows, def_lower, schema, mv_name)
            rows.append({
                "mv_name": full_name(schema, mv_name),
                "schema": schema,
                "estimated_rows": est_rows,
                "source_tables": ", ".join(source_tables),
                "refresh_cost_estimate": cost_estimate,
                "risk_level": rl,
                "size_pretty": size_pretty,
            })
        cur.close()

    # Tabla
    print("\n" + "=" * 100)
    print("MV PERFORMANCE HARDENING — Heavy MVs (ops, bi, plan)")
    print("=" * 100)
    fmt = "{:<45} {:<6} {:>12} {:<25} {:<10} {:<6} {:<8}"
    print(fmt.format("mv_name", "schema", "estimated_rows", "source_tables", "cost_est", "risk", "size"))
    print("-" * 100)
    for r in rows:
        print(fmt.format(
            r["mv_name"][:44],
            r["schema"],
            r["estimated_rows"],
            (r["source_tables"][:24] or "-"),
            r["refresh_cost_estimate"],
            r["risk_level"],
            r["size_pretty"] or "-",
        ))
    print("=" * 100)
    print("\nCritical MVs (confirmadas):", ", ".join(CRITICAL_MVS))
    print("HIGH RISK = viajes + agregación/joins, o >1M rows, o críticas listadas.")
    print()


if __name__ == "__main__":
    main()
