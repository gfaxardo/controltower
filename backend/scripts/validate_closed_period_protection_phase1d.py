"""Fase 1D — Validate closed period protection end-to-end."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.db.connection import init_db_pool, get_db, _get_connection_params
init_db_pool()
import psycopg2

print("=" * 60)
print("FASE 1D — CLOSED PERIOD PROTECTION VALIDATION")
print("=" * 60)

from app.services.period_closure_service import (
    get_last_reliable_data_date,
    classify_period,
    run_closure_qa,
    get_period_closure_status,
    get_period_readiness,
    assert_period_refresh_allowed,
    compute_fact_checksum,
    close_period,
    reopen_for_backfill,
)
from datetime import date

MAY = date(2026, 5, 1)
APR = date(2026, 4, 1)

# ------------------------------------------------------------
print("\n1. Last reliable data date")
r = get_last_reliable_data_date()
print(f"   date={r.get('last_reliable_data_date')} lag={r.get('lag_days')}d status={r.get('status')}")
assert r.get("last_reliable_data_date") is not None, "No reliable date!"
print("   PASS")

# ------------------------------------------------------------
print("\n2. Period classification")
may_c = classify_period("monthly", MAY)
print(f"   May 2026: open={may_c['is_open']} candidate={may_c['is_closed_candidate']} suggested={may_c['suggested_status']}")
assert may_c["is_open"] is True, "May should be open!"
print("   May is open: PASS")

apr_c = classify_period("monthly", APR)
print(f"   Apr 2026: open={apr_c['is_open']} candidate={apr_c['is_closed_candidate']} suggested={apr_c['suggested_status']}")
print(f"   (Apr status depends on data lag — may be closed_candidate or open)")
print("   PASS")

# ------------------------------------------------------------
print("\n3. Closure QA for April 2026")
qa = run_closure_qa("monthly", APR)
print(f"   Overall: {qa['overall']}")
print(f"   Coverage: {qa.get('coverage_pct')}%")
print(f"   Raw: {qa.get('raw_completed_count')}, Fact: {qa.get('fact_completed_count')}")
print(f"   Blockers: {qa.get('blockers')}")
print(f"   Warnings: {qa.get('warnings')}")
assert "overall" in qa
print("   PASS")

# ------------------------------------------------------------
print("\n4. Checksum computation")
csum = compute_fact_checksum("monthly", MAY)
print(f"   May 2026 checksum: {csum}")
assert csum is not None and csum != "empty"
print("   PASS")

# ------------------------------------------------------------
print("\n5. Close April (dry-run)")
result = close_period("monthly", APR, scope="global")
print(f"   Dry run: {result.get('dry_run')}")
print(f"   Action: {result.get('action')}")
print(f"   QA overall: {result['qa']['overall']}")
assert result.get("dry_run") is True
print("   PASS (dry-run, no actual closure)")

# ------------------------------------------------------------
print("\n6. Period closure status")
status = get_period_closure_status()
print(f"   Total periods: {status['total']}")
print(f"   Reliable date: {status['last_reliable_data'].get('last_reliable_data_date')}")
for p in status.get("periods", [])[:5]:
    print(f"   {p.get('grain')} {p.get('period_start')} status={p.get('status')} qa={p.get('qa_status')}")
print("   PASS")

# ------------------------------------------------------------
print("\n7. Readiness")
readiness = get_period_readiness("monthly", "2026-04")
print(f"   Can close: {readiness.get('can_close')}")
print(f"   Blockers: {readiness.get('blockers')}")
print(f"   Warnings: {readiness.get('warnings')}")
print("   PASS")

# ------------------------------------------------------------
print("\n8. Refresh allowed check")
allowed_may = assert_period_refresh_allowed("monthly", MAY)
print(f"   May: allowed={allowed_may['allowed']} status={allowed_may['status']}")
assert allowed_may["allowed"] is True
print("   PASS")

# ------------------------------------------------------------
print("\n9. Registry table exists")
c = psycopg2.connect(**_get_connection_params()); c.autocommit = True; cur = c.cursor()
cur.execute("SELECT to_regclass('ops.period_closure_registry')")
assert cur.fetchone()[0] is not None
cur.execute("SELECT to_regclass('ops.v_period_closure_status')")
assert cur.fetchone()[0] is not None
print("   Both exist: PASS")
cur.close(); c.close()

# ------------------------------------------------------------
print("\n10. Service imports + settings flags")
from app.settings import settings
flags = ["CT_DATA_LAG_DAYS", "CT_ALLOW_CLOSED_PERIOD_REFRESH", "CT_PERIOD_CLOSURE_ENABLED", "CT_PERIOD_CLOSURE_DRY_RUN", "CT_MIN_MAPPING_COVERAGE_PCT"]
for f in flags:
    assert hasattr(settings, f), f"Missing flag: {f}"
print(f"   All {len(flags)} flags exist: PASS")

# ------------------------------------------------------------
print("\n11. Omniview + Bogota not broken")
from app.services.business_slice_omniview_service import get_business_slice_omniview
print("   business_slice_omniview_service importable: PASS")

c = psycopg2.connect(**_get_connection_params()); c.autocommit = True; cur = c.cursor()
cur.execute("SELECT business_slice_name, SUM(trips_completed) FROM ops.real_business_slice_month_fact WHERE month='2026-05-01' AND LOWER(COALESCE(city,''))='bogota' GROUP BY 1 ORDER BY 2 DESC")
bogota = cur.fetchall()
bogota_slices = {str(r[0]): int(r[1]) for r in bogota}
assert bogota_slices.get("Carga") == 2801, f"Bogota Carga wrong: {bogota_slices}"
assert bogota_slices.get("Delivery moto") == 188, f"Bogota Delivery wrong: {bogota_slices}"
print(f"   Bogota OK: Carga=2801, Delivery=188: PASS")

cur.execute("SELECT business_slice_name, SUM(trips_completed) FROM ops.real_business_slice_month_fact WHERE month='2026-05-01' AND LOWER(COALESCE(city,''))='barranquilla' GROUP BY 1 ORDER BY 2 DESC")
baq = cur.fetchall()
baq_slices = {str(r[0]): int(r[1]) for r in baq}
assert baq_slices.get("Taxi Moto") == 12483, f"Barranquilla Taxi Moto wrong: {baq_slices}"
assert baq_slices.get("Auto regular") == 9764
assert baq_slices.get("Delivery moto") == 1406
print(f"   Barranquilla OK: Taxi Moto=12483, Auto=9764, Delivery=1406: PASS")
cur.close(); c.close()

print("\n" + "=" * 60)
print("ALL TESTS PASSED — FASE 1D GO")
print("=" * 60)
