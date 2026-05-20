"""Fase 1F — Fraud Recompute Script.

Uso:
  python backend/scripts/fraud_recompute.py --date-from 2026-05-01 --date-to 2026-05-19 --limit 10000 --dry-run true
  python backend/scripts/fraud_recompute.py --date-from 2026-05-01 --date-to 2026-05-19 --limit 10000 --dry-run false
"""
import sys, os, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__))))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.fraud.fraud_routine_service import run_routines


def main():
    parser = argparse.ArgumentParser(description="Fraud recompute")
    parser.add_argument("--date-from", default=None)
    parser.add_argument("--date-to", default=None)
    parser.add_argument("--driver-id", default=None)
    parser.add_argument("--park-id", default=None)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--dry-run", type=str, default="true")
    parser.add_argument("--routines", default=None, help="Comma-separated")
    parser.add_argument("--full-universe", type=str, default="false", help="Use full universe driver trust")
    args = parser.parse_args()

    dry_run = args.dry_run.lower() in ("true", "1", "yes")
    full_universe = args.full_universe.lower() in ("true", "1", "yes")
    routines = [r.strip() for r in args.routines.split(",")] if args.routines else None

    print(f"FRAUD RECOMPUTE — dry_run={dry_run}, limit={args.limit}, full_universe={full_universe}")
    if args.date_from:
        print(f"  date_from={args.date_from}")
    if args.date_to:
        print(f"  date_to={args.date_to}")

    result = run_routines(
        date_from=args.date_from, date_to=args.date_to,
        driver_id=args.driver_id, park_id=args.park_id,
        limit=args.limit, dry_run=dry_run, routines=routines,
        full_universe=full_universe,
    )

    print("\n=== SUMMARY ===")
    print(f"  dry_run: {result['dry_run']}")
    print(f"  trips_analyzed: {result['total_trips_analyzed']}")
    print(f"  flags_raised: {result['total_flags']}")
    print(f"  cases_created: {result['total_cases_created']}")
    if result["errors"]:
        print(f"  errors: {len(result['errors'])}")
        for e in result["errors"]:
            print(f"    - {e['routine']}: {e['error']}")


if __name__ == "__main__":
    main()
