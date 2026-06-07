"""
OV2-CX.1A — Empty State Root Cause Audit Script
Reproduces the exact scenario: CT_TRIPS_2026, day, 2026-06-06
Dumps shell response, matrix response, and CT source data.
"""
import json, os, sys
sys.path.insert(0, r"C:\cursor\controltower\controltower\backend")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "exports", "audits", "omniview_v2_empty_state")
os.makedirs(OUTPUT_DIR, exist_ok=True)

from app.services.omniview_v2_shell_service import build_shell
from app.services.omniview_v2_matrix_view_model_service import build_matrix_response
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

SOURCE = "CT_TRIPS_2026"
GRAIN = "day"
DATE_FROM = "2026-06-06"
DATE_TO = "2026-06-06"

print("=" * 60)
print(f"OV2-CX.1A Empty State Audit: {SOURCE} / {GRAIN} / {DATE_FROM}")
print("=" * 60)

# ── 1. Shell Response ───────────────────────────────────
print("\n[1] Shell Response")
shell = build_shell(source_system=SOURCE, grain=GRAIN, date_from=DATE_FROM, date_to=DATE_TO,
                     filters={"country": "peru", "city": "lima"})
shell_d = shell.to_dict()

print(f"  source_system: {shell_d['source_system']}")
print(f"  canonical_ready: {shell_d['canonical_ready']}")
print(f"  grain: {shell_d['grain']}")
print(f"  period: {shell_d.get('period', {})}")

kpi_strip = next((s for s in shell_d.get("sections", []) if s["section_id"] == "kpi_strip"), {})
print(f"  KPI strip status: {kpi_strip.get('status', {}).get('code', '?')}")
print(f"  KPIs: {[(k['metric_id'], k.get('value')) for k in kpi_strip.get('kpis', [])]}")

for sec in shell_d.get("sections", []):
    sid = sec["section_id"]
    sc = sec.get("status", {}).get("code", "?")
    print(f"  section {sid:25s} -> {sc}")

coverage = shell_d.get("coverage", {})
print(f"  coverage: {coverage.get('coverage_pct')}% ({coverage.get('days_with_data')}/{coverage.get('expected_days')} days)")

warnings = shell_d.get("warnings", [])
print(f"  warnings: {len(warnings)}")
for w in warnings:
    print(f"    [{w.get('severity','?')}] {w.get('code','?')}: {w.get('message','?')[:80]}")

with open(os.path.join(OUTPUT_DIR, "shell_response.json"), "w", encoding="utf-8") as f:
    json.dump(shell_d, f, indent=2, default=str, ensure_ascii=False)

# ── 2. Matrix Response ──────────────────────────────────
print("\n[2] Matrix Response")
matrix = build_matrix_response(source_system=SOURCE, grain=GRAIN, date_from=DATE_FROM, date_to=DATE_TO,
                                filters={"country": "peru", "city": "lima"})
matrix_d = matrix.to_dict()

meta = matrix_d.get("metadata", {})
print(f"  source_system: {matrix_d['source_system']}")
print(f"  canonical_ready: {matrix_d['canonical_ready']}")
print(f"  rows: {meta.get('row_count', '?')}")
print(f"  columns: {meta.get('column_count', '?')}")
print(f"  cells: {meta.get('cell_count', '?')}")
print(f"  coverage_pct: {meta.get('coverage_pct', '?')}")
print(f"  source_table: {meta.get('source_table', '?')}")
print(f"  data_date: {meta.get('data_date', '?')}")
print(f"  source_status: {meta.get('source_status', '?')}")

mw = matrix_d.get("warnings", [])
print(f"  warnings: {len(mw)}")
for w in mw:
    print(f"    [{w.get('severity','?')}] {w.get('code','?')}: {w.get('message','?')[:80]}")

cols = matrix_d.get("columns", [])
rows = matrix_d.get("rows", [])
cells_sample = matrix_d.get("cells", [])[:3]
print(f"  columns: {len(cols)} (sample: {[(c.get('period',''), c.get('period_status','')) for c in cols[:3]]})")
print(f"  rows: {len(rows)} (sample: {[r.get('label','') for r in rows[:3]]})")
print(f"  cells: {len(matrix_d.get('cells',[]))}")
for c in cells_sample:
    print(f"    cell: row={c.get('row_id','?')} col={c.get('period','?')} val={c.get('value')} status={c.get('cell_status','?')}")

with open(os.path.join(OUTPUT_DIR, "matrix_response.json"), "w", encoding="utf-8") as f:
    json.dump(matrix_d, f, indent=2, default=str, ensure_ascii=False)

# ── 3. CT Source Data ───────────────────────────────────
print("\n[3] CT Source (ops.real_business_slice_day_fact)")
with get_db() as c:
    cur = c.cursor(cursor_factory=RealDictCursor)

    # Check for exactly 2026-06-06
    cur.execute("""
        SELECT trip_date, COUNT(*) as slices,
               SUM(trips_completed) as trips,
               SUM(revenue_yego_final) as revenue
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
          AND trip_date = '2026-06-06'
        GROUP BY trip_date
    """)
    rows_0606 = [dict(r) for r in cur.fetchall()]
    print(f"  2026-06-06 rows: {len(rows_0606)}")
    for r in rows_0606:
        print(f"    date={r['trip_date']} slices={r['slices']} trips={r['trips']} revenue={r['revenue']}")

    # Check max available date
    cur.execute("""
        SELECT MAX(trip_date) as max_date, MIN(trip_date) as min_date,
               COUNT(DISTINCT trip_date) as date_count
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
    """)
    range_r = dict(cur.fetchone())
    print(f"  Date range: {range_r['min_date']} -> {range_r['max_date']} ({range_r['date_count']} days)")

    # Check last 3 days
    cur.execute("""
        SELECT trip_date, COUNT(*) as slices,
               SUM(trips_completed) as trips
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
          AND trip_date >= '2026-06-04'
        GROUP BY trip_date
        ORDER BY trip_date DESC
    """)
    print(f"  Last days:")
    for r in cur.fetchall():
        d = dict(r)
        print(f"    {d['trip_date']}: {d['slices']} slices, {d['trips']} trips")

    # Check for 2026-05-07 (health showed it earlier)
    cur.execute("""
        SELECT trip_date, COUNT(*) as slices,
               SUM(trips_completed) as trips
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country))='peru' AND LOWER(TRIM(city))='lima'
          AND trip_date = '2026-05-07'
        GROUP BY trip_date
    """)
    may_rows = [dict(r) for r in cur.fetchall()]
    print(f"  2026-05-07 rows: {len(may_rows)}")
    for r in may_rows:
        print(f"    date={r['trip_date']} slices={r['slices']} trips={r['trips']}")

    # Check what today's date actually is (DB perspective)
    cur.execute("SELECT CURRENT_DATE as db_today")
    db_today = dict(cur.fetchone())
    print(f"  DB today: {db_today['db_today']}")

    cur.close()

print(f"\n[output] {OUTPUT_DIR}")
print("Done.")
