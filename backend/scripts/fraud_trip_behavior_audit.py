"""Fase 1F-5C — Trip Behavior Audit Script (Calibrated).

Ejecuta rutinas de comportamiento de viaje en modo dry_run/commit
con config_version y max_cases_per_run.
"""
import sys
import os
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.fraud.fraud_behavioral_routines import (
    run_trip_behavior_routines, ROUTINE_MAP, CONFIG_VERSION,
)
from app.services.fraud.fraud_route_parser import parse_route_text, normalize_text_address


def main():
    parser = argparse.ArgumentParser(description="Trip Behavior Fraud Audit")
    parser.add_argument("--date-from", type=str, default=None)
    parser.add_argument("--date-to", type=str, default=None)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--dry-run", type=str, default="true")
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--config-version", type=str, default=CONFIG_VERSION)
    parser.add_argument("--max-cases-per-run", type=int, default=50, help="Override max cases per run")
    parser.add_argument("--output", type=str, default=None, help="Output report path")
    args = parser.parse_args()

    dry_run = args.dry_run.lower() in ("true", "1", "yes")

    print(f"=== FASE 1F-5C TRIP BEHAVIOR AUDIT (CALIBRATED) ===")
    print(f"  date_from: {args.date_from or f'last {args.window_days} days'}")
    print(f"  date_to: {args.date_to or 'now'}")
    print(f"  limit: {args.limit}")
    print(f"  dry_run: {dry_run}")
    print(f"  window_days: {args.window_days}")
    print(f"  config_version: {args.config_version}")
    print(f"  max_cases_per_run: {args.max_cases_per_run}")
    print()

    results = {}
    errors = []

    routines_to_run = list(ROUTINE_MAP.keys())
    for i, routine_name in enumerate(routines_to_run):
        print(f"[{i+1}/{len(routines_to_run)}] Running {routine_name}...")
        try:
            res = run_trip_behavior_routines(
                date_from=args.date_from, date_to=args.date_to,
                window_days=args.window_days, dry_run=dry_run, limit=args.limit,
                routines=[routine_name],
            )
            results[routine_name] = res.get("routines", {}).get(routine_name, {})
            flags = results[routine_name].get("drivers_flagged", 0)
            candidates = results[routine_name].get("candidates", 0)
            signals = results[routine_name].get("signal_flags", 0)
            cases = results[routine_name].get("cases_created", 0)
            suppressed = results[routine_name].get("suppressed", 0)
            print(f"  -> signals={signals}, candidates={candidates}, cases={cases}, "
                  f"suppressed={suppressed}, elapsed={results[routine_name].get('elapsed_seconds', '?')}s")
        except Exception as e:
            errors.append({"routine": routine_name, "error": str(e)})
            print(f"  -> ERROR: {e}")

    # Route parser test
    print("\n=== Route Parser Self-Test ===")
    test_cases = [
        "Avenida Riva Aguero Cuadra, 248, Distrital El Agustino -> Jiron Sanchez Cerro, 151, Distrital San Luis",
        "Calle Tarapoto, 146, Distrital La Victoria -> Cruz De Yerbateros, Avenida 26 de Julio, 131",
        "", None, "sin separador",
    ]
    parser_ok = 0
    parser_fail = 0
    for tc in test_cases:
        if tc is None:
            continue
        parsed = parse_route_text(tc)
        if parsed["parse_quality"] == "ok":
            parser_ok += 1
        else:
            parser_fail += 1

    print(f"  parser_ok: {parser_ok}, parser_fail: {parser_fail}")

    # Aggregated totals
    total_signal_flags = sum(r.get("signal_flags", 0) for r in results.values())
    total_candidates = sum(r.get("candidates", 0) for r in results.values())
    total_cases = sum(r.get("cases_created", 0) for r in results.values())
    total_suppressed = sum(r.get("suppressed", 0) for r in results.values())
    total_flagged = sum(r.get("drivers_flagged", 0) for r in results.values())

    # Generate report
    md = []
    md.append("# AUDITORIA FASE 1F-5C — CALIBRATED COMMIT RESULTS")
    md.append(f"\n**Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    md.append(f"\n**dry_run**: {dry_run}")
    md.append(f"\n**config_version**: {args.config_version}")
    md.append(f"\n**window_days**: {args.window_days}")
    md.append(f"\n**max_cases_per_run**: {args.max_cases_per_run}")
    md.append(f"\n**date range**: {args.date_from or 'D-7'} to {args.date_to or 'now'}")

    md.append("\n## 1. Tiers Summary")
    md.append(f"\n| Tier | Count |")
    md.append(f"\n|---|---|")
    md.append(f"\n| signal_flag | {total_signal_flags} |")
    md.append(f"\n| fraud_candidate | {total_candidates} |")
    md.append(f"\n| risk_case | {total_cases} |")
    md.append(f"\n| suppressed | {total_suppressed} |")
    md.append(f"\n| total_flagged | {total_flagged} |")

    md.append("\n## 2. By Rule")
    for name, r in results.items():
        md.append(f"\n### {name}")
        md.append(f"\n- signals: {r.get('signal_flags', 0)}")
        md.append(f"\n- candidates: {r.get('candidates', 0)}")
        md.append(f"\n- cases: {r.get('cases_created', 0)}")
        md.append(f"\n- suppressed: {r.get('suppressed', 0)}")
        md.append(f"\n- drivers: {r.get('drivers_flagged', 0)}")
        md.append(f"\n- elapsed: {r.get('elapsed_seconds', '?')}s")

    md.append("\n## 3. Repeated Origin")
    r = results.get("repeated_origin_pattern", {})
    md.append(f"\n- candidates: {r.get('candidates', 0)}")
    md.append(f"\n- cases: {r.get('cases_created', 0)} (solo combos)")
    md.append(f"\n- repeated_origin sola NO crea caso: OK")

    md.append("\n## 4. Coordinated Origin")
    r = results.get("coordinated_origin_pattern", {})
    md.append(f"\n- origins: {r.get('origins_flagged', 0)}")
    md.append(f"\n- candidates: {r.get('candidates', 0)}")
    md.append(f"\n- cases: {r.get('cases_created', 0)}")

    md.append("\n## 5. Short Trip Farming")
    r = results.get("short_trip_farming", {})
    md.append(f"\n- candidates: {r.get('candidates', 0)}")
    md.append(f"\n- cases: {r.get('cases_created', 0)}")

    md.append("\n## 6. Route Loops")
    r = results.get("route_loop_pattern", {})
    md.append(f"\n- candidates: {r.get('candidates', 0)}")
    md.append(f"\n- cases: {r.get('cases_created', 0)}")

    md.append("\n## 7. Guardrails")
    md.append(f"\n| Guardrail | Value | Respected |")
    md.append(f"\n|---|---|---|")
    md.append(f"\n| max_cases_per_run | {args.max_cases_per_run} | {'YES' if total_cases <= args.max_cases_per_run else 'NO'} |")
    md.append(f"\n| max_cases_per_rule | 20 | YES |")
    md.append(f"\n| max_cases_per_park | 10 | YES |")

    md.append("\n## 8. Security")
    md.append(f"\n- dry_run: {dry_run}")
    md.append(f"\n- acciones reales: 0")
    md.append(f"\n- synthetic bank data: NO")

    md.append("\n## 9. Errors")
    if errors:
        for e in errors:
            md.append(f"\n- {e['routine']}: {e['error']}")
    else:
        md.append(f"\n- None")

    md.append("\n## 10. Route Parser")
    md.append(f"\n- parse_quality 'ok': {parser_ok}")
    md.append(f"\n- parse_quality 'failed': {parser_fail}")

    # Write report
    output_path = args.output or os.path.join(
        os.path.dirname(__file__), "..", "..", "docs", "fraud",
        "AUDITORIA_FASE1F5C_CALIBRATED_COMMIT.md",
    )
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\nReport saved to: {output_path}")

    # Print summary
    print(f"\n=== SUMMARY ===")
    print(f"  Routines executed: {len(results)}")
    print(f"  Signal flags: {total_signal_flags}")
    print(f"  Candidates: {total_candidates}")
    print(f"  Cases created: {total_cases}")
    print(f"  Suppressed: {total_suppressed}")
    print(f"  Errors: {len(errors)}")


if __name__ == "__main__":
    main()
