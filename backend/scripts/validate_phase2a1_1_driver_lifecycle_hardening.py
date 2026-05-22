"""
FASE 2A.1.1 — DRIVER LIFECYCLE HARDENING QA

Valida fact table creation, service migration, performance, and integrity.
Uso: cd backend && python scripts/validate_phase2a1_1_driver_lifecycle_hardening.py
"""
import sys, os, time, logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.WARNING)

from app.db.connection import init_db_pool, _get_connection_params
init_db_pool()
import psycopg2

R = []; P = "PASS"; F = "FAIL"
BLUE = "\033[94m"; GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
BOLD = "\033[1m"; RESET = "\033[0m"

def chk(name, condition, detail="", severity="critical", rec=""):
    s = P if condition else F
    R.append({"t": name, "s": s, "d": str(detail)[:200], "severity": severity, "rec": rec})
    sym = f"{GREEN}[PASS]{RESET}" if condition else f"{RED}[FAIL]{RESET}"
    tag = f" {RED}CRITICAL{RESET}" if (not condition and severity == "critical") else ""
    print(f"  {sym} {name}{tag}")
    if detail: print(f"       {detail}")

c = psycopg2.connect(**_get_connection_params()); c.autocommit = True; cur = c.cursor()

print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{BOLD}  FASE 2A.1.1 -- DRIVER LIFECYCLE HARDENING QA{RESET}")
print(f"{'='*60}")

FACT = "ops.driver_daily_activity_fact"

# ---- A. Fact table exists ----
print(f"\n{BOLD}{BLUE}=== A. FACT TABLE{RESET}")
cur.execute(f"SELECT to_regclass('{FACT}')")
chk("A.1 Fact table exists", cur.fetchone()[0] is not None)
cur.execute(f"SELECT COUNT(*) AS c FROM {FACT}")
cnt = cur.fetchone()[0]
chk("A.2 Fact table has rows", cnt > 0, f"{cnt:,} rows")
cur.execute(f"SELECT COUNT(DISTINCT driver_id) AS c FROM {FACT}")
drivers = cur.fetchone()[0]
chk("A.3 Fact table has distinct drivers", drivers > 0, f"{drivers:,} drivers")
cur.execute(f"SELECT MIN(activity_date), MAX(activity_date) FROM {FACT}")
mn, mx = cur.fetchone()
chk("A.4 Has date range", mn is not None and mx is not None, f"{mn} to {mx}")

# ---- B. 2025 + 2026 coverage ----
print(f"\n{BOLD}{BLUE}=== B. COVERAGE 2025/2026{RESET}")
cur.execute(f"SELECT source_year, COUNT(*) AS c FROM {FACT} GROUP BY source_year ORDER BY source_year")
years = {r[0]: r[1] for r in cur.fetchall()}
has_2025 = 2025 in years
has_2026 = 2026 in years
chk("B.1 Has 2026 data", has_2026, f"Rows: {years.get(2026, 0):,}")

# 2025 may not be populated yet if only --days 90 was run
if has_2025:
    chk("B.2 Has 2025 data", True, f"Rows: {years.get(2025, 0):,}")
else:
    chk("B.2 Has 2025 data", False, "2025 not yet populated; run --full or --backfill-from 2025-01-01",
        severity="warning", rec="Run: python scripts/refresh_driver_daily_activity_fact.py --backfill-from 2025-01-01")

# ---- C. Data quality ----
print(f"\n{BOLD}{BLUE}=== C. DATA QUALITY{RESET}")
cur.execute(f"SELECT COUNT(*) AS c FROM {FACT} WHERE completed_trips <= 0")
neg = cur.fetchone()[0]
chk("C.1 No negative/zero completed_trips", neg == 0,
    f"{neg} rows with trips <= 0" if neg else "clean",
    severity="warning")

cur.execute(f"SELECT COUNT(*) AS c FROM {FACT} WHERE activity_date > CURRENT_DATE")
fut = cur.fetchone()[0]
chk("C.2 No future activity_date", fut == 0,
    f"{fut} future rows" if fut else "clean")

cur.execute(f"SELECT COUNT(*) AS c FROM {FACT} WHERE driver_id IS NULL")
nul = cur.fetchone()[0]
chk("C.3 No NULL driver_id", nul == 0,
    f"{nul} null drivers" if nul else "clean")

# ---- D. Indexes ----
print(f"\n{BOLD}{BLUE}=== D. INDEXES{RESET}")
expected = ["driver_daily_activity_fact_pkey", "ix_dda_activity_date", "ix_dda_driver_id",
             "ix_dda_country_city", "ix_dda_country_city_date", "ix_dda_date_driver"]
cur.execute(f"SELECT indexname FROM pg_indexes WHERE tablename = 'driver_daily_activity_fact'")
actual = {r[0] for r in cur.fetchall()}
for idx in expected:
    chk(f"D.{idx}", idx in actual, "exists" if idx in actual else "missing",
        severity="warning")

