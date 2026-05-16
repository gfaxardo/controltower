"""
Auditoría de endpoints visibles en UI de producción.

Este script verifica que los endpoints consumidos por las vistas KEEP_VISIBLE
respondan correctamente (sin 500, estructura JSON mínima).

IMPORTANTE: La lista de endpoints debe mantenerse sincronizada con
frontend/src/config/controlTowerNavigationRegistry.js

Uso:
  python backend/scripts/audit_visible_ui_endpoints.py
  python backend/scripts/audit_visible_ui_endpoints.py --base-url http://localhost:8000
  python backend/scripts/audit_visible_ui_endpoints.py --quick  # solo 10s timeout por endpoint
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

# ─── Endpoints usados por vistas KEEP_VISIBLE ────────────────────────────
# Cada entrada: (endpoint, vista_asociada, params_por_defecto)
VISIBLE_ENDPOINTS = [
    # Performance > Resumen (ExecutiveSnapshotView)
    ("/core/summary/monthly", "ExecutiveSnapshotView", {}),
    ("/ops/plan/monthly", "ExecutiveSnapshotView", {}),
    ("/ops/real/monthly", "ExecutiveSnapshotView", {"source": "canonical"}),

    # Performance > Plan vs Real (MonthlySplitView + WeeklyPlanVsRealView)
    ("/ops/plan-vs-real/monthly", "MonthlySplitView", {}),
    ("/phase2b/weekly/plan-vs-real", "WeeklyPlanVsRealView", {}),

    # Performance > Real diario (RealOperationalView)
    ("/ops/real-operational/snapshot", "RealOperationalView", {"country": "PE", "city": "Lima"}),

    # Drivers > Supply (SupplyView)
    ("/ops/supply/geo", "SupplyView", {}),
    ("/ops/supply/summary", "SupplyView", {}),

    # Drivers > Ciclo de vida (DriverLifecycleView)
    ("/ops/driver-lifecycle/summary", "DriverLifecycleView", {}),
    ("/ops/driver-lifecycle/weekly", "DriverLifecycleView", {}),

    # Drivers > Alertas de conducta (BehavioralAlertsView)
    ("/ops/behavior-alerts/summary", "BehavioralAlertsView", {}),
    ("/ops/behavior-alerts/drivers", "BehavioralAlertsView", {}),

    # Drivers > Fuga de flota (FleetLeakageView)
    ("/ops/leakage/summary", "FleetLeakageView", {}),
    ("/ops/leakage/drivers", "FleetLeakageView", {}),

    # Riesgo > Desviación por ventanas (DriverBehaviorView)
    ("/ops/driver-behavior/summary", "DriverBehaviorView", {}),
    ("/ops/driver-behavior/drivers", "DriverBehaviorView", {}),

    # Operación > Omniview Matrix (BusinessSliceOmniviewMatrix)
    ("/ops/business-slice/monthly", "BusinessSliceOmniviewMatrix", {}),
    ("/ops/business-slice/matrix-operational-trust", "BusinessSliceOmniviewMatrix", {}),

    # Operación > Control Loop PvR
    ("/ops/control-loop/plan-vs-real", "ControlLoopPlanVsRealView", {}),
    ("/ops/control-loop/plan-versions", "ControlLoopPlanVsRealView", {}),

    # Operación > Real LOB / Drill
    ("/ops/real-lob/drill/parks", "RealLOBDrillView", {}),

    # Plan > Acciones (Phase2BActionsTrackingView + Phase2CAccountabilityView)
    ("/phase2b/actions", "Phase2BActionsTrackingView", {}),
    ("/phase2c/scoreboard", "Phase2CAccountabilityView", {}),

    # Plan > Universo (LobUniverseView)
    ("/phase2c/lob-universe", "LobUniverseView", {}),

    # Plan > Validación (PlanTabs)
    ("/plan/out_of_universe", "PlanTabs", {}),
    ("/plan/missing", "PlanTabs", {}),

    # Diagnósticos (SystemHealthView)
    ("/ops/system-health", "SystemHealthView", {}),
    ("/ops/data-freshness/global", "SystemHealthView", {"group": "operational"}),
    ("/ops/integrity-report", "SystemHealthView", {}),
]


def check_endpoint(base_url, path, params=None, timeout=30):
    """Prueba un endpoint y retorna (status_code, latency_ms, ok, message)."""
    start = time.perf_counter()

    url = f"{base_url}{path}"
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        url = f"{url}?{query}"

    try:
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/json")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            latency = round((time.perf_counter() - start) * 1000)
            status = resp.status

            try:
                data = json.loads(raw)
                if isinstance(data, (dict, list)):
                    return status, latency, True, "JSON válido"
                else:
                    return status, latency, False, "Respuesta no es JSON objeto/array"
            except json.JSONDecodeError:
                text = raw.decode("utf-8", errors="replace")[:200]
                return status, latency, False, f"No es JSON: {text}"
    except urllib.error.HTTPError as e:
        latency = round((time.perf_counter() - start) * 1000)
        try:
            body = e.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            body = "(no body)"
        return e.code, latency, False, f"HTTP {e.code}: {body}"
    except Exception as e:
        latency = round((time.perf_counter() - start) * 1000)
        return 0, latency, False, str(e)


def run_audit(base_url, quick=False):
    """Ejecuta la auditoría completa y retorna resultados."""
    timeout = 10 if quick else 30
    results = []

    print(f"\n{'='*80}")
    print(f"  AUDITORÍA DE ENDPOINTS VISIBLES EN UI")
    print(f"  Base URL: {base_url}")
    print(f"  Timeout: {timeout}s por endpoint")
    print(f"  Total endpoints: {len(VISIBLE_ENDPOINTS)}")
    print(f"{'='*80}\n")

    for path, view, params in VISIBLE_ENDPOINTS:
        status, latency, ok, msg = check_endpoint(base_url, path, params, timeout)

        verdict = "OK" if ok else ("WARNING" if 400 <= status < 500 else "FAILED")
        results.append({
            "endpoint": path,
            "view": view,
            "status": status,
            "latency_ms": latency,
            "ok": ok,
            "verdict": verdict,
            "message": msg,
        })

        icon = "✓" if ok else ("⚠" if 400 <= status < 500 else "✗")
        print(f"  {icon} {path:45s}  {status:3d}  {latency:5d}ms  {verdict:8s}  {view}")
        if not ok:
            print(f"     └─ {msg}")

    return results


def print_summary(results):
    """Imprime resumen consolidado."""
    total = len(results)
    ok_count = sum(1 for r in results if r["verdict"] == "OK")
    warning_count = sum(1 for r in results if r["verdict"] == "WARNING")
    failed_count = sum(1 for r in results if r["verdict"] == "FAILED")

    avg_latency = round(sum(r["latency_ms"] for r in results) / total) if total else 0
    max_latency = max((r["latency_ms"] for r in results), default=0)

    print(f"\n{'='*80}")
    print(f"  RESUMEN")
    print(f"{'='*80}")
    print(f"  Total:     {total}")
    print(f"  OK:        {ok_count}")
    print(f"  WARNING:   {warning_count}")
    print(f"  FAILED:    {failed_count}")
    print(f"  Latencia:  avg={avg_latency}ms  max={max_latency}ms")
    print(f"{'='*80}\n")

    if failed_count > 0:
        print("  ENDPOINTS FALLIDOS:")
        for r in results:
            if r["verdict"] == "FAILED":
                print(f"    ✗ {r['endpoint']} ({r['view']}): {r['message']}")
        print()

    return ok_count == total


def main():
    parser = argparse.ArgumentParser(description="Auditar endpoints visibles en UI de producción")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="URL base de la API (default: http://localhost:8000)")
    parser.add_argument("--quick", action="store_true",
                        help="Timeout reducido a 10s por endpoint")
    parser.add_argument("--json", action="store_true",
                        help="Salida en formato JSON")
    args = parser.parse_args()

    results = run_audit(args.base_url, quick=args.quick)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        all_ok = print_summary(results)
        sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
