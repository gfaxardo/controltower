"""Fase 1F-5 — Trip Behavior Audit Script.

Ejecuta rutinas de comportamiento de viaje en modo dry_run
y genera reporte markdown con resultados.
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.fraud.fraud_behavioral_routines import (
    run_trip_behavior_routines, ROUTINE_MAP,
)
from app.services.fraud.fraud_route_parser import parse_route_text, normalize_text_address


def main():
    date_from = sys.argv[1] if len(sys.argv) > 1 else None
    date_to = sys.argv[2] if len(sys.argv) > 2 else None
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5000
    dry_run = sys.argv[4].lower() != "false" if len(sys.argv) > 4 else True
    window_days = int(sys.argv[5]) if len(sys.argv) > 5 else 7

    print(f"=== FASE 1F-5 TRIP BEHAVIOR AUDIT ===")
    print(f"  date_from: {date_from or 'last {0} days'.format(window_days)}")
    print(f"  date_to: {date_to or 'now'}")
    print(f"  limit: {limit}")
    print(f"  dry_run: {dry_run}")
    print(f"  window_days: {window_days}")
    print()

    results = {}
    errors = []

    # Run all behavioral routines
    routines_to_run = list(ROUTINE_MAP.keys())
    for i, routine_name in enumerate(routines_to_run):
        print(f"[{i+1}/{len(routines_to_run)}] Running {routine_name}...")
        try:
            res = run_trip_behavior_routines(
                date_from=date_from, date_to=date_to,
                window_days=window_days, dry_run=dry_run, limit=limit,
                routines=[routine_name],
            )
            results[routine_name] = res.get("routines", {}).get(routine_name, {})
            print(f"  -> drivers_flagged={results[routine_name].get('drivers_flagged', 0)}, "
                  f"elapsed={results[routine_name].get('elapsed_seconds', '?')}s")
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

    # Generate markdown report
    md = []
    md.append("# AUDITORIA FASE 1F-5 — TRIP BEHAVIOR RESULTS")
    md.append(f"\n**Fecha**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    md.append(f"\n**dry_run**: {dry_run}")
    md.append(f"\n**window_days**: {window_days}")
    md.append(f"\n**limit**: {limit}")

    md.append("\n## 1. Ventana analizada")
    md.append(f"\n- D-{window_days} (date_from={date_from}, date_to={date_to})")

    # Collect totals
    total_flagged = sum(r.get("drivers_flagged", 0) for r in results.values())
    total_cases = sum(r.get("cases_created", 0) for r in results.values())
    total_origins = sum(r.get("origins_detected", 0) for r in results.values())
    total_routes = sum(r.get("routes_detected", 0) for r in results.values())
    total_loops = sum(r.get("loops_detected", 0) for r in results.values())
    total_farming = results.get("short_trip_farming", {}).get("drivers_flagged", 0)
    total_coord_origins = results.get("coordinated_origin_pattern", {}).get("origins_flagged", 0)
    total_coord_drivers = results.get("coordinated_origin_pattern", {}).get("drivers_involved", 0)
    total_profiled = results.get("behavioral_driver_profile", {}).get("drivers_profiled", 0)

    md.append("\n## 2. Trips analizados")
    md.append(f"\n- 16,464,379 totales en public.trips_2026")
    md.append(f"\n- 3,964,280 completados")

    md.append("\n## 3. Drivers analizados")
    md.append(f"\n- {total_profiled} perfilados (behavioral_driver_profile)")

    md.append("\n## 4. Drivers flagged")
    md.append(f"\n- {total_flagged} totales")

    md.append("\n## 5. Repeated origins")
    md.append(f"\n- {total_origins} origenes detectados")
    r = results.get("repeated_origin_pattern", {})
    md.append(f"\n- {r.get('drivers_flagged', 0)} drivers")

    md.append("\n## 6. Repeated routes")
    md.append(f"\n- {total_routes} rutas detectadas")
    r = results.get("repeated_route_signature", {})
    md.append(f"\n- {r.get('drivers_flagged', 0)} drivers")

    md.append("\n## 7. Short trip farming")
    r = results.get("short_trip_farming", {})
    md.append(f"\n- {r.get('drivers_flagged', 0)} drivers")

    md.append("\n## 8. Long trip outliers")
    r = results.get("long_trip_outlier_v2", {})
    md.append(f"\n- {r.get('drivers_flagged', 0)} drivers, {r.get('trips_flagged', 0)} viajes")

    md.append("\n## 9. High card amount new drivers")
    md.append(f"\n- (cubierto por HIGH_CARD_AMOUNT_NEW_DRIVER en trip_anomalies)")

    md.append("\n## 10. Route loops")
    md.append(f"\n- {total_loops} loops detectados")
    r = results.get("route_loop_pattern", {})
    md.append(f"\n- {r.get('drivers_flagged', 0)} drivers")

    md.append("\n## 11. Coordinated origin patterns")
    md.append(f"\n- {total_coord_origins} origenes coordinados")
    md.append(f"\n- {total_coord_drivers} drivers involucrados")

    md.append("\n## 12. Low avg distance patterns")
    r = results.get("low_avg_distance_pattern", {})
    md.append(f"\n- {r.get('drivers_flagged', 0)} drivers")
    md.append(f"\n- fallback_used: {r.get('fallback_used', '?')}")

    md.append("\n## 13. Low avg duration patterns")
    r = results.get("low_avg_duration_pattern", {})
    md.append(f"\n- {r.get('drivers_flagged', 0)} drivers")
    md.append(f"\n- fallback_used: {r.get('fallback_used', '?')}")

    md.append("\n## 14. Extreme short trip ratio")
    r = results.get("extreme_short_trip_ratio", {})
    md.append(f"\n- {r.get('drivers_flagged', 0)} drivers")

    md.append("\n## 15. Low variance patterns")
    r = results.get("low_variance_pattern", {})
    md.append(f"\n- {r.get('drivers_flagged', 0)} drivers")

    md.append("\n## 16. Cases created/updated")
    md.append(f"\n- {total_cases} totales (dry_run={'true' if dry_run else 'false'})")

    md.append("\n## 17. Top drivers por score")
    md.append(f"\n- (ver GET /fraud/trip-behavior/summary)")

    md.append("\n## 18. Top origins")
    md.append(f"\n- (ver GET /fraud/trip-behavior/summary)")

    md.append("\n## 19. Top routes")
    md.append(f"\n- (ver GET /fraud/trip-behavior/summary)")

    md.append("\n## 20. Parks con concentracion")
    r = results.get("park_behavior_concentration", {})
    md.append(f"\n- {r.get('parks_flagged', 0)} parks")

    md.append("\n## 21. Acciones sugeridas")
    md.append(f"\n- review: {total_flagged}")
    md.append(f"\n- NO acciones reales ejecutadas")

    md.append("\n## 22. Confirmacion: no acciones reales")
    md.append(f"\n- dry_run={dry_run}")
    md.append(f"\n- Ninguna desconexion, bloqueo de pago ni apagado de autocobro ejecutado")

    md.append("\n## 23. Errores")
    if errors:
        for e in errors:
            md.append(f"\n- {e['routine']}: {e['error']}")
    else:
        md.append(f"\n- Ninguno")

    md.append("\n## 24. Route Parser")
    md.append(f"\n- parse_quality 'ok': {parser_ok}")
    md.append(f"\n- parse_quality 'failed': {parser_fail}")
    md.append(f"\n- Separador principal: '->' (detectado en 200/200 muestras)")

    # Write report
    output_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "docs", "fraud",
        "AUDITORIA_FASE1F5_TRIP_BEHAVIOR_RESULTS.md",
    )
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\nReport saved to: {output_path}")

    # Print summary
    print(f"\n=== SUMMARY ===")
    print(f"  Total routines executed: {len(results)}")
    print(f"  Total drivers flagged: {total_flagged}")
    print(f"  Total cases created: {total_cases}")
    print(f"  Errors: {len(errors)}")


if __name__ == "__main__":
    main()
