"""
CF-H2G — Run Canonical Source Mapper for Lima

Usage:
    python -m scripts.cf_h2g_run_mapper --date 2026-06-10
    python -m scripts.cf_h2g_run_mapper --date-from 2026-06-01 --date-to 2026-06-11
    python -m scripts.cf_h2g_run_mapper --date-from 2026-06-01 --date-to 2026-06-11 --dry-run
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cf_h2g_mapper")

PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"


def main():
    parser = argparse.ArgumentParser(description="CF-H2G Canonical Source Mapper")
    parser.add_argument("--date", type=str, help="Single date YYYY-MM-DD")
    parser.add_argument("--date-from", type=str, help="Start date YYYY-MM-DD")
    parser.add_argument("--date-to", type=str, help="End date YYYY-MM-DD")
    parser.add_argument("--park-id", type=str, default=PARK_ID)
    parser.add_argument("--dry-run", action="store_true", help="Generate but do not save")
    parser.add_argument("--last-n-days", type=int, default=0, help="Map last N days")
    parser.add_argument("--show-registry", action="store_true", help="Show metric registry and exit")
    args = parser.parse_args()

    from app.services.cf_h2g_canonical_mapper_service import (
        get_metric_registry,
        generate_canonical_day_fact,
        save_canonical_day_fact,
        run_mapper_for_date_range,
    )

    if args.show_registry:
        registry = get_metric_registry()
        for r in registry:
            print(f"  {r['metric_name']:<30} owner={r['canonical_owner']:<20} "
                  f"badge={r['source_badge']:<15} status={r['promotion_status']}")
        print(f"\nTotal active metrics: {len(registry)}")
        return

    if args.last_n_days > 0:
        today = date.today()
        date_from = (today - timedelta(days=args.last_n_days)).isoformat()
        date_to = today.isoformat()
    elif args.date:
        date_from = args.date
        date_to = args.date
    elif args.date_from:
        date_from = args.date_from
        date_to = args.date_to or date.today().isoformat()
    else:
        date_from = date.today().isoformat()
        date_to = date.today().isoformat()

    logger.info("CF-H2G Mapper: date_from=%s date_to=%s park=%s dry_run=%s",
                date_from, date_to, args.park_id, args.dry_run)

    if args.dry_run:
        logger.info("DRY RUN — generating facts without saving")
        d = date.fromisoformat(date_from)
        d_end = date.fromisoformat(date_to)
        while d <= d_end:
            target = d.isoformat()
            fact = generate_canonical_day_fact(target, args.park_id)
            logger.info("  %s | trips=%s rev=%.2f gmv=%.2f drivers=%s "
                        "fallback=%s badge_trips=%s badge_rev=%s",
                        target,
                        fact.get("completed_trips_value"),
                        fact.get("revenue_yego_value"),
                        fact.get("gmv_total_value"),
                        fact.get("active_drivers_value"),
                        fact.get("fallback_used"),
                        fact.get("completed_trips_source_badge"),
                        fact.get("revenue_yego_source_badge"))
            d += timedelta(days=1)
        return

    result = run_mapper_for_date_range(date_from, date_to, args.park_id)

    logger.info("Mapper complete: %d dates covered, %d fallback dates, %d errors",
                result["total_dates"], result["fallback_count"], len(result["errors"]))

    for r in result["results"]:
        logger.info("  %s | saved=%s fallback=%s trips=%s rev=%.2f gmv=%.2f",
                    r["date"], r["saved"], r["fallback_used"],
                    r["completed_trips"], r["revenue_yego"], r["gmv"])

    if result["errors"]:
        logger.warning("Errors:")
        for e in result["errors"]:
            logger.warning("  %s: %s", e["date"], e["error"])

    print(f"\n{'='*60}")
    print(f"CF-H2G Mapper Summary")
    print(f"{'='*60}")
    print(f"  Dates covered:   {result['total_dates']}")
    print(f"  Fallback dates:  {result['fallback_count']}")
    print(f"  Errors:          {len(result['errors'])}")
    print(f"  Mapper version:  {result['mapper_version']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
