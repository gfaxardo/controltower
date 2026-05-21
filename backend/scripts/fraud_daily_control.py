"""Fase 1F-7 — Hardened Daily Control Script.

Ejecuta rutinas antifraude segun schedule config (daily/weekly/monthly).
Soporta: config_version, max_cases_per_run, frequency tracking en routine_run_log.

Uso:
  python fraud_daily_control.py --mode daily --dry-run true
  python fraud_daily_control.py --mode daily --dry-run false --config-version trip_behavior_v1_calibrated --max-cases-per-run 50
  python fraud_daily_control.py --mode all --dry-run true
"""
import sys, os, argparse, time
from datetime import datetime, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.connection import get_db
from app.services.fraud.fraud_behavioral_routines import run_trip_behavior_routines

DEFAULT_CONFIG_VERSION = "trip_behavior_v1_calibrated"
DEFAULT_MAX_CASES = 50

# ── Fallback schedule (usado si routine_schedule_config no existe) ──
FALLBACK_SCHEDULE = {
    "daily": [
        "repeated_origin_pattern", "low_avg_distance_pattern",
        "low_avg_duration_pattern", "extreme_short_trip_ratio",
        "low_variance_pattern", "short_trip_farming",
        "park_behavior_concentration",
    ],
    "weekly": [
        "repeated_route_signature", "route_loop_pattern",
        "coordinated_origin_pattern", "long_trip_outlier_v2",
    ],
    "monthly": [
        "behavioral_driver_profile", "park_behavior_concentration",
    ],
}


def load_schedule(frequency: str) -> list:
    """Carga rutinas programadas para una frecuencia desde fraud.routine_schedule_config."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT routine_name, max_runtime_seconds
                FROM fraud.routine_schedule_config
                WHERE frequency = %s AND enabled = true
                ORDER BY routine_name
            """, (frequency,))
            rows = cur.fetchall()
            cur.close()
            if rows:
                return [(r[0], r[1]) for r in rows]
    except Exception:
        pass
    # Fallback
    names = FALLBACK_SCHEDULE.get(frequency, [])
    return [(n, None) for n in names]


def log_frequency_entry(run_code: str, frequency: str):
    """Actualiza routine_run_log con la frecuencia."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE fraud.routine_run_log
                SET frequency = %s
                WHERE run_code = %s
            """, (frequency, run_code))
            conn.commit()
            cur.close()
    except Exception:
        pass


def run_frequency_mode(frequency: str, dry_run=True, reference_date=None,
                       config_version=DEFAULT_CONFIG_VERSION, max_cases_per_run=DEFAULT_MAX_CASES,
                       window_days_override=None):
    ref = reference_date or datetime.now().date()

    # Window days by frequency
    if window_days_override:
        window_days = window_days_override
    elif frequency == "daily":
        window_days = 1
    elif frequency == "weekly":
        window_days = 7
    elif frequency == "monthly":
        window_days = 30
    else:
        window_days = 7

    date_from = (ref - timedelta(days=window_days)).isoformat()
    date_to = ref.isoformat()

    routines = load_schedule(frequency)
    routine_names = [r[0] for r in routines]

    print(f"\n{'='*60}")
    print(f"  {frequency.upper()} RUN (D-{window_days}: {date_from} to {date_to})")
    print(f"  Routines: {routine_names}")
    print(f"  Dry run: {dry_run}")
    print(f"  Config: {config_version}")
    print(f"  Max cases: {max_cases_per_run}")
    print(f"{'='*60}")

    t0 = time.time()

    result = run_trip_behavior_routines(
        date_from=date_from, date_to=date_to,
        window_days=window_days, dry_run=dry_run,
        limit=2000 if frequency == "monthly" else (500 if frequency == "daily" else 1000),
        routines=routine_names,
    )

    elapsed = round(time.time() - t0, 1)

    freq_result = {
        "frequency": frequency,
        "window_days": window_days,
        "date_from": date_from,
        "date_to": date_to,
        "dry_run": dry_run,
        "config_version": config_version,
        "elapsed_seconds": elapsed,
        "routines_executed": len(routine_names),
        "routines_errored": len(result.get("errors", [])),
        "total_signal_flags": result.get("total_signal_flags", 0),
        "total_candidates": result.get("total_candidates", 0),
        "total_cases_created": result.get("total_cases_created", 0),
        "total_suppressed": result.get("total_suppressed", 0),
        "by_routine": {},
        "errors": result.get("errors", []),
    }

    for name in routine_names:
        r = result.get("routines", {}).get(name, {})
        freq_result["by_routine"][name] = {
            "cases": r.get("cases_created", 0),
            "candidates": r.get("candidates", 0),
            "signals": r.get("signal_flags", 0),
            "suppressed": r.get("suppressed", 0),
            "elapsed": r.get("elapsed_seconds", 0),
        }

    return freq_result


