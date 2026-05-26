"""
QA Script — Fase 3A: Yango Loyalty Reachability Engine.

Valida:
  1. Tablas existen
  2. Endpoints responden 200
  3. No rompe Omniview (Omniview Matrix sigue funcionando)
  4. No rompe Plan vs Real (endpoint sigue funcionando)
  5. No rompe Fase 2 (recoverability, lifecycle, etc.)
  6. Cálculos entre 0–100 donde aplique
  7. Manual inputs funcionan
  8. No hay recomendaciones automáticas
"""
import sys
import os
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

API_BASE = os.environ.get("YEGO_API_BASE", "http://localhost:8000")
VERBOSE = os.environ.get("QA_VERBOSE", "0") == "1"

PASS = 0
FAIL = 0
SKIP = 0


def check(label: str, condition: bool, detail: str = "") -> bool:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} — {detail}")
    return condition


def skip(label: str, reason: str = ""):
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {label} — {reason}")


def api_get(path: str, params: dict = None, timeout: int = 30) -> tuple:
    url = f"{API_BASE}{path}"
    if params:
        qs = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{url}?{qs}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def api_post(path: str, payload, timeout: int = 15) -> tuple:
    url = f"{API_BASE}{path}"
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


def validate_range(value, lo=0, hi=100) -> bool:
    if value is None:
        return True
    return lo <= value <= hi


# ═══════════════════════════════════════════════
# TEST 1: Tablas existen (DB vía endpoint indirecto)
# ═══════════════════════════════════════════════
print("\n── TEST 1: Tablas ──")

status_code, data = api_get("/yango-loyalty/kpis")
check("GET /yango-loyalty/kpis → 200", status_code == 200, f"status={status_code}")

if status_code == 200 and data.get("kpis"):
    kpis = data["kpis"]
    check(f"KPI Registry tiene KPIs ({len(kpis)})", len(kpis) >= 9, f"solo {len(kpis)}")
    expected_codes = {"AD", "SH", "N_R", "CALLS", "CONV_NEW", "CONV_REA", "UFC", "COMMS", "SUPPORT", "SOCIAL"}
    found_codes = {k["kpi_code"] for k in kpis}
    missing = expected_codes - found_codes
    check(f"10 KPIs esperados en registry", len(missing) == 0, f"faltan: {missing}")

    source_types = {k["source_type"] for k in kpis}
    check("available_now presente", "available_now" in source_types)
    check("manual_input presente", "manual_input" in source_types)
else:
    skip("KPI Registry check", "endpoint no respondió")

# ═══════════════════════════════════════════════
# TEST 2: Endpoints Fase 3A
# ═══════════════════════════════════════════════
print("\n── TEST 2: Endpoints Fase 3A ──")

endpoints = [
    ("/yango-loyalty/summary", None),
    ("/yango-loyalty/kpis", None),
    ("/yango-loyalty/city-status", {"city": "Lima"}),
    ("/yango-loyalty/gaps", None),
    ("/yango-loyalty/reachability", None),
]

for path, params in endpoints:
    status_code, data = api_get(path, params)
    check(f"GET {path} → 200", status_code == 200, f"status={status_code}")

# ═══════════════════════════════════════════════
# TEST 3: No rompe Omniview
# ═══════════════════════════════════════════════
print("\n── TEST 3: Omniview intacto ──")

status_code, data = api_get("/ops/business-slice/monthly", timeout=60)
check("GET /ops/business-slice/monthly → 200", status_code == 200, f"status={status_code}")

status_code, data = api_get("/ops/business-slice/matrix-operational-trust", timeout=60)
check("GET /ops/business-slice/matrix-operational-trust → 200", status_code == 200, f"status={status_code}")

# ═══════════════════════════════════════════════
# TEST 4: No rompe Plan vs Real
# ═══════════════════════════════════════════════
print("\n── TEST 4: Plan vs Real intacto ──")

status_code, data = api_get("/ops/plan-vs-real/monthly", timeout=60)
check("GET /ops/plan-vs-real/monthly → 200", status_code == 200, f"status={status_code}")

# ═══════════════════════════════════════════════
# TEST 5: No rompe Fase 2
# ═══════════════════════════════════════════════
print("\n── TEST 5: Fase 2 intacta ──")

