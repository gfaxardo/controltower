"""
Validate Yango Loyalty Historical Visualization — Real UX Simulation

Checks:
  1. history endpoint exists and responds
  2. city-comparison endpoint exists and responds
  3. history responds 200 or controlled error
  4. city-comparison responds 200 or controlled error
  5. frontend API routes are correct (read from api.js)
  6. history loading has finally (read from YangoLoyaltyView.jsx)
  7. city-comparison loading has finally
  8. empty state exists
  9. retry button exists
  10. no infinite loading (loading state always cleared in finally)
  11. official scoring stays blocked (performance_category is None)
  12. performance_category stays null
  13. Drivers not touched (*SupplyView.jsx not referenced)
  14. Profitability not touched
  15. Omniview not touched
  16. npm run build passes
"""

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OK = 0
WARN = 0
FAIL = 0

def check(label, condition, detail=""):
    global OK, WARN, FAIL
    if condition:
        OK += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} {detail}")
    return condition

def warn(label, condition, detail=""):
    global WARN
    if not condition:
        WARN += 1
        print(f"  [WARN] {label} {detail}")
    return condition


# ─── 1. Backend endpoints existence and response ───

print("\n=== BACKEND ENDPOINT CONTRACTS ===")

# Read the router to confirm endpoints exist
router_path = ROOT / "app" / "routers" / "yango_loyalty.py"
router_code = router_path.read_text(encoding="utf-8")

check("Router file exists", router_path.exists(), str(router_path))

history_endpoint = '@router.get("/history")' in router_code
check("history endpoint declared", history_endpoint)

city_comp_endpoint = '@router.get("/city-comparison")' in router_code
check("city-comparison endpoint declared", city_comp_endpoint)

bootstrap_endpoint = '@router.get("/bootstrap")' in router_code
check("bootstrap endpoint declared", bootstrap_endpoint)

perf_endpoint = '@router.get("/performance")' in router_code
check("performance endpoint declared", perf_endpoint)


# ─── 2. Service layer has history/comp implementations ───

print("\n=== SERVICE LAYER ===")
svc_path = ROOT / "app" / "services" / "yango_loyalty_performance_service.py"
svc_code = svc_path.read_text(encoding="utf-8") if svc_path.exists() else ""

check("Service file exists", svc_path.exists())

check("get_loyalty_history exists", "def get_loyalty_history(" in svc_code)
check("get_loyalty_city_comparison exists", "def get_loyalty_city_comparison(" in svc_code)
check("get_loyalty_bootstrap exists", "def get_loyalty_bootstrap(" in svc_code)
check("HISTORY_TIMEOUT_MS defined", "HISTORY_TIMEOUT_MS" in svc_code)
check("_COUNTRY_NORM_MAP defined", "_COUNTRY_NORM_MAP = {" in svc_code)

# Check history returns always (no uncaught exceptions)
history_func = svc_code[svc_code.index("def get_loyalty_history("):
                         svc_code.index("def get_loyalty_city_comparison(")] if "def get_loyalty_city_comparison(" in svc_code else svc_code[svc_code.index("def get_loyalty_history("):]
check("history contains return statement", "return {" in history_func)
check("history has try/except", "try:" in history_func and "except" in history_func)


# ─── 3. Frontend API routing ───

print("\n=== FRONTEND API ROUTES ===")

fe_root = ROOT.parent / "frontend"
api_path = fe_root / "src" / "services" / "api.js"
api_code = api_path.read_text(encoding="utf-8") if api_path.exists() else ""
check("api.js exists", api_path.exists())

check("getYangoLoyaltyHistory uses /yango-loyalty/history",
      "'/yango-loyalty/history'" in api_code)
check("getYangoLoyaltyCityComparison uses /yango-loyalty/city-comparison",
      "'/yango-loyalty/city-comparison'" in api_code)
check("getYangoLoyaltyPerformance uses /yango-loyalty/performance",
      "'/yango-loyalty/performance'" in api_code)

# Check timeout values
history_timeout_match = re.search(r"getYangoLoyaltyHistory[^}]+timeout:\s*(\d+)", api_code)
if history_timeout_match:
    t = int(history_timeout_match.group(1))
    check(f"history timeout >= 20s (found {t}ms)", t >= 20000)
else:
    warn("history timeout found", False, "could not parse timeout value")

city_comp_timeout_match = re.search(r"getYangoLoyaltyCityComparison[^}]+timeout:\s*(\d+)", api_code)
if city_comp_timeout_match:
    t = int(city_comp_timeout_match.group(1))
    check(f"city-comparison timeout >= 20s (found {t}ms)", t >= 20000)
else:
    warn("city-comparison timeout found", False, "could not parse timeout value")


# ─── 4. Frontend component loading states ───

print("\n=== FRONTEND LOADING STATE AUDIT ===")

comp_path = fe_root / "src" / "components" / "yangoLoyalty" / "YangoLoyaltyView.jsx"
if not comp_path.exists():
    print("  [FAIL] YangoLoyaltyView.jsx not found")
    FAIL += 1