def print_summary(freq_result):
    fr = freq_result
    print(f"\n  [{fr['frequency'].upper()} SUMMARY]")
    print(f"  Runtime: {fr['elapsed_seconds']}s")
    print(f"  Signals: {fr['total_signal_flags']} | Candidates: {fr['total_candidates']} "
          f"| Cases: {fr['total_cases_created']} | Suppressed: {fr['total_suppressed']}")
    if fr.get("by_routine"):
        for name, r in fr["by_routine"].items():
            print(f"    {name}: cases={r['cases']} cand={r['candidates']} "
                  f"sig={r['signals']} sup={r['suppressed']} t={r['elapsed']}s")
    if fr.get("errors"):
        print(f"  Errors: {fr['errors']}")


def main():
    parser = argparse.ArgumentParser(description="Fraud daily control — schedule-based")
    parser.add_argument("--mode", default="daily", choices=["daily", "weekly", "monthly", "all"])
    parser.add_argument("--date", default=None, help="Reference date YYYY-MM-DD")
    parser.add_argument("--dry-run", type=str, default="true")
    parser.add_argument("--config-version", type=str, default=DEFAULT_CONFIG_VERSION)
    parser.add_argument("--max-cases-per-run", type=int, default=DEFAULT_MAX_CASES)
    args = parser.parse_args()

    dry_run = args.dry_run.lower() in ("true", "1", "yes")
    ref_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None

    print(f"FRAUD DAILY CONTROL — F1F-7")
    print(f"  mode: {args.mode}, dry_run: {dry_run}, config: {args.config_version}")
    print(f"  max_cases_per_run: {args.max_cases_per_run}")

    all_results = {}
    modes_to_run = ["daily", "weekly", "monthly"] if args.mode == "all" else [args.mode]

    for mode in modes_to_run:
        try:
            fr = run_frequency_mode(mode, dry_run=dry_run, reference_date=ref_date,
                                    config_version=args.config_version,
                                    max_cases_per_run=args.max_cases_per_run)
            all_results[mode] = fr
            print_summary(fr)
        except Exception as e:
            print(f"\n  [{mode.upper()} FAILED]: {e}")
            all_results[mode] = {"frequency": mode, "error": str(e)}

    # Final summary
    print(f"\n{'='*60}")
    print(f"=== FINAL SUMMARY ===")
    total_cases = 0
    total_suppressed = 0
    total_errors = 0
    for mode, fr in all_results.items():
        tc = fr.get("total_cases_created", 0)
        ts = fr.get("total_suppressed", 0)
        te = len(fr.get("errors", []))
        total_cases += tc
        total_suppressed += ts
        total_errors += te
        print(f"  {mode}: cases={tc} suppressed={ts} errors={te} runtime={fr.get('elapsed_seconds', '?')}s")
    print(f"  TOTAL: cases={total_cases} suppressed={total_suppressed} errors={total_errors}")

    mode_str = "DRY_RUN" if dry_run else "COMMIT"
    print(f"\n  MODE: {mode_str}")
    if not dry_run:
        print("  WARNING: Real data written. Verify before commit.")


if __name__ == "__main__":
    main()
