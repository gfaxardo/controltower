"""
OMNI-P0.1 — Trust Sensor Audit Script

Audita el trust reportado por matrix-operational-trust contra la evidencia real
del sistema corriendo (serving, fact layer, freshness).

Exit code:
  0 — trust reportado coincide con evidencia (sin contradicciones)
  1 — trust reportado contradice evidencia (falso SAFE o score inflado)
  2 — error irrecuperable (backend caído, timeout, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import URLError


BASE = "http://localhost:8001"
TIMEOUT = 30


def _get(path: str) -> dict[str, Any]:
    url = f"{BASE}{path}"
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except URLError as e:
        print(f"ERROR: No se pudo conectar a {url}: {e}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR: respuesta no es JSON en {url}: {e}", file=sys.stderr)
        sys.exit(2)


def audit() -> dict[str, Any]:
    """Ejecuta la auditoría completa y retorna el reporte."""

    evidence: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "trust_reported": None,
        "serving": {},
        "fact_layer": {},
        "freshness": {},
        "contradictions": [],
        "blocking_findings": [],
        "verdict": "INCONCLUSIVE",
        "exit_code": 0,
    }

    # ── 1. Trust reportado ──
    try:
        trust = _get("/ops/business-slice/matrix-operational-trust")
        evidence["trust_reported"] = {
            "trust_status": trust.get("trust_status"),
            "decision_mode": trust.get("operational_decision", {}).get("decision_mode"),
            "confidence_score": trust.get("operational_decision", {}).get("confidence", {}).get("score"),
            "coverage": trust.get("operational_decision", {}).get("confidence", {}).get("coverage"),
            "freshness": trust.get("operational_decision", {}).get("confidence", {}).get("freshness"),
            "consistency": trust.get("operational_decision", {}).get("confidence", {}).get("consistency"),
            "blocked_count": trust.get("operational_trust", {}).get("blocked_count", 0),
            "blocked_findings": trust.get("operational_trust", {}).get("blocked_findings", []),
            "warning_findings": trust.get("operational_trust", {}).get("warning_findings", []),
        }
    except SystemExit:
        raise
    except Exception as e:
        evidence["contradictions"].append(f"ERROR leyendo trust: {e}")
        evidence["exit_code"] = 2
        return evidence

    # ── 2. Evidencia de serving: daily/weekly/monthly ──
    for grain, path in [("daily", "/ops/business-slice/daily?country=Peru&city=Lima"),
                         ("weekly", "/ops/business-slice/weekly?country=Peru&city=Lima"),
                         ("monthly", "/ops/business-slice/monthly?country=Peru&city=Lima")]:
        try:
            resp = _get(path)
            rows = resp.get("data") or []
            evidence["serving"][grain] = {
                "row_count": len(rows),
                "fact_layer": resp.get("meta", {}).get("fact_layer", {}) if grain == "weekly" else None,
            }
            if rows:
                sample = rows[0]
                metrics = {}
                for k in ("trips_completed", "active_drivers", "avg_ticket", "trips_per_driver"):
                    metrics[k] = sample.get(k) is not None and sample.get(k) != 0
                rev_null = sample.get("revenue_yego_net") is None
                metrics["revenue_available"] = not rev_null
                evidence["serving"][grain]["sample_metrics"] = metrics
        except SystemExit:
            raise
        except Exception as e:
            evidence["serving"][grain] = {"error": str(e)[:200]}

    # ── 3. Health / freshness ──
    try:
        health = _get("/health")
        evidence["health"] = {
            "status": health.get("status"),
            "db_connection": health.get("db_connection"),
            "startup_overall": health.get("startup", {}).get("overall"),
        }
        checks = health.get("startup", {}).get("checks") or []
        for ch in checks:
            name = str(ch.get("name") or "")
            status = str(ch.get("status") or "")
            if name == "omniview_serving_integrity":
                evidence["freshness"]["serving_integrity"] = status
                evidence["freshness"]["serving_integrity_detail"] = str(ch.get("detail") or "")[:300]
            if name == "omniview_freshness":
                evidence["freshness"]["freshness_status"] = status
    except SystemExit:
        raise
    except Exception as e:
        evidence["health"] = {"error": str(e)[:200]}

    # ── 4. Reglas de validación ──
    ruled_evidence(evidence)

    return evidence


def ruled_evidence(ev: dict[str, Any]) -> None:
    """Aplica las 10 reglas hard fail de OMNI-P0.1 contra la evidencia."""

    trust = ev.get("trust_reported") or {}
    decision_mode = str(trust.get("decision_mode") or "").upper()
    trust_ok = decision_mode in ("SAFE", "OK") or str(trust.get("trust_status") or "") == "ok"
    serving = ev.get("serving") or {}
    freshness = ev.get("freshness") or {}

    # R1: weekly vacío + trust SAFE → FAIL
    weekly = serving.get("weekly") or {}
    if weekly.get("row_count", -1) == 0 and trust_ok:
        ev["contradictions"].append(
            "R1 FAIL: Trust dice SAFE/OK pero weekly tiene 0 filas (FACT_LAYER_EMPTY)."
        )
        ev["blocking_findings"].append("FACT_LAYER_EMPTY_WEEKLY")

    # R2: daily con <7 fechas + trust SAFE → FAIL
    daily = serving.get("daily") or {}
    if daily.get("row_count", 999) < 7 and trust_ok:
        ev["contradictions"].append(
            f"R2 FAIL: Trust dice SAFE/OK pero daily solo tiene {daily.get('row_count', 0)} filas."
        )
        ev["blocking_findings"].append("FACT_LAYER_THIN_DAILY")

    # R3: revenue NULL en todas las filas con trips → FAIL
    for grain_key in ("daily", "monthly"):
        g = serving.get(grain_key) or {}
        sample_metrics = g.get("sample_metrics") or {}
        if sample_metrics.get("trips_completed") and not sample_metrics.get("revenue_available"):
            if trust_ok:
                ev["contradictions"].append(
                    f"R3 FAIL: Trust dice SAFE/OK pero revenue es NULL en {grain_key} con trips>0."
                )
                ev["blocking_findings"].append("REVENUE_NULL_MASSIVE")

    # R4: serving integrity blocked + trust SAFE → FAIL
    si_status = freshness.get("serving_integrity") or ""
    if si_status in ("blocked", "error") and trust_ok:
        ev["contradictions"].append(
            f"R4 FAIL: Trust dice SAFE/OK pero serving integrity está {si_status}."
        )
        ev["blocking_findings"].append("SERVING_INTEGRITY_BLOCKED")

    # R5: freshness breach + trust SAFE → FAIL
    fs_status = freshness.get("freshness_status") or ""
    if fs_status in ("breach", "blocked") and trust_ok:
        ev["contradictions"].append(
            f"R5 FAIL: Trust dice SAFE/OK pero freshness governance está {fs_status}."
        )
        ev["blocking_findings"].append("FRESHNESS_GOVERNANCE_BREACH")

    # R6: trust < 45 → ya está BLOCKED, correcto
    score = trust.get("confidence_score")
    if isinstance(score, (int, float)) and score < 45:
        if decision_mode != "BLOCKED":
            ev["contradictions"].append(
                f"R6 FAIL: confidence={score} (<45) pero decision_mode={decision_mode}, debería ser BLOCKED."
            )

    # R7: trust SAFE con coverage < 80 → FAIL
    coverage = trust.get("coverage")
    if isinstance(coverage, (int, float)) and coverage < 80 and trust_ok:
        ev["contradictions"].append(
            f"R7 FAIL: Trust SAFE/OK pero coverage={coverage} (<80)."
        )

    # R8: trust SAFE con freshness < 60 → FAIL
    trust_fresh = trust.get("freshness")
    if isinstance(trust_fresh, (int, float)) and trust_fresh < 60 and trust_ok:
        ev["contradictions"].append(
            f"R8 FAIL: Trust SAFE/OK pero freshness={trust_fresh} (<60)."
        )

    # R9: trust SAFE con consistency < 70 → FAIL
    consistency = trust.get("consistency")
    if isinstance(consistency, (int, float)) and consistency < 70 and trust_ok:
        ev["contradictions"].append(
            f"R9 FAIL: Trust SAFE/OK pero consistency={consistency} (<70)."
        )

    # R10: blocked_count > 0 + trust SAFE → FAIL
    blocked_count = trust.get("blocked_count") or 0
    if blocked_count > 0 and trust_ok:
        ev["contradictions"].append(
            f"R10 FAIL: Trust SAFE/OK pero tiene {blocked_count} blocked findings activos."
        )
        ev["blocking_findings"].extend(
            [f.get("code") for f in trust.get("blocked_findings") or [] if f.get("code")]
        )

    # ── Veredicto ──
    if ev["contradictions"]:
        ev["verdict"] = "FAIL — Trust contradice evidencia"
        ev["exit_code"] = 1
    elif decision_mode == "BLOCKED":
        ev["verdict"] = "PASS — Trust correctamente BLOCKED (datos incompletos)"
        ev["exit_code"] = 0
    else:
        ev["verdict"] = "PASS — Trust SAFE y evidencia consistente"
        ev["exit_code"] = 0


def print_report(ev: dict[str, Any]) -> None:
    print("=" * 70)
    print("OMNI-P0.1 — Trust Sensor Audit")
    print(f"Timestamp: {ev['timestamp']}")
    print("=" * 70)

    trust = ev.get("trust_reported") or {}
    print(f"\n--- TRUST REPORTADO ---")
    print(f"  trust_status:    {trust.get('trust_status')}")
    print(f"  decision_mode:   {trust.get('decision_mode')}")
    print(f"  confidence:      {trust.get('confidence_score')}")
    print(f"  coverage:        {trust.get('coverage')}")
    print(f"  freshness:       {trust.get('freshness')}")
    print(f"  consistency:     {trust.get('consistency')}")
    print(f"  blocked_count:   {trust.get('blocked_count')}")

    blocked = trust.get("blocked_findings") or []
    if blocked:
        print(f"  blocked_findings:")
        for bf in blocked[:5]:
            print(f"    - [{bf.get('code')}] {bf.get('message', '')[:120]}")

    print(f"\n--- EVIDENCIA SERVING ---")
    for grain, info in (ev.get("serving") or {}).items():
        fl = info.get("fact_layer")
        fl_status = f" fact_layer={fl.get('status')}" if fl else ""
        print(f"  {grain}: {info.get('row_count', '?')} filas{fl_status}")

    print(f"\n--- EVIDENCIA FRESHNESS ---")
    for k, v in (ev.get("freshness") or {}).items():
        if not k.endswith("_detail"):
            print(f"  {k}: {v}")

    print(f"\n--- CONTRADICCIONES ---")
    if ev["contradictions"]:
        for c in ev["contradictions"]:
            print(f"  {c}")
    else:
        print("  Ninguna. Trust coherente con evidencia.")

    if ev["blocking_findings"]:
        unique = list(dict.fromkeys(ev["blocking_findings"]))
        print(f"\n  Blocking codes: {', '.join(unique)}")

    print(f"\n--- VEREDICTO ---")
    print(f"  {ev['verdict']}")
    print(f"  Exit code: {ev['exit_code']}")


def main() -> None:
    global BASE
    parser = argparse.ArgumentParser(description="OMNI-P0.1 Trust Sensor Audit")
    parser.add_argument("--json", action="store_true", help="Salida JSON")
    parser.add_argument("--base", default=None, help=f"Base URL (default: http://localhost:8001)")
    args = parser.parse_args()

    if args.base:
        BASE = args.base

    ev = audit()

    if args.json:
        print(json.dumps(ev, ensure_ascii=False, indent=2, default=str))
    else:
        print_report(ev)

    sys.exit(ev["exit_code"])


if __name__ == "__main__":
    main()