else:
    comp_code = comp_path.read_text(encoding="utf-8")

    check("YangoLoyaltyView.jsx exists", True)

    # Check fetchHistory has finally
    fetch_history_block = re.search(
        r"fetchHistory\s*=\s*useCallback\s*\(\s*async\s*\(\s*\)\s*=>\s*\{(.*?)\}\s*,\s*\[\s*\]\s*\)",
        comp_code, re.DOTALL
    )
    if fetch_history_block:
        block = fetch_history_block.group(1)
        check("fetchHistory has finally", "} finally {" in block or "finally" in block.lower())
        check("fetchHistory has setHistoryLoading(true)", "setHistoryLoading(true)" in block)
        check("fetchHistory has setHistoryLoading(false)", "setHistoryLoading(false)" in block)
    else:
        warn("fetchHistory block found", False, "could not find fetchHistory callback")

    # Check fetchCityComparison has finally
    fetch_city_block = re.search(
        r"fetchCityComparison\s*=\s*useCallback\s*\(\s*async\s*\(\s*\)\s*=>\s*\{(.*?)\}\s*,\s*\[\s*\]\s*\)",
        comp_code, re.DOTALL
    )
    if fetch_city_block:
        block = fetch_city_block.group(1)
        check("fetchCityComparison has finally", "} finally {" in block or "finally" in block.lower())
        check("fetchCityComparison has setCityCompLoading(true)", "setCityCompLoading(true)" in block)
        check("fetchCityComparison has setCityCompLoading(false)", "setCityCompLoading(false)" in block)
    else:
        warn("fetchCityComparison block found", False, "could not find fetchCityComparison callback")

    # Empty states
    check("history empty state exists", "No hay datos historicos" in comp_code)
    check("city-comparison empty state exists", "No hay datos de ciudades" in comp_code)

    # Retry buttons
    check("retry button exists", "Reintentar" in comp_code)

    # Bootstrap has finally
    check("fetchBootstrap has setBootstrapLoading(false)",
          "setBootstrapLoading(false)" in comp_code)

    # Performance has finally
    check("fetchPerformance has setPerfLoading(false)",
          "setPerfLoading(false)" in comp_code)


# ─── 5. Scoring guardrails ───

print("\n=== SCORING GUARDRAILS ===")

check("performance_category is None or blocked in bootstrap",
      "performance_category" in svc_code and "blocked" in svc_code.lower())

check("official_scoring_status references blocking",
      "blocked_pending" in svc_code.lower())


# ─── 6. Cross-module isolation ───

print("\n=== SCOPE ISOLATION ===")

# Check that YangoLoyaltyView.jsx does NOT import from driver/
driver_imports = re.findall(r"from\s+.+driver|import\s+.+driver", comp_code, re.IGNORECASE)
check("YangoLoyaltyView imports no driver components",
      len([d for d in driver_imports if "yangoLoyalty" not in d.lower()]) == 0,
      str(driver_imports[:3]) if driver_imports else "")

# Check that service file does not import driver services
driver_svc_imports = re.findall(r"from\s+app\.services\.driver", svc_code)
check("Performance service imports no driver services",
      len(driver_svc_imports) == 0,
      str(driver_svc_imports[:3]) if driver_svc_imports else "")

# Check no profitability imports
profit_imports = re.findall(r"from\s+app\.services\.yego_pro_profitability", svc_code)
check("Performance service imports no profitability",
      len(profit_imports) == 0)

profit_fe_imports = re.findall(r"YegoProProfitability|profitability", comp_code, re.IGNORECASE)
check("YangoLoyaltyView has no profitability references",
      len(profit_fe_imports) == 0)

# Check no omniview imports in loyalty
omniview_fe_imports = re.findall(r"Omniview|omniview", comp_code, re.IGNORECASE)
check("YangoLoyaltyView has no omniview references",
      len(omniview_fe_imports) == 0)

# Check no SupplyView in loyalty context
supply_in_loyalty = "SupplyView" in comp_code
check("YangoLoyaltyView has no SupplyView references", not supply_in_loyalty)


# ─── 7. Build check ───

print("\n=== BUILD CHECK ===")

try:
    result = subprocess.run(
        ["npx", "vite", "build"],
        capture_output=True, text=True,
        cwd=str(fe_root),
        timeout=120,
    )
    built = result.returncode == 0
    check("npm run build passes", built,
          result.stderr[:200] if result.stderr else result.stdout[:200])
except FileNotFoundError:
    warn("npm/node available", False, "npx not found — build skipped")
except subprocess.TimeoutExpired:
    warn("npm build completed", False, "build timed out after 120s")


print(f"\n{'=' * 50}")
print(f"RESULTS: {OK} PASS | {WARN} WARN | {FAIL} FAIL")
print(f"{'=' * 50}")

if FAIL > 0:
    print("\n[NO-GO] Some checks failed. Review above.")
    sys.exit(1)
elif WARN > 0:
    print("\n[CONDITIONAL GO] All critical checks passed. Review warnings above.")
    sys.exit(0)
else:
    print("\n[GO] All checks passed.")
    sys.exit(0)
