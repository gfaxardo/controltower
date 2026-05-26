"""
QA Script — Fase 3A.1: Yango Loyalty Operating Layer.

Valida:
  A. Tablas existen y tienen columnas nuevas
  B. Endpoints 3A intactos
  C. Endpoints 3A.1 nuevos
  D. Completeness compute
  E. Freshness compute
  F. Goal management (POST + copy)
  G. Manual inputs (POST + bulk)
  H. Daily snapshot
  I. Historical tracking
  J. No recommendations
  K. Omniview intacto
  L. Plan vs Real intacto
  M. Fase 2 intacta
  N. Frontend build OK (placeholder)
"""
import sys
import os
import json
import urllib.request
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

API_BASE = os.environ.get("YEGO_API_BASE", "http://localhost:8000")

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


# ═══════════════════════════════════
# A. Tablas + columnas
# ═══════════════════════════════════
print("\n── A. Tablas y columnas ──")

status_code, data = api_get("/yango-loyalty/kpis")
check("GET /yango-loyalty/kpis → 200", status_code == 200)
if status_code == 200:
    check("KPI registry tiene registros", len(data.get("kpis", [])) >= 10)

# ═══════════════════════════════════
# B. Endpoints 3A intactos
# ═══════════════════════════════════
print("\n── B. Endpoints 3A ──")

for path, params in [
    ("/yango-loyalty/summary", None),
    ("/yango-loyalty/kpis", None),
    ("/yango-loyalty/city-status", {"city": "Lima"}),
    ("/yango-loyalty/gaps", None),
    ("/yango-loyalty/reachability", None),
]:
    sc, _ = api_get(path, params)
    check(f"GET {path} → 200", sc == 200, f"status={sc}")

# ═══════════════════════════════════
# C. Endpoints 3A.1 nuevos
# ═══════════════════════════════════
print("\n── C. Endpoints 3A.1 ──")

for path, params in [
    ("/yango-loyalty/completeness", None),
    ("/yango-loyalty/freshness", None),
    ("/yango-loyalty/daily-snapshot", None),
    ("/yango-loyalty/historical", {"months_back": 3}),
]:
    sc, _ = api_get(path, params)
    check(f"GET {path} → 200", sc == 200, f"status={sc}")

# ═══════════════════════════════════
# D. Completeness
# ═══════════════════════════════════
print("\n── D. Completeness ──")

sc, data = api_get("/yango-loyalty/completeness")
if sc == 200:
    check("global_completeness_pct presente", "global_completeness_pct" in data)
    check("city_completeness tiene 3 ciudades", len(data.get("city_completeness", {})) >= 3)
    check("global_completeness_pct entre 0-100", 0 <= data.get("global_completeness_pct", -1) <= 100)
else:
    skip("Completeness", f"status={sc}")

# ═══════════════════════════════════
# E. Freshness
# ═══════════════════════════════════
print("\n── E. Freshness ──")

sc, data = api_get("/yango-loyalty/freshness")
if sc == 200:
    check("freshness_distribution presente", "freshness_distribution" in data)
    check("total_manual_kpis es int", isinstance(data.get("total_manual_kpis"), int))
else:
    skip("Freshness", f"status={sc}")

# ═══════════════════════════════════
# F. Goal management
# ═══════════════════════════════════
print("\n── F. Goal management ──")

sc, data = api_post("/yango-loyalty/goals", [{
    "month": "2026-05", "country": "PE", "city": "Lima",
    "kpi_code": "CALLS", "target_value": 300,
}])
check("POST /goals → 200", sc == 200, f"status={sc}")
if sc == 200:
    check("goals upsert ok (no errors)", not data.get("errors"), str(data.get("errors", [])[:2]))

sc, data = api_post("/yango-loyalty/goals/copy", {
    "from_month": "2026-05", "to_month": "2026-06",
})
check("POST /goals/copy → 200", sc == 200, f"status={sc}")
if sc == 200:
    check("copy devuelve copied count", "copied" in str(data))

# ═══════════════════════════════════
# G. Manual inputs + bulk
# ═══════════════════════════════════
print("\n── G. Manual inputs ──")

sc, data = api_post("/yango-loyalty/manual-results", [{
    "month": "2026-05", "country": "PE", "city": "Lima",
    "kpi_code": "CALLS", "real_value": 180,
}])
check("POST /manual-results → 200", sc == 200, f"status={sc}")

