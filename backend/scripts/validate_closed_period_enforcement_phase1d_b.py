"""Fase 1D-B — Closed Period Enforcement Validation."""
import sys, os, logging
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
from app.db.connection import init_db_pool, _get_connection_params
init_db_pool()
import psycopg2
from datetime import date

R = []; P = "PASS"; F = "FAIL"
def chk(n, c, d=""): s = P if c else F; R.append({"t":n,"s":s,"d":str(d)[:200]}); logging.info("%s %s: %s %s", "[PASS]" if c else "[FAIL]", s, n, (f"({d})" if d else ""))

print("=" * 60)
print("FASE 1D-B — CLOSED PERIOD ENFORCEMENT")
print("=" * 60)

from app.services.period_closure_service import (
    check_period_refresh_guard,
    assert_period_refresh_allowed,
    classify_period,
    close_period,
    _ct_dry_run,
)

APR = date(2026, 4, 1)
MAY = date(2026, 5, 1)

# ------------------------------------------------------------
print("\n1. Current state check")
r = classify_period("monthly", MAY)
chk("1.1 May is open", r["is_open"], str(r))
r2 = classify_period("monthly", APR)
chk("1.2 Apr is closed_candidate", r2["is_closed_candidate"], str(r2))
print(f"   CT_DRY_RUN = {_ct_dry_run()}")

# ------------------------------------------------------------
print("\n2. Dry-run: April refresh would warn but not block")
result = check_period_refresh_guard(
    grain="monthly", period_start=APR,
    refresh_name="test_enforcement", trigger_source="manual",
)
chk("2.1 Dry-run allows", result["allowed"] is True, str(result))
chk("2.2 Dry-run flags would_block", result.get("would_block") is True, f"would_block={result.get('would_block')}")

# ------------------------------------------------------------
print("\n3. Dry-run: May refresh is fine")
result_may = check_period_refresh_guard(
    grain="monthly", period_start=MAY,
    refresh_name="test_enforcement", trigger_source="manual",
)
chk("3.1 May allowed", result_may["allowed"] is True)
chk("3.2 May not would_block", result_may.get("would_block") is not True, str(result_may))

# ------------------------------------------------------------
print("\n4. Blocked without reason (dry-run=false simulation)")
# Simulate what would happen in non-dry-run mode
import os
orig_dry = os.environ.get("CT_PERIOD_CLOSURE_DRY_RUN")
os.environ["CT_PERIOD_CLOSURE_DRY_RUN"] = "false"
os.environ["CT_ALLOW_CLOSED_PERIOD_REFRESH"] = "false"
try:
    result_blocked = check_period_refresh_guard(
        grain="monthly", period_start=APR,
        refresh_name="test_enforcement_blocked", trigger_source="manual",
    )
    chk("4.1 Blocked without flag", result_blocked["allowed"] is False, str(result_blocked))
    chk("4.2 Blocked status", result_blocked.get("blocked") is True)
finally:
    if orig_dry is not None:
        os.environ["CT_PERIOD_CLOSURE_DRY_RUN"] = orig_dry
    else:
        os.environ["CT_PERIOD_CLOSURE_DRY_RUN"] = "true"

# ------------------------------------------------------------
print("\n5. Backfill with reason+flag")
os.environ["CT_PERIOD_CLOSURE_DRY_RUN"] = "false"
os.environ["CT_ALLOW_CLOSED_PERIOD_REFRESH"] = "true"
try:
    result_bf = check_period_refresh_guard(
        grain="monthly", period_start=APR,
        refresh_name="test_enforcement_backfill", trigger_source="manual",
        reason="Authorized backfill for QA test",
        allow_closed_flag=True,
    )
    chk("5.1 Backfill allowed", result_bf["allowed"] is True, str(result_bf))
    chk("5.2 Backfill status", result_bf.get("status") == "backfill", str(result_bf))
finally:
    os.environ["CT_PERIOD_CLOSURE_DRY_RUN"] = "true"
    os.environ["CT_ALLOW_CLOSED_PERIOD_REFRESH"] = "false"

