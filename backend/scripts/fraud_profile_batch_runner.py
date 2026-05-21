"""Fase 1F-8 — Behavioral Profile Batch Runner (Fixed).

Ejecuta routine_behavioral_driver_profile sobre universo completo de drivers
usando batching con OFFSET real para evitar timeout y procesar todo el universo.

Uso:
    python fraud_profile_batch_runner.py --dry-run true
    python fraud_profile_batch_runner.py --dry-run false --batch-size 500 --resume-from 0
    python fraud_profile_batch_runner.py --dry-run false --batch-size 500 --config-version trip_behavior_v1_calibrated
"""
import sys, os, time, argparse
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.fraud.fraud_behavioral_routines import run_trip_behavior_routines
from app.db.connection import get_db

DEFAULT_CONFIG_VERSION = "trip_behavior_v1_calibrated"


def run_profiles(dry_run=True, batch_size=500, resume_offset=0, total_drivers=None,
                 config_version=DEFAULT_CONFIG_VERSION, date_to=None):
    with get_db() as conn:
        cur = conn.cursor()

        if total_drivers is None:
            cur.execute("SELECT COUNT(*) FROM fraud.driver_trust_snapshot")
            total_drivers = cur.fetchone()[0] or 0

        cur.close()

    ref_date = date_to or date.today()
    date_from_str = (ref_date - timedelta(days=30)).isoformat()
    date_to_str = ref_date.isoformat()

    print(f"=== BEHAVIORAL PROFILE BATCH RUNNER (F1F-8) ===")
    print(f"  Total drivers in trust snapshot: {total_drivers}")
    print(f"  Batch size: {batch_size}")
    print(f"  Resume offset: {resume_offset}")
    print(f"  Date range: {date_from_str} -> {date_to_str}")
    print(f"  Config version: {config_version}")
    print(f"  Dry run: {dry_run}")

    batches = max((total_drivers - resume_offset + batch_size - 1) // batch_size, 1)
    total_profiled = 0
    total_elapsed = 0
    errors_accumulated = []

    for batch_num in range(batches):
        batch_start = resume_offset + batch_num * batch_size

        if batch_start >= total_drivers:
            print(f"\nBatch {batch_num+1}/{batches}: offset {batch_start} >= total {total_drivers}. Done.")
            break

        print(f"\nBatch {batch_num+1}/{batches} (offset {batch_start}, limit {batch_size})")
        t0 = time.time()

        result = run_trip_behavior_routines(
            date_from=date_from_str, date_to=date_to_str,
            window_days=30, dry_run=dry_run, limit=batch_size,
            offset=batch_start,
            routines=["behavioral_driver_profile"],
        )

        elapsed = round(time.time() - t0, 1)
        total_elapsed += elapsed

        r = result.get("routines", {}).get("behavioral_driver_profile", {})
        drivers_profiled = r.get("drivers_profiled", 0)
        total_profiled += drivers_profiled

        errors = result.get("errors", [])
        if errors:
            errors_accumulated.extend(errors)

        print(f"  -> {drivers_profiled} profiled in {elapsed}s  |  running total: {total_profiled}")

        if drivers_profiled == 0:
            print(f"  -> No drivers returned. Universe exhausted or no more data.")
            break

    print(f"\n=== BATCH RUN COMPLETE ===")
    print(f"  Total profiled: {total_profiled}")
    print(f"  Total elapsed: {total_elapsed}s ({round(total_elapsed/60,1)} min)")
    print(f"  Errors: {len(errors_accumulated)}")

    if dry_run:
        print("  [DRY RUN] No data written.")
    else:
        # Verify coverage
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM fraud.driver_risk_snapshot")
            total_risk = cur.fetchone()[0] or 0
            cur.execute("SELECT COUNT(*) FROM fraud.driver_risk_snapshot WHERE behavioral_profile_class IS NOT NULL")
            profiled = cur.fetchone()[0] or 0
            cur.execute("""
                SELECT behavioral_profile_class, COUNT(*)
                FROM fraud.driver_risk_snapshot
                WHERE behavioral_profile_class IS NOT NULL
                GROUP BY behavioral_profile_class
                ORDER BY COUNT(*) DESC
            """)
            print(f"\n  driver_risk_snapshot: {total_risk}")
            pct = round(profiled / max(total_risk, 1) * 100, 1)
            print(f"  with behavioral_profile: {profiled} ({pct}%)")
            for row in cur.fetchall():
                print(f"    {row[0]}: {row[1]}")
            cur.close()

    return {
        "total_profiled": total_profiled,
        "total_elapsed": total_elapsed,
        "errors": len(errors_accumulated),
        "dry_run": dry_run,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch run behavioral driver profiles (F1F-8)")
    parser.add_argument("--dry-run", type=str, default="true")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--resume-from", type=int, default=0)
    parser.add_argument("--config-version", type=str, default=DEFAULT_CONFIG_VERSION)
    parser.add_argument("--date-to", type=str, default=None, help="Reference date YYYY-MM-DD")
    args = parser.parse_args()

    dry = args.dry_run.lower() in ("true", "1", "yes")
    ref = date.fromisoformat(args.date_to) if args.date_to else None
    run_profiles(
        dry_run=dry, batch_size=args.batch_size,
        resume_offset=args.resume_from,
        config_version=args.config_version,
        date_to=ref,
    )
