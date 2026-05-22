"""
QA Script — Fase 2B: Operational Behavioral Intelligence
Valida integridad del servicio, router y respuestas de endpoints.
NO modifica datos. Solo consulta GET.

Uso:
    cd backend
    python -m scripts.validate_phase2b_operational_behavioral_intelligence

Veredicto: GO / CONDITIONAL GO / NO-GO
"""
from __future__ import annotations

import json
import sys
import time
import os
import requests

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8000")
VALIDATION_ID = "phase2b_operational_behavioral_intelligence"

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results: list[dict] = []


def check(name: str, condition: bool, detail: str = "", warn: bool = False) -> bool:
    status = WARN if warn else (PASS if condition else FAIL)
    results.append({"check": name, "status": status, "detail": detail})
    if not condition and not warn:
        print(f"  [{status}] {name}: {detail}")
    else:
        print(f"  [{status}] {name}")
    return condition


def get(path: str, params: dict = None, timeout: int = 90) -> tuple[int, dict | str]:
    url = f"{BASE_URL}{path}"
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        try:
            body = resp.json()
        except Exception:
            body = resp.text[:500]
        return resp.status_code, body
    except requests.exceptions.ConnectionError:
        return 0, f"CONNECTION_ERROR: No se pudo conectar a {BASE_URL}"
    except requests.exceptions.Timeout:
        return 0, "TIMEOUT"
    except Exception as e:
        return 0, str(e)


