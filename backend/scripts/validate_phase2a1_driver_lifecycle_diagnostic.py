"""
FASE 2A.1 — DRIVER LIFECYCLE DIAGNOSTIC ENGINE QA

Valida el motor de diagnostico deterministico de ciclo de vida y riesgo.
Ejecuta endpoint checks, validacion de contratos, reglas del negocio.

Uso:
    cd backend && python scripts/validate_phase2a1_driver_lifecycle_diagnostic.py

Veredicto: GO | CONDITIONAL GO | NO-GO
"""
import sys, os, time, logging
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
logging.basicConfig(level=logging.WARNING)

from app.db.connection import init_db_pool
init_db_pool()

R = []  # results

P = "PASS"; F = "FAIL"; W = "WARN"
BLUE = "\033[94m"; GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"
BOLD = "\033[1m"; RESET = "\033[0m"

def chk(name, condition, detail="", severity="critical", rec=""):
    s = P if condition else F
    R.append({"t": name, "s": s, "d": str(detail)[:200], "severity": severity, "rec": rec})
    sym = f"{GREEN}[PASS]{RESET}" if condition else f"{RED}[FAIL]{RESET}"
    tag = ""
    if not condition and severity == "critical":
        tag = f" {RED}CRITICAL{RESET}"
    elif severity == "warning":
        tag = f" {YELLOW}WARNING{RESET}"
    print(f"  {sym} {name}{tag}")
    if detail:
        print(f"       {detail}")

VALID_STATES = {"CHURNED", "DORMANT", "REACTIVATED", "NEW", "AT_RISK", "DECLINING", "GROWING", "STABLE", "ACTIVATING"}
VALID_RISKS = {"HIGH", "MEDIUM", "LOW"}

print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{BOLD}  FASE 2A.1 -- DRIVER LIFECYCLE DIAGNOSTIC ENGINE QA{RESET}")
print(f"{'='*60}")

# ---- A. Import check ----
print(f"\n{BOLD}{BLUE}=== A. IMPORTS{RESET}")
try:
    from app.services.driver_lifecycle_diagnostic_service import (
        get_diagnostic_summary, get_diagnostic_funnel,
        get_diagnostic_risk_list, get_diagnostic_cohorts_basic,
    )
    chk("A.1 Diagnostic service importable", True)
except Exception as e:
    chk("A.1 Diagnostic service importable", False, str(e), "critical")

try:
    from app.routers.driver_lifecycle_diagnostic import router
    chk("A.2 Diagnostic router importable", True)
except Exception as e:
    chk("A.2 Diagnostic router importable", False, str(e), "critical")

# ---- B. GET /driver-lifecycle/summary ----
print(f"\n{BOLD}{BLUE}=== B. ENDPOINT: /driver-lifecycle/summary{RESET}")
try:
    result = get_diagnostic_summary()
    required_fields = [
        "total_drivers_seen", "active_7d", "active_28d",
        "new_drivers", "activating_drivers", "stable_drivers", "growing_drivers",
        "declining_drivers", "at_risk_drivers", "dormant_drivers", "churned_drivers",
        "reactivated_drivers", "high_risk", "medium_risk", "low_risk",
        "leakage_rate", "retention_rate",
    ]
    missing = [f for f in required_fields if f not in result]
    chk("B.1 Summary returns all required fields", len(missing) == 0,
        f"Missing: {missing}" if missing else f"All {len(required_fields)} present")
    chk("B.2 Summary has data (total > 0)", result.get("total_drivers_seen", 0) > 0,
        f"total={result.get('total_drivers_seen')}")
    # leak/retention between 0-100
    lr = result.get("leakage_rate", -1)
    rr = result.get("retention_rate", -1)
    chk("B.3 Leakage rate 0-100", 0 <= lr <= 100, f"leakage={lr}%")
    chk("B.4 Retention rate 0-100", 0 <= rr <= 100, f"retention={rr}%")
except Exception as e:
    chk("B Summary endpoint", False, str(e), "critical")

# ---- C. GET /driver-lifecycle/funnel ----
print(f"\n{BOLD}{BLUE}=== C. ENDPOINT: /driver-lifecycle/funnel{RESET}")
try:
    result = get_diagnostic_funnel()
    layers = ["input_layer", "retained_layer", "risk_layer", "leakage_layer"]
    for layer in layers:
        chk(f"C.{layer} present in funnel", layer in result,
            f"Has keys: {list(result.get(layer, {}).keys())[:4]}" if layer in result else "missing",
            severity="warning")
    chk("C.5 All 4 funnel layers present", all(l in result for l in layers),
        f"Present: {[l for l in layers if l in result]}")
