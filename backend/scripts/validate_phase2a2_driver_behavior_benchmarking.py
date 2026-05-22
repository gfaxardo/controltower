"""
QA Script — Fase 2A.2: Driver Behavior Benchmarking Layer
Valida integridad del servicio, router y respuestas de endpoints.
NO modifica datos. Solo consulta GET.

Uso:
    cd backend
    python -m scripts.validate_phase2a2_driver_behavior_benchmarking

Veredicto: GO / CONDITIONAL GO / NO-GO
"""
from __future__ import annotations

import json
import sys
import time
import os
import requests

BASE_URL = os.environ.get("CT_BASE_URL", "http://127.0.0.1:8000")
VALIDATION_ID = "phase2a2_driver_behavior_benchmarking"

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


def get(path: str, params: dict = None, timeout: int = 60) -> tuple[int, dict | str]:
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
    print("QA: Fase 2A.2 — Driver Behavior Benchmarking Layer")
    print(f"Validación ID: {VALIDATION_ID}")
    print(f"Base URL: {BASE_URL}")
    print("=" * 60)

    all_pass = True
    has_warnings = False

    # A. Router importado en main.py
    print("\n--- A. Router importado ---")
    try:
        main_py_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app", "main.py"
        )
        with open(main_py_path, "r", encoding="utf-8") as f:
            content = f.read()
        router_imported = "driver_behavior_benchmarking" in content
        router_included = "driver_behavior_benchmarking.router" in content
        check("A.1 Import en main.py", router_imported, main_py_path)
        check("A.2 include_router en main.py", router_included, main_py_path)
    except Exception as e:
        check("A.1 Import en main.py", False, str(e))
        all_pass = False

    # B. Endpoints responden 200
    print("\n--- B. Endpoints responden ---")
    endpoints_to_check = [
        ("/driver-behavior/summary", {"period_days": 28}),
        ("/driver-behavior/group-benchmarks", {"period_days": 28}),
        ("/driver-behavior/top-vs-risk", {"period_days": 28}),
        ("/driver-behavior/distributions", {"dimension": "city"}),
    ]

    for path, params in endpoints_to_check:
        code, body = get(path, params)
        ok = 200 <= code < 300 if isinstance(code, int) else False
        check(f"B.{len(results) - len([r for r in results if r['check'].startswith('A.')])}  GET {path} -> {code}", ok,
              body if not ok else "")
        if not ok and code == 0:
            all_pass = False

    print("\n--- A+. Fact table DB verification ---")
    try:
        import psycopg2
        conn = psycopg2.connect(
            host='168.119.226.236',
            dbname='yego_integral',
            user='yego_user',
            password='37>MNA&-35+',
            port=5432,
            connect_timeout=10,
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
            "WHERE table_schema='ops' AND table_name='driver_daily_activity_fact')"
        )
        exists = cur.fetchone()[0]
        check("A+.1 Fact table exists in ops schema", exists)
        if exists:
            cur.execute(
                "SELECT COUNT(*), COUNT(DISTINCT driver_id), MIN(activity_date), MAX(activity_date) "
                "FROM ops.driver_daily_activity_fact"
            )
            row = cur.fetchone()
            check("A+.2 Fact table has rows", row[0] > 0, f"rows={row[0]}")
            check("A+.3 Fact table has drivers", row[1] > 0, f"drivers={row[1]}")
            check("A+.4 Fact table date range valid", row[2] is not None and row[3] is not None,
                  f"min={row[2]} max={row[3]}")
        conn.close()
    except Exception as e:
        check("A+.1 DB connection", False, str(e))
    print("\n--- C-FACT. Source alignment validation ---")
    code, body_src = get("/driver-behavior/summary", {"period_days": 28})
    if isinstance(body_src, dict):
        data_source = body_src.get("data_source", "")
        source_warning = body_src.get("source_warning")
        fallback_reason = body_src.get("fallback_reason")
        source_type = body_src.get("source_type", "")
        fact_meta = body_src.get("fact_meta")

        uses_fact = data_source == "ops.driver_daily_activity_fact"
        check("C-FACT.1 data_source is ops.driver_daily_activity_fact", uses_fact,
              f"actual={data_source}")
        check("C-FACT.2 source_type is pre_aggregated_fact", source_type == "pre_aggregated_fact",
              f"actual={source_type}")
        check("C-FACT.3 No fallback_reason (fact table active)", fallback_reason is None,
              f"actual={fallback_reason}")
        check("C-FACT.4 No source_warning", source_warning is None,
              f"actual={source_warning}")
        check("C-FACT.5 fact_meta present", fact_meta is not None,
              f"fact_meta={fact_meta}")
        if fact_meta:
            check("C-FACT.6 fact_meta has drivers_count", fact_meta.get("drivers_count", 0) > 0)
            check("C-FACT.7 fact_meta has rows_count", fact_meta.get("rows_count", 0) > 0)

    # Original C checks
    print("\n--- C. Summary contiene métricas clave ---")
    code, body = get("/driver-behavior/summary", {"period_days": 28})
    if isinstance(body, dict):
        has_available = "available_metrics" in body
        has_missing = "missing_metrics" in body
        has_source = "data_source" in body
        has_date_range = "date_range" in body
        check("C.1 available_metrics presente", has_available)
        check("C.2 missing_metrics presente", has_missing)
        check("C.3 data_source presente", has_source)
        check("C.4 date_range presente", has_date_range)

        available = body.get("available_metrics", [])
        missing = body.get("missing_metrics", [])
        check("C.5 Hay métricas disponibles o faltantes documentadas", len(available) + len(missing) > 0)
    else:
        check("C.1 Summary responde como dict", False, str(body)[:200])
        all_pass = False

    # D. Group benchmarks contiene grupos válidos
    print("\n--- D. Group Benchmarks ---")
    code, body = get("/driver-behavior/group-benchmarks", {"period_days": 28})
    if isinstance(body, dict):
        groups_list = body.get("groups", [])
        has_groups = len(groups_list) > 0
        check("D.1 groups no vacío", has_groups, f"Total grupos: {len(groups_list)}")
        if has_groups:
            group_names = {g.get("group_name") for g in groups_list}
            valid_groups = group_names & {
                "TOP_PERFORMER", "STABLE", "GROWING", "DECLINING",
                "AT_RISK", "DORMANT", "CHURNED", "REACTIVATED"
            }
            check("D.2 Grupos contienen nombres válidos", len(valid_groups) > 0,
                  f"Grupos encontrados: {sorted(group_names)}")
            # Verificar que cada grupo tiene fields básicos
            first = groups_list[0]
            required_fields = ["group_name", "drivers_count", "total_trips",
                               "avg_trips_per_driver", "avg_active_days"]
            all_fields = all(f in first for f in required_fields)
            check("D.3 Benchmarks tienen campos requeridos", all_fields,
                  f"Campos en primer grupo: {list(first.keys())}" if not all_fields else "")
    else:
        check("D.1 Group benchmarks responde como dict", False, str(body)[:200])
        all_pass = False

    # E. No hay valores negativos en trips
    print("\n--- E. Validación de valores no negativos ---")
    if isinstance(body, dict):
        groups_list = body.get("groups", [])
        has_negative = False
        for g in groups_list:
            for field in ["drivers_count", "total_trips", "avg_trips_per_driver", "avg_active_days", "trips_per_active_day"]:
                val = g.get(field)
                if val is not None and isinstance(val, (int, float)) and val < 0:
                    has_negative = True
                    print(f"  NEGATIVO: {g['group_name']}.{field} = {val}")
        check("E.1 Sin valores negativos en métricas de trips", not has_negative)
    else:
        check("E.1 Sin valores negativos", False, "No se pudo obtener group-benchmarks")

    # F. TOP_PERFORMER existe si hay data suficiente
    print("\n--- F. TOP_PERFORMER existe ---")
    if isinstance(body, dict):
        groups_list = body.get("groups", [])
        top = next((g for g in groups_list if g.get("group_name") == "TOP_PERFORMER"), None)
        total_drivers = sum(g.get("drivers_count", 0) for g in groups_list)
        if total_drivers > 10 and top and (top.get("drivers_count", 0) == 0):
            check("F.1 TOP_PERFORMER con conductores", False,
                  f"Total drivers={total_drivers} pero TOP_PERFORMER tiene 0 drivers")
        else:
            check("F.1 TOP_PERFORMER detectado si hay data", True,
                  f"TOP_PERFORMER: {top.get('drivers_count', 0) if top else 0} / Total: {total_drivers}")
    else:
        check("F.1 TOP_PERFORMER", False, "No se pudo obtener group-benchmarks")

    # G. top-vs-risk responde con interpretaciones neutrales
    print("\n--- G. Top vs Risk — Interpretaciones neutrales ---")
    code, tvr = get("/driver-behavior/top-vs-risk", {"period_days": 28})
    if isinstance(tvr, dict):
        comparisons = tvr.get("comparisons", [])
        check("G.1 comparisons no vacío", len(comparisons) > 0)

        forbidden_words = [
            "debe llamar", "debe trabajar", "sugerir", "debería",
            "recomendar", "aconsejar", "imperativo", "urgir",
            "implorar", "exigir", "contactar", "intervenir",
        ]
        has_forbidden = False
        for c in comparisons:
            interp = (c.get("interpretation") or "").lower()
            for word in forbidden_words:
                if word in interp:
                    has_forbidden = True
                    print(f"  FORBIDDEN WORD '{word}' in: {c.get('interpretation')}")

        check("G.2 Sin recomendaciones accionables en interpretaciones",
              not has_forbidden,
              "Se encontraron palabras prohibidas en interpretaciones")
    else:
        check("G.1 Top vs Risk responde", False, str(tvr)[:200])
        all_pass = False

    # H. No aparecen recomendaciones accionables en otros endpoints
    print("\n--- H. Sin recomendaciones accionables en endpoints ---")
    code, sumbody = get("/driver-behavior/summary", {"period_days": 28})
    all_text = json.dumps(sumbody if isinstance(sumbody, dict) else {}, default=str).lower()
    forbidden_any = ["debe llamar", "debe trabajar", "debería contactar",
                     "recomendar al conductor", "aconsejar que"]
    found_any = any(w in all_text for w in forbidden_any)
    check("H.1 Summary sin recomendaciones accionables", not found_any)

    # I. distributions maneja dimensiones faltantes sin romper
    print("\n--- I. Distributions maneja dimensiones faltantes ---")
    code, body_dist = get("/driver-behavior/distributions", {
        "dimension": "nonexistent_dim",
        "period_days": 28,
    })
    if isinstance(body_dist, dict):
        available = body_dist.get("available")
        reason = body_dist.get("reason", "")
        check("I.1 Dimensión inexistente: available=false", available is False,
              f"available={available}, reason={reason}")
        check("I.2 Dimensión inexistente: reason presente", bool(reason))
        check("I.3 Dimension inexistente no es 500", 200 <= code < 300 if isinstance(code, int) else False,
              f"status={code}")
    else:
        check("I.1 Dimension handling", False, str(body_dist)[:200])

    # J. No se rompe /ops/driver-lifecycle/summary
    print("\n--- J. Driver Lifecycle no se rompe ---")
    code, dl = get("/ops/driver-lifecycle/summary", {
        "from": "2026-01-01",
        "to": "2026-05-21",
        "grain": "weekly",
    })
    ok_dl = 200 <= code < 300 if isinstance(code, int) else False
    check("J.1 GET /ops/driver-lifecycle/summary -> 200", ok_dl,
          f"status={code}" + (f" body={str(dl)[:200]}" if not ok_dl else ""))

    # K. No se rompe Omniview Matrix
    print("\n--- K. Omniview Matrix no se rompe ---")
    code, om = get("/ops/business-slice/matrix-operational-trust", timeout=120)
    ok_om = 200 <= code < 300 if isinstance(code, int) else False
    check("K.1 GET /ops/business-slice/matrix-operational-trust -> 200", ok_om,
          f"status={code}" + (f" body={str(om)[:200]}" if not ok_om else ""))

    # L. No se toca Plan vs Real
    print("\n--- L. Plan vs Real no se toca ---")
    code, pvr = get("/ops/plan-vs-real/monthly", {"month": "2026-01"})
    ok_pvr = 200 <= code < 300 if isinstance(code, int) else False
    check("L.1 GET /ops/plan-vs-real/monthly -> 200", ok_pvr,
          f"status={code}" + (f" body={str(pvr)[:200]}" if not ok_pvr else ""))

    # M. Performance razonable
    print("\n--- M. Performance ---")
    t0 = time.perf_counter()
    code, _ = get("/driver-behavior/summary", {"period_days": 28})
    elapsed = time.perf_counter() - t0
    check("M.1 /driver-behavior/summary < 15s", elapsed < 15,
          f"{elapsed:.1f}s (umbral: 15s)")

    # N. Documentación creada
    print("\n--- N. Documentación ---")
    doc_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs", "diagnostic_engine", "FASE2A2_DRIVER_BEHAVIOR_BENCHMARKING.md"
    )
    doc_exists = os.path.isfile(doc_path)
    check("N.1 FASE2A2_DRIVER_BEHAVIOR_BENCHMARKING.md existe", doc_exists,
          doc_path if not doc_exists else "")

    # Veredicto
    print("\n" + "=" * 60)
    passes = sum(1 for r in results if r["status"] == PASS)
    fails = sum(1 for r in results if r["status"] == FAIL)
    warns = sum(1 for r in results if r["status"] == WARN)
    total = len(results)

    print(f"Resultados: {passes} PASS, {fails} FAIL, {warns} WARN de {total} checks")

    if fails == 0 and warns == 0:
        verdict = "GO"
    elif fails == 0:
        verdict = "CONDITIONAL GO"
    else:
        verdict = "NO-GO"

    print(f"\nVEREDICTO: {verdict}")

    # Guardar resultados
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "qa_results"
    )
    os.makedirs(output_dir, exist_ok=True)
    result_file = os.path.join(output_dir, f"{VALIDATION_ID}.json")
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump({
            "validation_id": VALIDATION_ID,
            "timestamp": time.time(),
            "verdict": verdict,
            "passes": passes,
            "fails": fails,
            "warns": warns,
            "total": total,
            "results": results,
        }, f, indent=2, default=str)

    print(f"Resultados guardados en: {result_file}")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