def main():
    print("=" * 60)
    print("QA: Fase 2B — Operational Behavioral Intelligence")
    print(f"Validación ID: {VALIDATION_ID}")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    all_pass = True
    has_warnings = False

    # ═══ A. Router importado en main.py ═══
    print("\n--- A. Router importado en main.py ---")
    try:
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app", "main.py"
        )
        with open(main_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        router_imported = "operational_behavioral_intelligence" in content
        router_included = "operational_behavioral_intelligence.router" in content
        check("A.1 Import en main.py", router_imported, main_py_path)
        check("A.2 include_router en main.py", router_included, main_py_path)
    except Exception as e:
        check("A.1 Import en main.py", False, str(e))
        all_pass = False

    # ═══ B. SQL facts existen ═══
    print("\n--- B. SQL Facts ---")
    sql_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "sql", "phase2b_operational_intelligence_build.sql"
    )
    check("B.1 Build SQL existe", os.path.exists(sql_path), sql_path)
    if os.path.exists(sql_path):
        with open(sql_path, "r", encoding="utf-8") as f:
            sql_content = f.read()
        check("B.2 driver_trip_behavior_fact en SQL", "ops.driver_trip_behavior_fact" in sql_content)
        check("B.3 driver_session_fact en SQL", "ops.driver_session_fact" in sql_content)
        check("B.4 driver_zone_behavior_fact en SQL", "ops.driver_zone_behavior_fact" in sql_content)

    # ═══ C. Service existe ═══
    print("\n--- C. Service ---")
    service_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app", "services", "operational_behavioral_intelligence_service.py"
    )
    check("C.1 Service file existe", os.path.exists(service_path), service_path)
    if os.path.exists(service_path):
        with open(service_path, "r", encoding="utf-8") as f:
            svc_content = f.read()
        check("C.2 get_operational_summary definida", "def get_operational_summary" in svc_content)
        check("C.3 get_efficiency_analytics definida", "def get_efficiency_analytics" in svc_content)
        check("C.4 get_session_analytics definida", "def get_session_analytics" in svc_content)
        check("C.5 get_zone_analytics definida", "def get_zone_analytics" in svc_content)
        check("C.6 get_time_patterns definida", "def get_time_patterns" in svc_content)
        check("C.7 get_pre_churn_signals definida", "def get_pre_churn_signals" in svc_content)
        check("C.8 get_operational_archetypes definida", "def get_operational_archetypes" in svc_content)
        check("C.9 get_top_vs_churned definida", "def get_top_vs_churned" in svc_content)
        # Verificar que NO hay recomendaciones automáticas
        check("C.10 NO recomendaciones automáticas (suggestion)", "sugerir" not in svc_content.lower() and "recommend" not in svc_content.lower(),
              "El servicio no debe generar recomendaciones", warn=True)
        check("C.11 NO IA/ML", "sklearn" not in svc_content.lower() and "tensorflow" not in svc_content.lower() and "model.predict" not in svc_content.lower(),
              "El servicio no debe usar IA", warn=True)

    # ═══ D. Router existe ═══
    print("\n--- D. Router ---")
    router_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "app", "routers", "operational_behavioral_intelligence.py"
    )
    check("D.1 Router file existe", os.path.exists(router_path), router_path)
    if os.path.exists(router_path):
        with open(router_path, "r", encoding="utf-8") as f:
            rtr_content = f.read()
        check("D.2 Prefijo /operational-intelligence", "/operational-intelligence" in rtr_content)
        check("D.3 Endpoint /summary", "/summary" in rtr_content)
        check("D.4 Endpoint /efficiency", "/efficiency" in rtr_content)
        check("D.5 Endpoint /sessions", "/sessions" in rtr_content)
        check("D.6 Endpoint /zones", "/zones" in rtr_content)
        check("D.7 Endpoint /time-patterns", "/time-patterns" in rtr_content)
        check("D.8 Endpoint /pre-churn-signals", "/pre-churn-signals" in rtr_content)
        check("D.9 Endpoint /archetypes", "/archetypes" in rtr_content)
        check("D.10 Endpoint /top-vs-churned", "/top-vs-churned" in rtr_content)

    # ═══ E. Endpoints responden ═══
    print("\n--- E. Endpoints responden ---")
    endpoints_to_check = [
        ("/operational-intelligence/summary", {"period_days": 28}),
        ("/operational-intelligence/efficiency", {"period_days": 28}),
        ("/operational-intelligence/sessions", {"period_days": 28}),
        ("/operational-intelligence/zones", {"period_days": 28}),
        ("/operational-intelligence/time-patterns", {"period_days": 28}),
        ("/operational-intelligence/pre-churn-signals", {"period_days": 56}),
        ("/operational-intelligence/archetypes", {"period_days": 28}),
        ("/operational-intelligence/top-vs-churned", {"period_days": 28}),
    ]

    endpoint_statuses = {}
    for path, params in endpoints_to_check:
        start = time.time()
        code, body = get(path, params)
        elapsed = round((time.time() - start) * 1000)
        ok = 200 <= code < 300 if isinstance(code, int) else False
        check(
            f"E.{len([r for r in results if r['check'].startswith('E.')]) + 1}  GET {path} -> {code} ({elapsed}ms)",
            ok,
            str(body)[:200] if not ok else ""
        )
        endpoint_statuses[path] = {"code": code, "ok": ok, "elapsed_ms": elapsed}
        if not ok and code == 0:
            all_pass = False
        elif elapsed > 30000:
            results[-1]["detail"] = f"LENTO: {elapsed}ms > 30s"
            if results[-1]["status"] == PASS:
                results[-1]["status"] = WARN

    # ═══ F. No rompe lifecycle ═══
    print("\n--- F. Lifecycle intacto ---")
    lifecycle_code, lifecycle_body = get("/ops/driver-lifecycle/monthly", {"from": "2026-04-22", "to": "2026-05-22"}, timeout=60)
    check("F.1 Lifecycle monthly responde", 200 <= lifecycle_code < 300 if isinstance(lifecycle_code, int) else False,
          f"HTTP {lifecycle_code}")
    if isinstance(lifecycle_body, dict):
        check("F.2 Lifecycle tiene kpis", "kpis" in lifecycle_body or "data" in lifecycle_body or "periods" in lifecycle_body,
              "La respuesta debe contener datos", warn=True)

    # ═══ G. No rompe benchmarking ═══
    print("\n--- G. Benchmarking intacto ---")
    bench_code, bench_body = get("/driver-behavior/summary", {"period_days": 28}, timeout=60)
    check("G.1 Benchmarking summary responde", 200 <= bench_code < 300 if isinstance(bench_code, int) else False,
          f"HTTP {bench_code}")

    # ═══ H. No rompe pattern diagnosis ═══
    print("\n--- H. Pattern Diagnosis intacto ---")
    pat_code, pat_body = get("/behavioral-patterns/summary", {"period_days": 28}, timeout=60)
    check("H.1 Patterns summary responde", 200 <= pat_code < 300 if isinstance(pat_code, int) else False,
          f"HTTP {pat_code}")

    # ═══ I. No rompe Omniview ═══
    print("\n--- I. Omniview intacto ---")
    omni_code, omni_body = get("/ops/business-slice/monthly", {"month": 5, "year": 2026}, timeout=60)
    check("I.1 Omniview monthly responde", 200 <= omni_code < 300 if isinstance(omni_code, int) else False,
          f"HTTP {omni_code}")

    # ═══ J. No rompe Plan vs Real ═══
    print("\n--- J. Plan vs Real intacto ---")
    pvr_code, pvr_body = get("/ops/plan-vs-real/monthly", {"month": "2026-05"}, timeout=60)
    check("J.1 Plan vs Real responde", 200 <= pvr_code < 300 if isinstance(pvr_code, int) else False,
          f"HTTP {pvr_code}")

    # ═══ K. Frontend files existen ═══
    print("\n--- K. Frontend ---")
    fe_dashboard = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "frontend", "src", "components", "operationalIntelligence",
        "OperationalBehavioralIntelligenceDashboard.jsx"
    )
    fe_dashboard = os.path.normpath(fe_dashboard)
    check("K.1 Dashboard existe", os.path.exists(fe_dashboard), fe_dashboard)

    fe_nav = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "frontend", "src", "config", "controlTowerNavigationRegistry.js"
    )
    fe_nav = os.path.normpath(fe_nav)
    if os.path.exists(fe_nav):
        with open(fe_nav, "r", encoding="utf-8") as f:
            nav_content = f.read()
        check("K.2 Navigation registry actualizado", "drivers_operational_intelligence" in nav_content)

    fe_app = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "..", "frontend", "src", "App.jsx"
    )
    fe_app = os.path.normpath(fe_app)
    if os.path.exists(fe_app):
        with open(fe_app, "r", encoding="utf-8") as f:
            app_content = f.read()
        check("K.3 App.jsx actualizado", "drivers_operational_intelligence" in app_content)

    # ═══ L. Validación de contenido semántico ═══
    print("\n--- L. Validación semántica (endpoint /summary) ---")
    sum_code, sum_body = get("/operational-intelligence/summary", {"period_days": 28}, timeout=60)
    if isinstance(sum_body, dict):
        check("L.1 summary tiene campo 'summary'", "summary" in sum_body)
        check("L.2 summary tiene campo 'source'", "source" in sum_body)
        check("L.3 available_objects en source", "available_objects" in sum_body.get("source", {}), warn=True)
        check("L.4 missing_columns en source", "missing_columns" in sum_body.get("source", {}), warn=True)
        # Verificar que no hay recomendaciones en la respuesta
        body_str = json.dumps(sum_body).lower()
        check("L.5 NO recomendaciones en summary", "recomend" not in body_str and "sugerir" not in body_str,
              "La respuesta no debe contener recomendaciones", warn=True)

    # ═══ M. Validación archetypes ═══
    print("\n--- M. Archetypes ---")
    arch_code, arch_body = get("/operational-intelligence/archetypes", {"period_days": 28}, timeout=60)
    if isinstance(arch_body, dict):
        check("M.1 Archetypes tiene distribution", "distribution" in arch_body)
        check("M.2 Archetypes tiene classification_rules", "classification_rules" in arch_body)
        check("M.3 Archetypes tiene reference_thresholds", "reference_thresholds" in arch_body)
        if "distribution" in arch_body:
            dist = arch_body["distribution"]
            check("M.4 Al menos un archetype con >0", sum(dist.values()) > 0, str(dist), warn=True)

    # ═══ N. Performance check ═══
    print("\n--- N. Performance ---")
    slow_endpoints = {k: v for k, v in endpoint_statuses.items() if v.get("elapsed_ms", 0) > 30000}
    if slow_endpoints:
        for path, info in slow_endpoints.items():
            check(f"N.1 Performance {path}", False, f"{info['elapsed_ms']}ms > 30s")
        all_pass = False
    else:
        check("N.1 Todos endpoints < 30s", True)

    # ═══ O. No hay recomendaciones en ningún endpoint ═══
    print("\n--- O. No recommendations audit ---")
    recommendation_keywords = ["recomendación", "recomendacion", "sugerencia", "acción recomendada", "accion recomendada"]
    negations = ["sin ", "no ", "without ", "ninguna", "ningún", "ningun"]
    found_recommendations = False
    for path, _ in endpoints_to_check:
        code, body = get(path, {"period_days": 28}, timeout=60)
        if isinstance(body, dict):
            body_str = json.dumps(body).lower()
            for kw in recommendation_keywords:
                if kw in body_str:
                    # check if keyword appears in negation context (e.g., "Sin recomendaciones")
                    idx = body_str.find(kw)
                    prefix = body_str[max(0, idx - 15):idx]
                    is_negated = any(neg in prefix for neg in negations)
                    if not is_negated:
                        check(f"O.1 NO '{kw}' en {path}", False, f"Encontrado en respuesta")
                        found_recommendations = True
    if not found_recommendations:
        check("O.1 Ningún endpoint genera recomendaciones", True)

    # ═══ VEREDICTO ═══
    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["status"] == PASS)
    warned = sum(1 for r in results if r["status"] == WARN)
    failed = sum(1 for r in results if r["status"] == FAIL)
    critical_failures = sum(1 for r in results if r["status"] == FAIL and r["check"].startswith(("A.", "E.", "F.", "G.", "H.", "I.", "J.")))

    print(f"Total checks: {total}")
    print(f"  PASS: {passed}")
    print(f"  WARN: {warned}")
    print(f"  FAIL: {failed}")
    print(f"  Critical FAIL: {critical_failures}")

    if failed == 0:
        verdict = "GO"
    elif critical_failures == 0:
        verdict = "CONDITIONAL GO"
    else:
        verdict = "NO-GO"

    print(f"\nVEREDICTO: {verdict}")
    print(f"  GO: Todas las validaciones críticas pasan (facts, endpoints, no roturas).")
    print(f"  CONDITIONAL GO: Hay warnings pero las validaciones críticas pasan.")
    print(f"  NO-GO: Fallos críticos que deben resolverse.")

    # Guardar resultados
    output_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "qa_results"
    )
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{VALIDATION_ID}.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "validation_id": VALIDATION_ID,
            "verdict": verdict,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "base_url": BASE_URL,
            "total_checks": total,
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "critical_failures": critical_failures,
            "results": results,
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en: {output_path}")

    return 0 if verdict != "NO-GO" else 1


if __name__ == "__main__":
    sys.exit(main())