# ------------------------------------------------------------
print("\n6. Scripts check")
sdir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
scripts = [
    ("refresh_business_slice_mvs.py", "check_period_refresh_guard", "allow-closed-period"),
    ("refresh_hourly_first_chain.py", "check_period_refresh_guard", "allow-closed-period"),
]
for sf, guard_fn, flag_name in scripts:
    fp = os.path.join(sdir, sf)
    with open(fp, "r", encoding="utf-8") as fh:
        c = fh.read()
    has_g = guard_fn in c
    has_f = flag_name in c
    chk(f"6.{scripts.index((sf,guard_fn,flag_name))+1} {sf} has guard+flag", has_g and has_f, f"guard={has_g} flag={has_f}")

# job file
jp = os.path.join(os.path.dirname(sdir), "app", "services", "business_slice_real_refresh_job.py")
with open(jp, "r", encoding="utf-8") as fh:
    jc = fh.read()
chk("6.3 business_slice_real_refresh_job has guard", "check_period_refresh_guard" in jc)

# pipeline
pp = os.path.join(sdir, "run_pipeline_refresh_and_audit.py")
with open(pp, "r", encoding="utf-8") as fh:
    pc = fh.read()
chk("6.4 pipeline has trigger-source support", "trigger-source" in pc)

# ------------------------------------------------------------
print("\n7. Bogota + Barranquilla intact")
c = psycopg2.connect(**_get_connection_params()); c.autocommit = True; cur = c.cursor()
cur.execute("SELECT business_slice_name, SUM(trips_completed) FROM ops.real_business_slice_month_fact WHERE month='2026-05-01' AND LOWER(COALESCE(city,''))='bogota' GROUP BY 1 ORDER BY 2 DESC")
bg = {str(r[0]): int(r[1]) for r in cur.fetchall()}
chk("7.1 Bogota Carga=2801", bg.get("Carga") == 2801, str(bg))
chk("7.2 Bogota Delivery=188", bg.get("Delivery moto") == 188, str(bg))

cur.execute("SELECT business_slice_name, SUM(trips_completed) FROM ops.real_business_slice_month_fact WHERE month='2026-05-01' AND LOWER(COALESCE(city,''))='barranquilla' GROUP BY 1 ORDER BY 2 DESC")
bq = {str(r[0]): int(r[1]) for r in cur.fetchall()}
chk("7.3 Barranquilla Taxi Moto=12483", bq.get("Taxi Moto") == 12483, str(bq))
chk("7.4 Barranquilla Auto=9764", bq.get("Auto regular") == 9764, str(bq))
chk("7.5 Barranquilla Delivery=1406", bq.get("Delivery moto") == 1406, str(bq))
cur.close(); c.close()

# ------------------------------------------------------------
print("\n8. refresh_run_log has period guard entries")
c = psycopg2.connect(**_get_connection_params()); c.autocommit = True; cur = c.cursor()
cur.execute("SELECT count(*) FROM ops.refresh_run_log WHERE refresh_name LIKE '%period_guard%'")
cnt = cur.fetchone()[0]
chk("8.1 Period guard logged in refresh_run_log", cnt > 0, f"{cnt} entries")
cur.close(); c.close()

# ------------------------------------------------------------
print("\n9. Omniview + service endpoints not broken")
chk("9.1 period_closure_service importable", True)
from app.services.business_slice_omniview_service import get_business_slice_omniview
chk("9.2 omniview_service importable", True)
from app.services.refresh_control_service import get_refresh_status
chk("9.3 refresh_control_service importable", True)

# Summary
print("\n" + "=" * 60)
ps = sum(1 for r in R if r["s"] == P); fs = sum(1 for r in R if r["s"] == F)
for r in R: print(f"  {'[PASS]' if r['s']==P else '[FAIL]'} {r['t']}")
print(f"\n{ps}/{len(R)} PASS, {fs} FAIL — {'GO' if fs==0 else 'NO-GO'}")
if fs: [print(f"  [FAIL] {r['t']}: {r['d']}") for r in R if r['s']==F]