except Exception as e:
    chk("C Funnel endpoint", False, str(e), "critical")

# ---- D. GET /driver-lifecycle/risk-list ----
print(f"\n{BOLD}{BLUE}=== D. ENDPOINT: /driver-lifecycle/risk-list{RESET}")
try:
    result = get_diagnostic_risk_list(limit=50)
    chk("D.1 Risk-list returns list", isinstance(result, list), f"Type: {type(result).__name__}")
    chk("D.2 Risk-list has entries", len(result) > 0, f"Count: {len(result)}")

    if result:
        # Check field presence
        dr = result[0]
        required = ["driver_id", "country", "city", "lifecycle_state", "risk_level",
                     "rule_reason", "first_trip_date", "last_trip_date",
                     "days_since_last_trip", "rolling_7d_trips", "baseline_trips_28d", "decline_pct"]
        missing = [f for f in required if f not in dr]
        chk("D.3 Each risk-list row has all fields", len(missing) == 0,
            f"Missing: {missing}" if missing else "all present")

        # Valid states
        states = {d.get("lifecycle_state") for d in result if d.get("lifecycle_state")}
        invalid_states = states - VALID_STATES
        chk("D.4 All lifecycle_states in catalog", len(invalid_states) == 0,
            f"Invalid: {invalid_states}" if invalid_states else f"Valid: {states}")

        # Valid risk levels
        risks = {d.get("risk_level") for d in result if d.get("risk_level")}
        invalid_risks = risks - VALID_RISKS
        chk("D.5 All risk_levels in {HIGH,MEDIUM,LOW}", len(invalid_risks) == 0,
            f"Invalid: {invalid_risks}" if invalid_risks else f"Valid: {risks}")

        # Non-negative
        neg_days = any((d.get("days_since_last_trip") or 0) < 0 for d in result)
        chk("D.6 days_since_last_trip not negative", not neg_days,
            "has negative values" if neg_days else "all >= 0")

        neg_7d = any((d.get("rolling_7d_trips") or 0) < 0 for d in result)
        chk("D.7 rolling_7d_trips not negative", not neg_7d,
            "has negative values" if neg_7d else "all >= 0")

        neg_base = any((d.get("baseline_trips_28d") or 0) < 0 for d in result)
        chk("D.8 baseline_trips_28d not negative", not neg_base,
            "has negative values" if neg_base else "all >= 0")
except Exception as e:
    chk("D Risk-list endpoint", False, str(e), "critical")

# ---- E. GET /driver-lifecycle/cohorts-basic ----
print(f"\n{BOLD}{BLUE}=== E. ENDPOINT: /driver-lifecycle/cohorts-basic{RESET}")
try:
    result = get_diagnostic_cohorts_basic()
    chk("E.1 Cohorts returns list", isinstance(result, list), f"Type: {type(result).__name__}, count={len(result)}")
    if result:
        cr = result[0]
        cohort_fields = ["cohort", "drivers_started", "retained_7d", "retained_14d", "retained_30d",
                          "retention_7d_pct", "retention_14d_pct", "retention_30d_pct"]
        missing = [f for f in cohort_fields if f not in cr]
        chk("E.2 Cohort row has all fields", len(missing) == 0,
            f"Missing: {missing}" if missing else "all present")
        # Retention % 0-100
        r7 = cr.get("retention_7d_pct", -1)
        chk("E.3 retention_7d_pct 0-100", 0 <= r7 <= 100, f"{r7}%")
except Exception as e:
    chk("E Cohorts endpoint", False, str(e), "critical")

# ---- F. Filtered queries ----
print(f"\n{BOLD}{BLUE}=== F. FILTERED ENDPOINTS{RESET}")
try:
    result = get_diagnostic_summary(country="peru")
    chk("F.1 Summary filtered by country=peru", result.get("total_drivers_seen", 0) >= 0,
        f"total={result.get('total_drivers_seen')}")

    risk_list = get_diagnostic_risk_list(risk_level="HIGH", limit=10)
    chk("F.2 Risk-list filtered by risk_level=HIGH", isinstance(risk_list, list),
        f"Count: {len(risk_list)}")

    state_list = get_diagnostic_risk_list(lifecycle_state="CHURNED", limit=10)
    chk("F.3 Risk-list filtered by lifecycle_state=CHURNED", isinstance(state_list, list),
        f"Count: {len(state_list)}")
    if state_list:
        all_churned = all(d.get("lifecycle_state") == "CHURNED" for d in state_list)
        chk("F.4 All filtered results are CHURNED", all_churned,
            "some not CHURNED" if not all_churned else "all CHURNED")
