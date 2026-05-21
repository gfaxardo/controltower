"""Fase 1F-7 — Behavioral Profile Batch Runner.

Ejecuta routine_behavioral_driver_profile sobre universo completo de drivers
usando batching para evitar timeout.

Uso:
    python fraud_profile_batch_runner.py --dry-run true
    python fraud_profile_batch_runner.py --dry-run false --batch-size 500 --resume-from 0
"""
import sys, os, time, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.fraud.fraud_behavioral_routines import run_trip_behavior_routines
from app.db.connection import get_db


def run_profiles(dry_run=True, batch_size=500, resume_offset=0, total_drivers=None):
    with get_db() as conn:
        cur = conn.cursor()

        # Get total driver count for progress
        if total_drivers is None:
            cur.execute("SELECT COUNT(*) FROM fraud.driver_trust_snapshot")
            total_drivers = cur.fetchone()[0] or 0

        cur.close()

    print(f"=== BEHAVIORAL PROFILE BATCH RUNNER ===")
    print(f"  Total drivers in trust snapshot: {total_drivers}")
    print(f"  Batch size: {batch_size}")
    print(f"  Resume offset: {resume_offset}")
    print(f"  Dry run: {dry_run}")

    batches = (total_drivers - resume_offset + batch_size - 1) // batch_size
    total_profiled = 0
    total_elapsed = 0
    errors_accumulated = []

    for batch_num in range(batches):
        batch_start = resume_offset + batch_num * batch_size
        batch_end = min(batch_start + batch_size, total_drivers)

        print(f"\nBatch {batch_num+1}/{batches} (offset {batch_start}-{batch_end})")
        t0 = time.time()

        result = run_trip_behavior_routines(
            date_from="2026-05-13", date_to="2026-05-20",
            window_days=30, dry_run=dry_run, limit=batch_size,
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

        print(f"  -> {drivers_profiled} profiled in {elapsed}s")

        if drivers_profiled == 0:
            print(f"  -> No drivers returned. Batch may be complete.")
            break

    print(f"\n=== BATCH RUN COMPLETE ===")
    print(f"  Total profiled: {total_profiled}")
    print(f"  Total elapsed: {total_elapsed}s")
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
            cur.execute("SELECT behavioral_profile_class, COUNT(*) FROM fraud.driver_risk_snapshot WHERE behavioral_profile_class IS NOT NULL GROUP BY behavioral_profile_class ORDER BY COUNT(*) DESC")
            print(f"\n  driver_risk_snapshot: {total_risk}")
            print(f"  with behavioral_profile: {profiled} ({round(profiled/max(total_risk,1)*100,1)}%)")
            for row in cur.fetchall():
                print(f"    {row[0]}: {row[1]}")
            cur.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch run behavioral driver profiles")
    parser.add_argument("--dry-run", type=str, default="true")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--resume-from", type=int, default=0)
    args = parser.parse_args()

    dry = args.dry_run.lower() in ("true", "1", "yes")
    run_profiles(dry_run=dry, batch_size=args.batch_size, resume_offset=args.resume_from)