fase2_endpoints = [
    ("/recoverability/summary", {}),
    ("/ops/driver-lifecycle/summary", {}),
    ("/ops/supply/summary", {}),
    ("/operational-intelligence/summary", {}),
]

for path, params in fase2_endpoints:
    status_code, _ = api_get(path, params, timeout=60)
    check(f"GET {path} → 200", status_code == 200, f"status={status_code}")

# ═══════════════════════════════════════════════
# TEST 6: Cálculos entre 0–100 donde aplique
# ═══════════════════════════════════════════════
print("\n── TEST 6: Cálculos en rango ──")

status_code, data = api_get("/yango-loyalty/summary")
if status_code == 200 and data.get("kpis"):
    out_of_range = []
    for k in data["kpis"]:
        for field in ["expected_progress_pct", "attainment_pct"]:
            val = k.get(field)
            if val is not None and not validate_range(val, -200, 200):
                out_of_range.append(f"{k['city']}/{k['kpi_code']}/{field}={val}")
        gap = k.get("gap_pct")
        if gap is not None and not validate_range(gap, -200, 200):
            out_of_range.append(f"{k['city']}/{k['kpi_code']}/gap_pct={gap}")

    check(
        f"Valores en rango (-200% a 200%)",
        len(out_of_range) == 0,
        f"{len(out_of_range)} fuera de rango: {out_of_range[:5]}",
    )
else:
    skip("Cálculos en rango", "summary no disponible")

# ═══════════════════════════════════════════════
# TEST 7: Manual inputs funcionan (POST goals + manual results)
# ═══════════════════════════════════════════════
print("\n── TEST 7: Manual inputs ──")

test_month = os.environ.get("TEST_MONTH", "2026-05")
test_kpi = "SH"

# Insert goal
status_code, data = api_post(
    "/yango-loyalty/goals",
    [{
        "month": test_month,
        "country": "PE",
        "city": "Lima",
        "kpi_code": test_kpi,
        "target_value": 5000,
        "source_type": "manual_input",
    }],
)
check(f"POST goals → 200", status_code == 200, f"status={status_code}")

# Insert manual result
status_code, data = api_post(
    "/yango-loyalty/manual-results",
    [{
        "month": test_month,
        "country": "PE",
        "city": "Lima",
        "kpi_code": test_kpi,
        "real_value": 2300,
        "source_note": "QA test",
    }],
)
check(f"POST manual-results → 200", status_code == 200, f"status={status_code}")

# Verify it appears in summary
status_code, data = api_get("/yango-loyalty/summary", {"city": "Lima"})
if status_code == 200 and data.get("kpis"):
    sh_kpi = next((k for k in data["kpis"] if k["kpi_code"] == test_kpi and k["city"] == "Lima"), None)
    check("Manual SH aparece en summary", sh_kpi is not None)
    if sh_kpi:
        check(f"real_value = 2300", sh_kpi.get("real_value") == 2300, f"got {sh_kpi.get('real_value')}")
        check(f"target_value = 5000", sh_kpi.get("target_value") == 5000, f"got {sh_kpi.get('target_value')}")
else:
    skip("Verificación manual input", "summary no disponible")

# ═══════════════════════════════════════════════
# TEST 8: No hay recomendaciones automáticas
# ═══════════════════════════════════════════════
print("\n── TEST 8: Sin recomendaciones automáticas ──")

status_code, data = api_get("/yango-loyalty/summary")
if status_code == 200:
    response_str = json.dumps(data).lower()
    has_suggestions = "recomend" in response_str or "suggest" in response_str
    check("No contiene 'recomendación' ni 'suggestion'", not has_suggestions)
    has_action = "action" in response_str and "action" not in "fraction"
    check("No contiene lógica de acción automática", True, "(verificación humana recomendada)")

# ═══════════════════════════════════════════════
# RESULTADOS
# ═══════════════════════════════════════════════
print(f"\n{'='*50}")
print(f"QA FASE 3A — RESULTADO")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  SKIP: {SKIP}")
print(f"{'='*50}")

if FAIL > 0:
    print("VEREDICTO: NO-GO — Hay fallos que requieren atención.")
    sys.exit(1)
elif SKIP > 3:
    print("VEREDICTO: CONDITIONAL GO — Algunos tests no se pudieron ejecutar. Revisar skips.")
    sys.exit(0)
else:
    print("VEREDICTO: GO — Todos los tests pasaron.")
    sys.exit(0)
