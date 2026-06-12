"""
CF-H2F.1 — Business Slice Mapping Validator

Cross-walks Yango orders through dim.yango_category_to_slice
and compares against CT ops.real_business_slice_day_fact per slice.

Usage:
    python -m scripts.cf_h2f1_validate_mapping --date 2026-06-10
    python -m scripts.cf_h2f1_validate_mapping --date-from 2026-06-01 --date-to 2026-06-11
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, timedelta
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cf_h2f1_validate")

PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"
MAPPING_TABLE = "dim.yango_category_to_slice"


def _get_db():
    import sys
    sys.path.insert(0, "backend")
    from app.db.connection import get_db
    return get_db()


def get_mapping() -> Dict[str, str]:
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT yango_category, business_slice_name, confidence, mapping_status "
            f"FROM {MAPPING_TABLE} WHERE park_id = %(p)s AND mapping_status = 'MAPPED'",
            {"p": PARK_ID}
        )
        return {r[0]: r[1] for r in cur.fetchall()}


def get_yango_by_slice(target_date: str, mapping: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT "
            "  COALESCE(raw_payload->>'category', 'UNKNOWN') AS cat, "
            "  COUNT(DISTINCT order_id) AS completed_trips, "
            "  COUNT(DISTINCT driver_profile_id) AS active_drivers "
            "FROM raw_yango.orders_raw "
            "WHERE park_id = %(p)s "
            "  AND order_status = 'complete' "
            "  AND order_ended_at::date = %(d)s "
            "GROUP BY 1",
            {"p": PARK_ID, "d": target_date}
        )
        result: Dict[str, Dict[str, Any]] = {}
        unmapped = 0
        for r in cur.fetchall():
            cat = r[0]
            slice_name = mapping.get(cat)
            if not slice_name:
                slice_name = "unmapped"
                unmapped += 1
            if slice_name not in result:
                result[slice_name] = {"completed_trips": 0, "active_drivers": 0, "yango_categories": []}
            result[slice_name]["completed_trips"] += int(r[1] or 0)
            result[slice_name]["active_drivers"] += int(r[2] or 0)
            result[slice_name]["yango_categories"].append(cat)

        if unmapped > 0:
            logger.warning("  %s unmapped categories for date %s", unmapped, target_date)

    return result


def get_ct_by_slice(target_date: str) -> Dict[str, Dict[str, Any]]:
    with _get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT business_slice_name, "
            "  SUM(trips_completed) AS trips, "
            "  SUM(active_drivers) AS drivers, "
            "  SUM(revenue_yego_final) AS revenue "
            "FROM ops.real_business_slice_day_fact "
            "WHERE LOWER(TRIM(country)) = 'peru' "
            "  AND LOWER(TRIM(city)) = 'lima' "
            "  AND trip_date = %(d)s "
            "GROUP BY business_slice_name",
            {"d": target_date}
        )
        return {
            r[0]: {
                "trips_completed": int(r[1] or 0),
                "active_drivers": int(r[2] or 0),
                "revenue_yego_final": float(r[3] or 0),
            }
            for r in cur.fetchall()
        }


def validate_date(target_date: str) -> Dict[str, Any]:
    mapping = get_mapping()
    yango_slices = get_yango_by_slice(target_date, mapping)
    ct_slices = get_ct_by_slice(target_date)

    all_slices = sorted(set(list(yango_slices.keys()) + list(ct_slices.keys())))

    results = []
    total_yango = 0
    total_ct = 0
    pass_count = 0
    warn_count = 0
    fail_count = 0

    for slice_name in all_slices:
        y = yango_slices.get(slice_name, {"completed_trips": 0, "active_drivers": 0})
        c = ct_slices.get(slice_name, {"trips_completed": 0, "active_drivers": 0})

        y_trips = y["completed_trips"]
        c_trips = c["trips_completed"]
        total_yango += y_trips
        total_ct += c_trips

        if y_trips == 0 and c_trips == 0:
            continue

        delta_abs = y_trips - c_trips
        delta_pct = round(delta_abs / c_trips * 100, 2) if c_trips > 0 else None

        if delta_pct is None:
            status = "WARN" if y_trips > 0 else "PASS"
            reason = "Yang-only slice (CT has 0)" if y_trips > 0 else "CT-only slice"
        elif abs(delta_pct) <= 5:
            status = "PASS"
            reason = "Within 5% threshold"
            pass_count += 1
        elif abs(delta_pct) <= 15:
            status = "WARN"
            reason = f"Delta {delta_pct}% exceeds 5%"
            warn_count += 1
        else:
            status = "FAIL"
            reason = f"Delta {delta_pct}% exceeds 15%"
            fail_count += 1

        results.append({
            "slice_name": slice_name,
            "yango_trips": y_trips,
            "ct_trips": c_trips,
            "delta_abs": delta_abs,
            "delta_pct": delta_pct,
            "status": status,
            "reason": reason,
            "yango_categories": y.get("yango_categories", []),
        })

    overall = "PASS" if fail_count == 0 and warn_count <= 2 else "WARN" if fail_count == 0 else "FAIL"

    return {
        "date": target_date,
        "overall": overall,
        "total_yango_trips": total_yango,
        "total_ct_trips": total_ct,
        "total_delta_abs": total_yango - total_ct,
        "total_delta_pct": round((total_yango - total_ct) / total_ct * 100, 2) if total_ct > 0 else None,
        "pass_count": pass_count,
        "warn_count": warn_count,
        "fail_count": fail_count,
        "slices": results,
    }


def main():
    parser = argparse.ArgumentParser(description="CF-H2F.1 Business Slice Mapping Validator")
    parser.add_argument("--date", type=str)
    parser.add_argument("--date-from", type=str)
    parser.add_argument("--date-to", type=str)
    parser.add_argument("--last-n-days", type=int, default=0)
    parser.add_argument("--show-mapping", action="store_true")
    args = parser.parse_args()

    if args.show_mapping:
        mapping = get_mapping()
        print(f"{'Yango Category':<20} -> {'CT Business Slice':<25}")
        print("-" * 50)
        for cat, sl in sorted(mapping.items()):
            print(f"{cat:<20} -> {sl:<25}")
        print(f"\nTotal mapped categories: {len(mapping)}")
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

    d = date.fromisoformat(date_from)
    d_end = date.fromisoformat(date_to)

    all_results = []
    total_pass = total_warn = total_fail = 0

    while d <= d_end:
        target = d.isoformat()
        result = validate_date(target)
        all_results.append(result)

        status_icon = "PASS" if result["overall"] == "PASS" else "WARN" if result["overall"] == "WARN" else "FAIL"
        logger.info("  %s | %s | y=%s ct=%s delta=%s%% | slices: P=%s W=%s F=%s",
                    target, status_icon,
                    result["total_yango_trips"], result["total_ct_trips"],
                    result["total_delta_pct"],
                    result["pass_count"], result["warn_count"], result["fail_count"])

        if result["overall"] == "PASS":
            total_pass += 1
        elif result["overall"] == "WARN":
            total_warn += 1
        else:
            total_fail += 1

        d += timedelta(days=1)

    print(f"\n{'='*60}")
    print(f"CF-H2F.1 Business Slice Mapping Validation Summary")
    print(f"{'='*60}")
    print(f"  Dates analyzed:  {len(all_results)}")
    print(f"  PASS: {total_pass}  WARN: {total_warn}  FAIL: {total_fail}")

    if all_results:
        last = all_results[-1]
        print(f"\n  Last date ({last['date']}) per-slice breakdown:")
        for s in last["slices"]:
            print(f"    {s['slice_name']:<25} y={s['yango_trips']:>6} ct={s['ct_trips']:>6} "
                  f"delta={str(s['delta_pct'])+'%' if s['delta_pct'] else 'N/A':>8} "
                  f"[{s['status']}] {s['reason']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
