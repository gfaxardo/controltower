"""Fase 1F-8 — Autocobro Eligibility Preview Script.

Simula elegibilidad de autocobro usando politica deterministica.
Genera preview de distribucion. NO ejecuta accion real.

Uso:
    python fraud_autocobro_eligibility_preview.py --policy-version autocobro_v1_preview --dry-run true
    python fraud_autocobro_eligibility_preview.py --policy-version autocobro_v1_preview --dry-run false
    python fraud_autocobro_eligibility_preview.py --policy-version autocobro_v1_preview --dry-run true --limit 100
"""
import sys, os, argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.fraud.fraud_autocobro_eligibility_service import (
    recompute_autocobro_eligibility, get_autocobro_eligibility_summary,
    DEFAULT_POLICY,
)


def main():
    parser = argparse.ArgumentParser(description="Autocobro eligibility preview (F1F-8)")
    parser.add_argument("--policy-version", type=str, default=DEFAULT_POLICY)
    parser.add_argument("--dry-run", type=str, default="true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--park-id", type=str, default=None)
    args = parser.parse_args()

    dry_run = args.dry_run.lower() in ("true", "1", "yes")

    print(f"=== AUTOCOBRO ELIGIBILITY PREVIEW (F1F-8) ===")
    print(f"  Policy version: {args.policy_version}")
    print(f"  Dry run: {dry_run}")
    print(f"  Limit: {args.limit or 'none (full universe)'}")
    if args.park_id:
        print(f"  Park ID: {args.park_id}")

    result = recompute_autocobro_eligibility(
        policy_version=args.policy_version,
        dry_run=dry_run,
        limit=args.limit,
        park_id=args.park_id,
    )

    dist = result["distribution"]
    total = result["total_evaluated"]

    print(f"\n=== PREVIEW RESULTS ===")
    print(f"  Total drivers evaluated: {total}")
    print(f"  Eligible:           {dist.get('eligible', 0):>6}  ({_pct(dist.get('eligible', 0), total)})")
    print(f"  Near Eligible:      {dist.get('near_eligible', 0):>6}  ({_pct(dist.get('near_eligible', 0), total)})")
    print(f"  Review Required:    {dist.get('review_required', 0):>6}  ({_pct(dist.get('review_required', 0), total)})")
    print(f"  Stale Profile:      {dist.get('stale_profile', 0):>6}  ({_pct(dist.get('stale_profile', 0), total)})")
    print(f"  Profile Gap:        {dist.get('profile_gap', 0):>6}  ({_pct(dist.get('profile_gap', 0), total)})")
    print(f"  Restricted:         {dist.get('restricted', 0):>6}  ({_pct(dist.get('restricted', 0), total)})")
    print(f"  Unknown:            {dist.get('unknown', 0):>6}  ({_pct(dist.get('unknown', 0), total)})")
    print(f"  Unclassified:       {dist.get('unclassified', 0):>6}  ({_pct(dist.get('unclassified', 0), total)})")

    if result["top_reasons"]:
        print(f"\n  Top reasons:")
        for item in result["top_reasons"]:
            print(f"    [{item['count']:>5}] {item['reason']}")

    if result["errors"]:
        print(f"\n  Errors: {len(result['errors'])}")
        for e in result["errors"][:5]:
            print(f"    {e['driver_id']}: {e['error']}")

    print(f"\n  Actions executed: {result['actions_executed']}")
    print(f"  External execution: {result['external_execution']}")

    if dry_run:
        print(f"\n  [DRY RUN] No snapshot written. No acciones reales ejecutadas.")
    else:
        print(f"\n  Snapshot written to fraud.autocobro_eligibility_snapshot.")
        summary = get_autocobro_eligibility_summary(args.policy_version)
        print(f"  DB summary: {summary}")

    print(f"\n=== PREVIEW COMPLETE ===")
    return result


def _pct(part, total):
    if total == 0:
        return "0.0%"
    return f"{round(part / total * 100, 1)}%"


if __name__ == "__main__":
    main()
