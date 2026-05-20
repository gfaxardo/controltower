"""Fase 1F-5 — Enhanced Daily Control Script.

Ejecuta rutinas antifraude por ventanas D-1, D-7, D-30 e historico.
Incluye rutinas conductuales Fase 1F-5.
Soporta modos: daily, weekly, monthly, historical, all.
dry_run=true por defecto.

Uso:
  python backend/scripts/fraud_daily_control.py --mode daily --dry-run true
  python backend/scripts/fraud_daily_control.py --mode daily --dry-run false
  python backend/scripts/fraud_daily_control.py --mode all --include-historical --dry-run false
"""
import sys, os, argparse
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from app.services.fraud.fraud_routine_service import run_routines, routine_driver_trust_full_universe, routine_bank_account_cluster
from app.services.fraud.fraud_behavioral_routines import run_trip_behavior_routines


def run_daily(dry_run=True, reference_date=None):
    """D-1: viajes de ayer — anomalias, clusters, burst + behavioral."""
    ref = reference_date or datetime.now().date()
    d1 = (ref - timedelta(days=1)).isoformat()
    d0 = ref.isoformat()
    print(f"\n--- DAILY (D-1: {d1}) ---")
    result = run_routines(date_from=d1, date_to=d0, limit=10000, dry_run=dry_run,
                          routines=["trip_anomalies", "pickup_clusters", "referral_abuse"])
    # Behavioral D-1
    beh = run_trip_behavior_routines(date_from=d1, date_to=d0, window_days=1, dry_run=dry_run, limit=5000,
                                     routines=["repeated_origin_pattern", "repeated_route_signature",
                                               "route_loop_pattern", "coordinated_origin_pattern"])
    if "results" not in result:
        result["results"] = {}
    result["results"]["trip_behavior_daily"] = beh
    return result


def run_weekly(dry_run=True, reference_date=None):
    """D-7: patrones semanales, actividad explosiva + behavioral."""
    ref = reference_date or datetime.now().date()
    d7 = (ref - timedelta(days=7)).isoformat()
    d0 = ref.isoformat()
    print(f"\n--- WEEKLY (D-7: {d7}) ---")
    result = run_routines(date_from=d7, date_to=d0, limit=20000, dry_run=dry_run,
                          routines=["trip_anomalies", "pickup_clusters", "referral_abuse", "park_concentration"])
    # Behavioral D-7
    beh = run_trip_behavior_routines(date_from=d7, date_to=d0, window_days=7, dry_run=dry_run, limit=10000)
    if "results" not in result:
        result["results"] = {}
    result["results"]["trip_behavior_weekly"] = beh
    return result


def run_monthly(dry_run=True, reference_date=None):
    """D-30: acumulacion de riesgo + behavioral completo."""
    ref = reference_date or datetime.now().date()
    d30 = (ref - timedelta(days=30)).isoformat()
    d0 = ref.isoformat()
    print(f"\n--- MONTHLY (D-30: {d30}) ---")
    result = run_routines(date_from=d30, date_to=d0, limit=50000, dry_run=dry_run, full_universe=True,
                          routines=["driver_trust", "park_concentration"])
    # Behavioral D-30: rutinas pesadas (baseline, variance, farming)
    beh = run_trip_behavior_routines(date_from=d30, date_to=d0, window_days=30, dry_run=dry_run, limit=20000,
                                     routines=["low_avg_distance_pattern", "low_avg_duration_pattern",
                                               "extreme_short_trip_ratio", "low_variance_pattern",
                                               "short_trip_farming", "long_trip_outlier_v2",
                                               "behavioral_driver_profile", "park_behavior_concentration"])
    if "results" not in result:
        result["results"] = {}
    result["results"]["trip_behavior_monthly"] = beh
    return result


def run_historical(dry_run=True):
    """Historico: full universe driver trust + bank cluster."""
    print("\n--- HISTORICAL ---")
    result = run_routines(dry_run=dry_run, full_universe=True,
                          routines=["driver_trust"])
    bank_result = routine_bank_account_cluster(dry_run=dry_run)
    if "results" not in result:
        result["results"] = {}
    result["results"]["bank_account_cluster"] = bank_result
    return result


def main():
    parser = argparse.ArgumentParser(description="Fraud daily control")
    parser.add_argument("--mode", default="daily", choices=["daily", "weekly", "monthly", "historical", "all"])
    parser.add_argument("--date", default=None, help="Reference date YYYY-MM-DD")
    parser.add_argument("--dry-run", type=str, default="true")
    parser.add_argument("--include-historical", type=str, default="false")
    args = parser.parse_args()

    dry_run = args.dry_run.lower() in ("true", "1", "yes")
    include_hist = args.include_historical.lower() in ("true", "1", "yes")
    ref_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None

    print(f"FRAUD DAILY CONTROL — mode={args.mode}, dry_run={dry_run}")

    results = {}
    mode = args.mode

    if mode in ("daily", "all"):
        results["daily"] = run_daily(dry_run, ref_date)
    if mode in ("weekly", "all"):
        results["weekly"] = run_weekly(dry_run, ref_date)
    if mode in ("monthly", "all"):
        results["monthly"] = run_monthly(dry_run, ref_date)
    if mode in ("historical", "all") and (include_hist or mode == "historical"):
        results["historical"] = run_historical(dry_run)

    print("\n=== DAILY CONTROL SUMMARY ===")
    for mode_name, r in results.items():
        total_trips = r.get("total_trips_analyzed", 0)
        total_flags = r.get("total_flags", 0)
        total_cases = r.get("total_cases_created", 0)
        print(f"  {mode_name}: trips={total_trips} flags={total_flags} cases={total_cases}")
        if r.get("results"):
            for k, v in r["results"].items():
                if isinstance(v, dict):
                    print(f"    {k}: drivers_flagged={v.get('total_drivers_flagged', v.get('drivers_flagged', '?'))}")
                else:
                    print(f"    {k}: {v}")
        if r.get("errors"):
            print(f"    errors: {r['errors']}")

    print(f"\nMODE: {'dry_run' if dry_run else 'COMMIT (snapshots/cases written)'}")
    if not dry_run:
        print("WARNING: Real data written. Use with caution.")


if __name__ == "__main__":
    main()