except Exception as e:
    chk("F Filtered queries", False, str(e), "warning")

# ---- G. Omniview Matrix not broken ----
print(f"\n{BOLD}{BLUE}=== G. OMNIVIEW MATRIX INTEGRITY{RESET}")
try:
    from app.services.business_slice_omniview_service import get_business_slice_omniview
    result = get_business_slice_omniview(
        granularity="monthly", period="2026-04", limit_rows=5
    )
    chk("G.1 Omniview Matrix still responds", bool(result and result.get("rows") is not None),
        f"Rows: {len(result.get('rows', []))}" if result else "No response")
except Exception as e:
    chk("G.1 Omniview Matrix integrity", False, f"Exception: {e}", "critical",
        rec="Omniview may be broken by diagnostic engine changes.")

# ---- H. Plan vs Real not mixed ----
print(f"\n{BOLD}{BLUE}=== H. PLAN VS REAL INTEGRITY{RESET}")
try:
    from app.services.plan_vs_real_service import get_plan_vs_real_monthly
    result = get_plan_vs_real_monthly(month="2026-04", use_canonical=True)
    chk("H.1 Plan vs Real still responds", isinstance(result, list),
        f"Return type: {type(result).__name__}, rows: {len(result)}")
except Exception as e:
    chk("H.1 Plan vs Real integrity", False, f"Exception: {e}", "critical",
        rec="Plan vs Real may be broken.")

# ---- I. Performance ----
print(f"\n{BOLD}{BLUE}=== I. PERFORMANCE{RESET}")
try:
    t0 = time.time()
    _ = get_diagnostic_summary()
    elapsed = (time.time() - t0) * 1000
    ok = elapsed < 30000  # 30s
    chk(f"I.1 Summary response time ({elapsed:.0f}ms)", ok,
        f"{elapsed:.0f}ms " + ("OK" if ok else ">30s threshold"),
        severity="warning")

    t0 = time.time()
    _ = get_diagnostic_risk_list(limit=50)
    elapsed2 = (time.time() - t0) * 1000
    ok2 = elapsed2 < 30000
    chk(f"I.2 Risk-list response time ({elapsed2:.0f}ms)", ok2,
        f"{elapsed2:.0f}ms " + ("OK" if ok2 else ">30s threshold"),
        severity="warning")
except Exception as e:
    chk("I Performance", False, str(e), "warning")

# ---- VEREDICTO ----
print(f"\n{BOLD}{'='*60}{RESET}")
print(f"{BOLD}  VEREDICTO FINAL{RESET}")
print(f"{'='*60}")

total = len(R)
passed = sum(1 for r in R if r["s"] == P)
failed = sum(1 for r in R if r["s"] == F)
critical_failed = sum(1 for r in R if r["s"] == F and r["severity"] == "critical")

print(f"\n  Total validations: {total}")
print(f"  {GREEN}PASS: {passed}{RESET}")
print(f"  {RED}FAIL: {failed}{RESET}  ({RED}CRITICAL: {critical_failed}{RESET})")

if failed:
    print(f"\n  {RED}FAILURES:{RESET}")
    for r in R:
        if r["s"] == F:
            tag = "CRITICAL" if r["severity"] == "critical" else "WARNING"
            print(f"    [{tag}] {r['t']}")
            if r.get("rec"):
                print(f"           -> {r['rec']}")

print()
if critical_failed == 0 and failed == 0:
    print(f"  {GREEN}{BOLD}VEREDICTO: GO{RESET}")
    exit_code = 0
elif critical_failed == 0:
    print(f"  {YELLOW}{BOLD}VEREDICTO: CONDITIONAL GO{RESET}")
    exit_code = 1
else:
    print(f"  {RED}{BOLD}VEREDICTO: NO-GO{RESET}")
    exit_code = 2

print(f"\n{BOLD}{'='*60}{RESET}\n")
sys.exit(exit_code)