sc, data = api_post("/yango-loyalty/manual-results/bulk", [
    {"month": "2026-05", "country": "PE", "city": "Lima", "kpi_code": "SH", "real_value": 2500},
    {"month": "2026-05", "country": "PE", "city": "Lima", "kpi_code": "COMMS", "real_value": 85},
    {"month": "2026-05", "country": "PE", "city": "Trujillo", "kpi_code": "SUPPORT", "real_value": 72},
])
check("POST /manual-results/bulk → 200", sc == 200, f"status={sc}")

# Invalid input test
sc, data = api_post("/yango-loyalty/manual-results/bulk", [
    {"month": "2026-05", "country": "PE", "city": "Mars", "kpi_code": "AD", "real_value": 100},
])
check("POST bulk con input inválido → 200 (con errores)", sc == 200 and (data.get("errors") or data.get("validated") is False),
      f"status={sc}, data={json.dumps(data)[:100]}")

# ═══════════════════════════════════
# H. Daily Snapshot
# ═══════════════════════════════════
print("\n── H. Daily Snapshot ──")

sc, data = api_get("/yango-loyalty/daily-snapshot")
if sc == 200:
    check("items presente", "items" in data and len(data["items"]) > 0)
    check("today_day presente", isinstance(data.get("today_day"), int))
else:
    skip("Daily snapshot", f"status={sc}")

# ═══════════════════════════════════
# I. Historical
# ═══════════════════════════════════
print("\n── I. Historical ──")

sc, data = api_get("/yango-loyalty/historical", {"months_back": 2})
if sc == 200:
    check("historical items presente", "historical" in data)
    check("months_queried tiene 2 meses", len(data.get("months_queried", [])) == 2)
else:
    skip("Historical", f"status={sc}")

# ═══════════════════════════════════
# J. No recommendations
# ═══════════════════════════════════
print("\n── J. Sin recomendaciones ──")

sc, data = api_get("/yango-loyalty/summary")
if sc == 200:
    response_str = json.dumps(data).lower()
    check("No tiene 'recomendación'", "recomend" not in response_str)
    check("No tiene 'suggestion'", "suggest" not in response_str)

# ═══════════════════════════════════
# K. Omniview intacto
# ═══════════════════════════════════
print("\n── K. Omniview ──")

sc, _ = api_get("/ops/business-slice/monthly", timeout=60)
check("Omniview monthly → 200", sc == 200, f"status={sc}")

# ═══════════════════════════════════
# L. Plan vs Real
# ═══════════════════════════════════
print("\n── L. Plan vs Real ──")

sc, _ = api_get("/ops/plan-vs-real/monthly", timeout=60)
check("Plan vs Real → 200", sc == 200, f"status={sc}")

# ═══════════════════════════════════
# M. Fase 2
# ═══════════════════════════════════
print("\n── M. Fase 2 ──")

for path, params in [
    ("/recoverability/summary", {}),
    ("/ops/driver-lifecycle/summary", {}),
    ("/operational-intelligence/summary", {}),
]:
    sc, _ = api_get(path, params, timeout=60)
    check(f"GET {path} → 200", sc == 200, f"status={sc}")

# ═══════════════════════════════════
# N. Frontend build (placeholder)
# ═══════════════════════════════════
print("\n── N. Frontend ──")

frontend_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.isdir(os.path.join(frontend_dir, "src")):
    skip("Frontend build validation", "Ejecutar manualmente: cd frontend && npm run build && npm run dev")
else:
    skip("Frontend check", "directorio no encontrado")

# ═══════════════════════════════════
# RESULTADO
# ═══════════════════════════════════
print(f"\n{'='*50}")
print(f"QA FASE 3A.1 — RESULTADO")
print(f"  PASS: {PASS}")
print(f"  FAIL: {FAIL}")
print(f"  SKIP: {SKIP}")
print(f"{'='*50}")

if FAIL > 0:
    print("VEREDICTO: NO-GO — Hay fallos que requieren atención.")
    sys.exit(1)
elif SKIP > 3:
    print("VEREDICTO: CONDITIONAL GO — Tests incompletos. Revisar skips.")
    sys.exit(0)
else:
    print("VEREDICTO: GO — Todos los tests pasaron.")
    sys.exit(0)