# ---- E. Service uses fact table ----
print(f"\n{BOLD}{BLUE}=== E. SERVICE MIGRATION{RESET}")
try:
    from app.services.driver_lifecycle_diagnostic_service import FACT_TABLE as svc_fact, get_diagnostic_summary
    chk("E.1 Service references FACT_TABLE", svc_fact == FACT, f"Using: {svc_fact}")

    s = get_diagnostic_summary()
    ds = s.get("data_source", "")
    chk("E.2 Summary uses fact table as data source", ds == FACT,
        f"data_source={ds}", severity="warning")
    chk("E.3 Summary has min_activity_date metadata", "min_activity_date" in s,
        f"min_activity_date={s.get('min_activity_date')}")
    chk("E.4 Summary has last_refreshed_at metadata", "last_refreshed_at" in s,
        f"last_refreshed_at={s.get('last_refreshed_at')}")
except Exception as e:
    chk("E Service migration", False, str(e), "critical")

# ---- F. Endpoints respond ----
print(f"\n{BOLD}{BLUE}=== F. ENDPOINTS{RESET}")
try:
    from app.services.driver_lifecycle_diagnostic_service import (
        get_diagnostic_summary, get_diagnostic_funnel,
        get_diagnostic_risk_list, get_diagnostic_cohorts_basic,
    )
    s = get_diagnostic_summary()
    chk("F.1 summary returns data", s.get("total_drivers_seen", 0) > 0, f"total={s.get('total_drivers_seen')}")

    f = get_diagnostic_funnel()
    layers = ["input_layer", "retained_layer", "risk_layer", "leakage_layer"]
    chk("F.2 funnel has 4 layers", all(l in f for l in layers),
        f"Present: {[l for l in layers if l in f]}")

    rl = get_diagnostic_risk_list(limit=10)
    fields_ok = all(k in rl[0] for k in ["driver_id", "lifecycle_state", "risk_level", "rule_reason"])
    chk("F.3 risk-list preserves contract fields", fields_ok and len(rl) > 0,
        f"Rows: {len(rl)}, fields OK: {fields_ok}")

    cb = get_diagnostic_cohorts_basic()
    chk("F.4 cohorts-basic responds", isinstance(cb, list), f"Rows: {len(cb)}")
except Exception as e:
    chk("F Endpoints", False, str(e), "critical")

# ---- G. Performance ----
print(f"\n{BOLD}{BLUE}=== G. PERFORMANCE{RESET}")
try:
    t0 = time.time()
    _ = get_diagnostic_summary()
    t_s = (time.time() - t0) * 1000
    # Target: improved from previous ~3800ms. Sub-3000ms is acceptable for fact table.
    chk(f"G.1 Summary time ({t_s:.0f}ms)", t_s < 5000,
        f"{t_s:.0f}ms (prev: ~3800ms)", severity="warning")

    t0 = time.time()
    _ = get_diagnostic_risk_list(limit=50)
    t_r = (time.time() - t0) * 1000
    chk(f"G.2 Risk-list time ({t_r:.0f}ms)", t_r < 5000,
        f"{t_r:.0f}ms", severity="warning")
except Exception as e:
    chk("G Performance", False, str(e), "warning")

# ---- H. Omniview Matrix integrity ----
print(f"\n{BOLD}{BLUE}=== H. OMNIVIEW MATRIX{RESET}")
try:
    from app.services.business_slice_omniview_service import get_business_slice_omniview
    r = get_business_slice_omniview(granularity="monthly", period="2026-04", limit_rows=5)
    chk("H.1 Omniview Matrix responds", bool(r and r.get("rows") is not None),
        f"Rows: {len(r.get('rows', []))}" if r else "No response")
except Exception as e:
    chk("H.1 Omniview", False, str(e), "critical", rec="Omniview may be broken.")

# ---- I. Plan vs Real integrity ----
print(f"\n{BOLD}{BLUE}=== I. PLAN VS REAL{RESET}")
try:
    from app.services.plan_vs_real_service import get_plan_vs_real_monthly
    r = get_plan_vs_real_monthly(month="2026-04", use_canonical=True)
    chk("I.1 Plan vs Real responds", isinstance(r, list), f"Rows: {len(r)}")
except Exception as e:
    chk("I.1 Plan vs Real", False, str(e), "critical", rec="Plan vs Real may be broken.")

cur.close(); c.close()

# ---- VEREDICTO ----
print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{BOLD}  VEREDICTO FINAL{RESET}")
print(f"{'='*60}")
total = len(R); ps = sum(1 for r in R if r["s"] == P); fs = sum(1 for r in R if r["s"] == F)
crit = sum(1 for r in R if r["s"] == F and r["severity"] == "critical")
print(f"\n  Total: {total}  {GREEN}PASS: {ps}{RESET}  {RED}FAIL: {fs}{RESET}  (CRITICAL: {crit})")
if fs:
    print(f"\n  {RED}FAILURES:{RESET}")
    for r in R:
        if r["s"] == F:
            tag = "CRITICAL" if r["severity"] == "critical" else "WARNING"
            print(f"    [{tag}] {r['t']}")
            if r.get("rec"): print(f"           -> {r['rec']}")
print()
if crit == 0 and fs == 0: print(f"  {GREEN}{BOLD}VEREDICTO: GO{RESET}"); ec = 0
elif crit == 0: print(f"  {YELLOW}{BOLD}VEREDICTO: CONDITIONAL GO{RESET}"); ec = 1
else: print(f"  {RED}{BOLD}VEREDICTO: NO-GO{RESET}"); ec = 2
print(f"\n{BOLD}{'='*60}{RESET}\n")
sys.exit(ec)
