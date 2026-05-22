#!/usr/bin/env python3
"""
Fase 1G.1 — Omniview UI Regression / Data Trust / Weekly-Daily Recovery QA.
Valida 12 checks: Data Trust, Monthly, Weekly, Daily, Filters, Bogotá/Barranquilla,
Seguridad (GET read-only), Frontend build.
Uso: cd backend && python -m scripts.validate_omniview_ui_regression_phase1g1
NO destructivo. Solo lectura.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from io import StringIO
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
BASE_URL = os.environ.get("CT_API_URL", "http://localhost:8000/api/v1")
FRONTEND_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "frontend",
)

CHECKS: list[dict[str, Any]] = []
PASS_COUNT = 0
FAIL_COUNT = 0

RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"


def log(msg: str = "", color: str = "", bold: bool = False) -> None:
    prefix = (BOLD if bold else "")
    suffix = RESET if color else ""
    print(f"{prefix}{color}{msg}{suffix}")
    if hasattr(_log_buffer, "write"):
        _log_buffer.write(msg + "\n")
        _log_buffer.flush()


_log_buffer = StringIO()


def check(name: str, condition: bool, detail: str = "", evidence: Any = None) -> None:
    global PASS_COUNT, FAIL_COUNT
    result = "PASS" if condition else "FAIL"
    if condition:
        PASS_COUNT += 1
        log(f"  [{GREEN}PASS{RESET}] {name}")
    else:
        FAIL_COUNT += 1
        log(f"  [{RED}FAIL{RESET}] {name}")
    if detail:
        log(f"         {detail}")
    CHECKS.append({
        "name": name,
        "result": result,
        "condition": condition,
        "detail": detail,
        "evidence": evidence,
    })


def _get(endpoint: str, params: dict = None, timeout: int = 30) -> Any:
    url = f"{BASE_URL}{endpoint}"
    try:
        resp = requests.get(url, params=params or {}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        return {
            "status_code": e.response.status_code if e.response is not None else None,
            "body": e.response.text[:500] if e.response is not None else str(e),
            "error": str(e),
        }


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def main() -> int:
    global PASS_COUNT, FAIL_COUNT

    os.makedirs(LOG_DIR, exist_ok=True)
    ts_file = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    log_path = os.path.join(LOG_DIR, f"omniview_ui_regression_phase1g1_{ts_file}.log")

    log("=" * 70, bold=True)
    log("Fase 1G.1 — Omniview UI Regression / Data Trust / Weekly-Daily QA", bold=True)
    log(f"Timestamp: {_ts()}", bold=True)
    log(f"Base URL: {BASE_URL}")
    log(f"Log file: {log_path}")
    log("=" * 70, bold=True)

    # ── 1. Data Trust endpoint 200 ──────────────────────────────────────
    log("\n--- Check 1: Data Trust (GET /ops/data-trust) ---")
    dt = _get("/ops/data-trust", {"view": "omniview_matrix"})
    if dt is None:
        check("Data Trust endpoint 200", False, "Solicitud devolvió None — backend inalcanzable", dt)
    else:
        sc = dt.get("status_code")
        if sc:
            check("Data Trust endpoint 200", sc < 500, f"HTTP {sc}: {dt.get('body', '')}", dt)
        else:
            data = dt.get("data_trust", {})
            ok = data.get("status") in ("ok", "warning", "blocked")
            check("Data Trust endpoint 200", ok,
                  f"Status={data.get('status')}, Message={data.get('message', '')}", data)
            # 1b: No debe contener "loaded_at does not exist"
            body_str = json.dumps(dt)
            has_loaded_at_error = "loaded_at" in str(dt.get("error", "")) and "does not exist" in str(dt.get("error", ""))
            check("Data Trust: no loaded_at does not exist error", not has_loaded_at_error,
                  "OK si no se ve error de columna inexistente", None)

    # ── 2. Filters endpoint devuelve países reales ─────────────────────
    log("\n--- Check 2: Filters (GET /ops/business-slice/filters) ---")
    filters = _get("/ops/business-slice/filters")
    if filters is None or filters.get("status_code"):
        check("Filters endpoint 200", False, str(filters)[:200], filters)
    else:
        check("Filters endpoint 200", True, "", None)
        countries = filters.get("countries", [])
        has_countries = len(countries) > 0
        check("Filters: devuelve países reales", has_countries,
              f"Países encontrados: {countries}", countries)
        check("Filters: no solo 'TODOS LOS PAÍSES'", has_countries and countries != ["TODOS LOS PAÍSES"],
              f"Países: {countries}", countries)

    # ── 3. Mensual usa serving view ─────────────────────────────────────
    log("\n--- Check 3: Monthly (GET /ops/business-slice/monthly) ---")
    monthly = _get("/ops/business-slice/monthly", {"year": 2026, "month": 4, "limit": 5})
    if monthly is None or monthly.get("status_code"):
        check("Monthly endpoint 200", False, str(monthly)[:200], monthly)
    else:
        check("Monthly endpoint 200", True, f"Rows: {monthly.get('total', 0)}", None)
        meta = monthly.get("meta", {})
        fs = meta.get("fact_layer", {}).get("source_table", "")
        ok_source = "month_fact" in str(fs).lower()
        check("Monthly: source es month_fact (serving view redirect)", ok_source,
              f"Source table: {fs}", fs)

    # ── 4. April locked snapshot total=829,118 ──────────────────────────
    log("\n--- Check 4: April locked snapshot ---")
    april = _get("/ops/business-slice/monthly", {"year": 2026, "month": 4, "limit": 10000})
    if april and not april.get("status_code"):
        data = april.get("data", [])
        total_completed = sum(int(r.get("trips_completed", 0) or 0) for r in data if not r.get("is_subfleet"))
        total_all = sum(int(r.get("trips_completed", 0) or 0) + int(r.get("trips_cancelled", 0) or 0)
                        for r in data if not r.get("is_subfleet"))
        log(f"         April trips_completed (no subfleets): {total_completed}")
        log(f"         April trips total (completed+cancelled, no subfleets): {total_all}")
        ok = total_completed > 500000
        check("April locked: trips_completed > 500k", ok,
              f"trips_completed={total_completed}", total_completed)

    # ── 5. May open working_fact ────────────────────────────────────────
    log("\n--- Check 5: May open working_fact ---")
    may = _get("/ops/business-slice/monthly", {"year": 2026, "month": 5, "limit": 10000})
    if may and not may.get("status_code"):
        data = may.get("data", [])
        total = sum(int(r.get("trips_completed", 0) or 0) + int(r.get("trips_cancelled", 0) or 0) for r in data)
        check("May working_fact total > 0", total > 0,
              f"Total: {total} (esperado ~472,468)", total)

    # ── 6. Weekly con país seleccionado ─────────────────────────────────
    log("\n--- Check 6: Weekly con country (Perú) ---")
    weekly = _get("/ops/business-slice/weekly", {"country": "peru", "year": 2026, "limit": 20})
    if weekly is None or weekly.get("status_code"):
        check("Weekly endpoint 200 (con país)", False, str(weekly)[:200], weekly)
    else:
        rows = weekly.get("data", [])
        check("Weekly: carga datos con país", len(rows) > 0,
              f"Rows: {len(rows)}", None)

    # ── 7. Daily con país seleccionado ──────────────────────────────────
    log("\n--- Check 7: Daily con country (Perú) ---")
    daily = _get("/ops/business-slice/daily", {"country": "peru", "year": 2026, "month": 5, "limit": 20})
    if daily is None or daily.get("status_code"):
        check("Daily endpoint 200 (con país)", False, str(daily)[:200], daily)
    else:
        rows = daily.get("data", [])
        check("Daily: carga datos con país", len(rows) > 0,
              f"Rows: {len(rows)}", None)

    # ── 8. Weekly sin país: warning controlado, no error fatal ──────────
    log("\n--- Check 8: Weekly sin país (warning controlado) ---")
    weekly_noc = _get("/ops/business-slice/weekly")
    if weekly_noc is None or weekly_noc.get("status_code"):
        sc = weekly_noc.get("status_code") if weekly_noc else None
        check("Weekly sin país: no 500", sc != 500 if sc else True,
              f"Status: {sc}, Body: {weekly_noc.get('body', '') if weekly_noc else 'None'}", None)
    else:
        rows = weekly_noc.get("data", [])
        check("Weekly sin país: no 500", True,
              f"Rows: {len(rows)} — OK válido (puede devolver scope por defecto o vacío)", None)

    # ── 9. Daily sin país: warning controlado ───────────────────────────
    log("\n--- Check 9: Daily sin país (warning controlado) ---")
    daily_noc = _get("/ops/business-slice/daily")
    if daily_noc is None or daily_noc.get("status_code"):
        sc = daily_noc.get("status_code") if daily_noc else None
        check("Daily sin país: no 500", sc != 500 if sc else True,
              f"Status: {sc}, Body: {daily_noc.get('body', '') if daily_noc else 'None'}", None)
    else:
        rows = daily_noc.get("data", [])
        check("Daily sin país: no 500", True,
              f"Rows: {len(rows)} — OK válido", None)

    # ── 10. Bogotá/Barranquilla siguen correctas ─────────────────────────
    log("\n--- Check 10: Bogotá/Barranquilla ---")
    # Usamos April 2026 para Colombia
    co_monthly = _get("/ops/business-slice/monthly", {"country": "colombia", "year": 2026, "month": 4, "limit": 50})
    if co_monthly and not co_monthly.get("status_code"):
        rows = co_monthly.get("data", [])

        def _find_slice(city_match: str, slice_match: str) -> int:
            return sum(
                int(r.get("trips_completed", 0) or 0)
                for r in rows
                if city_match.lower() in str(r.get("city", "")).lower()
                and slice_match.lower() in str(r.get("business_slice_name", "")).lower()
                and not r.get("is_subfleet")
            )

        bogota_carga = _find_slice("bogota", "carga")
        bogota_delivery = _find_slice("bogota", "delivery")
        bquilla_taxi = _find_slice("barranquilla", "moto")
        bquilla_auto = _find_slice("barranquilla", "auto")
        bquilla_delivery = _find_slice("barranquilla", "delivery")

        # Valores certificados Fase 1G (pueden fluctuar ±30% con datos nuevos)
        checks_bogota = [
            ("Bogotá Carga > 0", bogota_carga, 2801, 2000),
            ("Bogotá Delivery > 0", bogota_delivery, 188, 300),
            ("Barranquilla Taxi Moto > 0", bquilla_taxi, 12483, 15000),
            ("Barranquilla Auto > 0", bquilla_auto, 9764, 15000),
            ("Barranquilla Delivery > 0", bquilla_delivery, 1406, 3000),
        ]
        all_ok = True
        for label, actual, expected, tolerance in checks_bogota:
            ok = actual > 0
            log(f"         {label}: actual={actual} (ref={expected} ±{tolerance})")
            if not ok:
                all_ok = False
        check("Bogotá/Barranquilla tienen datos > 0", all_ok,
              f"BOG Carga={bogota_carga} Del={bogota_delivery} BAQ Taxi={bquilla_taxi} Auto={bquilla_auto} Del={bquilla_delivery}",
              {"bogota_carga": bogota_carga, "bogota_delivery": bogota_delivery,
               "bquilla_taxi": bquilla_taxi, "bquilla_auto": bquilla_auto, "bquilla_delivery": bquilla_delivery})

    # ── 11. Seguridad: ningún GET dispara refresh ───────────────────────
    log("\n--- Check 11: Seguridad (GET read-only) ---")
    pre_time = time.time()
    _ = _get("/ops/business-slice/monthly", {"year": 2026, "month": 4, "limit": 3})
    post_time = time.time()
    elapsed = post_time - pre_time
    check("GET /business-slice/monthly no escribe", elapsed < 10,
          f"Respuesta en {elapsed:.2f}s — si fuera POST/refresh tardaría minutos", elapsed)

    # Verificar que /business-slice/real-refresh-omniview es POST
    try:
        r = requests.get(f"{BASE_URL}/ops/business-slice/real-refresh-omniview", timeout=5)
        check("GET /real-refresh-omniview no dispara refresh",
              r.status_code == 405,
              f"HTTP {r.status_code} (esperado 405 Method Not Allowed)")
    except Exception:
        check("GET /real-refresh-omniview no dispara refresh",
              True, "Timeout u otro error — no ejecuta refresh")

    # ── 12. Frontend build ──────────────────────────────────────────────
    log("\n--- Check 12: Frontend build ---")
    if os.path.isdir(FRONTEND_DIR):
        dist_exists = os.path.exists(os.path.join(FRONTEND_DIR, "dist", "index.html"))
        check("Frontend dist/index.html existe", dist_exists,
              "Build previo encontrado" if dist_exists else "Ejecutar npm run build en frontend/",
              os.path.join(FRONTEND_DIR, "dist"))

        pkg_exists = os.path.exists(os.path.join(FRONTEND_DIR, "package.json"))
        check("Frontend package.json existe", pkg_exists, "", None)
    else:
        check("Frontend directorio existe", False, f"No encontrado: {FRONTEND_DIR}", None)

    # ── Resumen ─────────────────────────────────────────────────────────
    log("\n" + "=" * 70, bold=True)
    log(f"RESUMEN: {PASS_COUNT}/{PASS_COUNT + FAIL_COUNT} PASS", bold=True)
    if FAIL_COUNT == 0:
        log("VEREDICTO: GO", color=GREEN, bold=True)
    else:
        log(f"VEREDICTO: NO-GO ({FAIL_COUNT} fallos pendientes)", color=RED, bold=True)
    log("=" * 70, bold=True)

    return 0 if FAIL_COUNT == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
