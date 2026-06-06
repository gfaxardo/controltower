#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Park Lima External Truth Reconciliation Test

Compares Fleet/API Park Lima vs OV2 Raw Landing vs Omniview V1 CT
against an optional external truth number.

Usage:
  cd backend
  python -m scripts.audit_park_lima_external_truth --start-date 2026-06-04 --external-trips 4500
  python -m scripts.audit_park_lima_external_truth --start-date 2026-06-04  (without external)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PET = timezone(timedelta(hours=-5))

PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"
PARK_NAME = "Yego (Lima)"
DEFAULT_TZ = "America/Lima"

# ── Data Sources ────────────────────────────────────────────


def _query(sql: str, params: tuple = ()) -> Any:
    from app.db.connection import get_db
    from psycopg2.extras import RealDictCursor

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        result = cur.fetchall()
        cur.close()
        return result


def _query_one(sql: str, params: tuple = ()) -> Optional[Dict]:
    rows = _query(sql, params)
    return rows[0] if rows else None


# ── OV2 Raw ─────────────────────────────────────────────────


def ov2_raw_count(
    park_id: str,
    start_dt: str,
    end_dt: str,
    time_col: str = "order_created_at",
) -> Dict[str, Any]:
    """Count completed orders in raw_yango.orders_raw."""
    row = _query_one(
        f"""
        SELECT
            COUNT(*) AS total_orders,
            COUNT(*) FILTER (WHERE order_status = 'complete') AS completed_orders,
            COUNT(*) FILTER (WHERE order_status = 'cancelled') AS cancelled_orders,
            COUNT(*) FILTER (WHERE order_status NOT IN ('complete', 'cancelled')) AS other_orders,
            MIN({time_col}) AS first_trip,
            MAX({time_col}) AS last_trip
        FROM raw_yango.orders_raw
        WHERE park_id = %s
          AND {time_col} >= %s::timestamptz
          AND {time_col} < %s::timestamptz
        """,
        (park_id, start_dt, end_dt),
    )
    if not row:
        return {"total": 0, "completed": 0, "cancelled": 0, "other": 0}
    return {
        "total": int(row["total_orders"] or 0),
        "completed": int(row["completed_orders"] or 0),
        "cancelled": int(row["cancelled_orders"] or 0),
        "other": int(row["other_orders"] or 0),
        "time_col_used": time_col,
        "first_trip": str(row.get("first_trip") or ""),
        "last_trip": str(row.get("last_trip") or ""),
    }


# ── OV2 MV ──────────────────────────────────────────────────


def ov2_mv_count(
    park_id: str,
    date_str: str,
) -> int:
    """Count completed orders from MV (already aggregated by day)."""
    row = _query_one(
        """
        SELECT COALESCE(SUM(orders_completed), 0) AS n
        FROM raw_yango.mv_orders_day
        WHERE park_id = %s AND order_date = %s::date
        """,
        (park_id, date_str),
    )
    return int(row["n"] or 0) if row else 0


# ── V1 Raw ──────────────────────────────────────────────────


def v1_raw_count(
    park_id: str,
    start_dt: str,
    end_dt: str,
) -> Dict[str, Any]:
    """Count completed trips in public.trips_all for the exact park."""
    row = _query_one(
        """
        SELECT
            COUNT(*) AS total_trips,
            COUNT(*) FILTER (WHERE condicion = 'Completado') AS completed_trips,
            COUNT(*) FILTER (WHERE condicion = 'Cancelado') AS cancelled_trips,
            COUNT(*) FILTER (WHERE condicion NOT IN ('Completado', 'Cancelado')) AS other_trips,
            MIN(fecha_inicio_viaje) AS first_trip,
            MAX(fecha_inicio_viaje) AS last_trip
        FROM public.trips_all
        WHERE park_id = %s
          AND fecha_inicio_viaje >= %s::timestamptz
          AND fecha_inicio_viaje < %s::timestamptz
        """,
        (park_id, start_dt, end_dt),
    )
    if not row or (row["total_trips"] or 0) == 0:
        # Check if any data exists for this park at all
        check = _query_one(
            "SELECT MIN(fecha_inicio_viaje) AS d1, MAX(fecha_inicio_viaje) AS d2 FROM public.trips_all WHERE park_id = %s",
            (park_id,),
        )
        return {
            "total": 0,
            "completed": 0,
            "cancelled": 0,
            "other": 0,
            "available": False,
            "note": f"V1 trips_all has NO data after {str(check['d2'])[:10] if check and check.get('d2') else 'unknown'}. Range: {str(check.get('d1','?'))[:10]} -> {str(check.get('d2','?'))[:10]}",
        }

    return {
        "total": int(row["total_trips"] or 0),
        "completed": int(row["completed_trips"] or 0),
        "cancelled": int(row["cancelled_trips"] or 0),
        "other": int(row["other_trips"] or 0),
        "available": True,
        "first_trip": str(row.get("first_trip") or ""),
        "last_trip": str(row.get("last_trip") or ""),
    }


# ── V1 CT Facts ─────────────────────────────────────────────


def v1_ct_count(
    date_str: str,
    country: str = "peru",
    city: str = "lima",
) -> Dict[str, Any]:
    """Count trips from CT serving facts for Lima (aggregated, no park_id)."""
    row = _query_one(
        """
        SELECT
            COALESCE(SUM(trips_completed), 0)::bigint AS trips,
            COALESCE(SUM(revenue_yego_final), 0)::numeric AS revenue,
            COUNT(*) AS slices
        FROM ops.real_business_slice_day_fact
        WHERE LOWER(TRIM(country)) = %s
          AND LOWER(TRIM(city)) = %s
          AND trip_date = %s::date
        """,
        (country, city, date_str),
    )
    if not row or (row["trips"] or 0) == 0:
        return {
            "trips": 0,
            "available": False,
            "note": f"CT fact table has no data for {country}/{city} on {date_str}",
        }
    return {
        "trips": int(row["trips"] or 0),
        "revenue": float(row["revenue"] or 0),
        "slices": int(row["slices"] or 0),
        "available": True,
    }


# ── Classification ──────────────────────────────────────────


def _delta_pct(a: int, b: int) -> Optional[float]:
    if b and b != 0:
        return round((a - b) / b * 100, 2)
    return None


def _classify_delta(a: int, b: int) -> str:
    d = _delta_pct(a, b)
    if d is None:
        return "NOT_COMPUTED"
    ad = abs(d)
    if ad <= 1:
        return "PASS"
    elif ad <= 5:
        return "WARNING"
    else:
        return "FAIL"


def _classify_status(result: Dict[str, Any]) -> str:
    """Classify the overall result based on external truth."""
    external = result.get("external_trips")
    ov2 = result.get("ov2_completed", 0)
    v1 = result.get("v1_completed", 0)

    if external is None:
        return "EXTERNAL_NOT_PROVIDED"

    ov2_delta = _delta_pct(ov2, external)
    v1_delta = _delta_pct(v1, external)

    if ov2_delta is not None and abs(ov2_delta) <= 5 and (v1_delta is None or abs(v1_delta) > 5):
        return "OV2_CLOSER_TO_TRUTH"
    elif v1_delta is not None and abs(v1_delta) <= 5 and (ov2_delta is None or abs(ov2_delta) > 5):
        return "V1_CLOSER_TO_TRUTH"
    elif ov2_delta is not None and v1_delta is not None and abs(ov2_delta) <= 5 and abs(v1_delta) <= 5:
        return "BOTH_MATCH"
    else:
        return "NEITHER_MATCH"


# ── Main ────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description="Park Lima External Truth Reconciliation")
    ap.add_argument("--park-id", default=PARK_ID)
    ap.add_argument("--park-name", default=PARK_NAME)
    ap.add_argument(
        "--start-date",
        default="2026-06-04",
        help="Date to reconcile in YYYY-MM-DD format",
    )
    ap.add_argument(
        "--end-date",
        default=None,
        help="End date (exclusive). Defaults to start-date + 1 day.",
    )
    ap.add_argument(
        "--start-time",
        default="00:00:00",
        help="Start time in HH:MM:SS (local timezone)",
    )
    ap.add_argument(
        "--end-time",
        default="23:59:59",
        help="End time in HH:MM:SS (local timezone)",
    )
    ap.add_argument("--timezone", default=DEFAULT_TZ, help="Timezone for range")
    ap.add_argument(
        "--external-trips",
        type=int,
        default=None,
        help="Completed trips from Fleet Room/API (external truth)",
    )
    ap.add_argument(
        "--output-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports", "audits", "park_lima_external_truth",
        ),
    )
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    start_date = args.start_date
    end_date = args.end_date or (
        datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=1)
    ).strftime("%Y-%m-%d")
    start_dt = f"{start_date} {args.start_time}-05"
    end_dt = f"{end_date} 00:00:00-05"

    print("=" * 72)
    print("  PARK LIMA EXTERNAL TRUTH RECONCILIATION TEST")
    print("=" * 72)
    print(f"  Park:         {args.park_name} ({args.park_id})")
    print(f"  Range:        {start_dt} -> {end_dt}")
    print(f"  Timezone:     {args.timezone}")
    print(f"  External:     {args.external_trips or 'NOT PROVIDED'}")
    print()

    # ── A) OV2 Raw ──
    ov2 = ov2_raw_count(args.park_id, start_dt, end_dt)
    print(f"  [OV2 RAW] raw_yango.orders_raw")
    print(f"    Total:      {ov2['total']:>8,}")
    print(f"    Completed:  {ov2['completed']:>8,}")
    print(f"    Cancelled:  {ov2['cancelled']:>8,}")
    print(f"    Other:      {ov2['other']:>8,}")
    print(f"    Time col:   {ov2['time_col_used']}")
    if ov2.get("first_trip"):
        print(f"    First:      {ov2['first_trip'][:19]}")
        print(f"    Last:       {ov2['last_trip'][:19]}")

    # ── B) OV2 MV ──
    ov2_mv = ov2_mv_count(args.park_id, start_date)
    print(f"\n  [OV2 MV]   raw_yango.mv_orders_day")
    print(f"    Completed:  {ov2_mv:>8,}")
    print(f"    Note:       MV aggregates by operational_date (may differ from order_created_at)")

    # ── C) V1 Raw ──
    v1 = v1_raw_count(args.park_id, start_dt, end_dt)
    print(f"\n  [V1 RAW]  public.trips_all (exact park_id)")
    if v1.get("available"):
        print(f"    Completed:  {v1['completed']:>8,}")
        print(f"    Total:      {v1['total']:>8,}")
        print(f"    Cancelled:  {v1['cancelled']:>8,}")
    else:
        print(f"    Status:     UNAVAILABLE")
        print(f"    Note:       {v1.get('note', 'No data for this date range')}")

    # ── D) V1 CT Facts ──
    v1ct = v1_ct_count(start_date)
    print(f"\n  [V1 CT]   ops.real_business_slice_day_fact (Lima aggregate)")
    if v1ct.get("available"):
        print(f"    Trips:      {v1ct['trips']:>8,}")
        print(f"    Revenue:    {v1ct['revenue']:>12,.2f}")
        print(f"    Slices:     {v1ct['slices']}")
    else:
        print(f"    Status:     UNAVAILABLE")
        print(f"    Note:       {v1ct.get('note', 'No data')}")

    # ── E) External ──
    print(f"\n  [EXTERNAL] Fleet Room / API (user-provided)")
    if args.external_trips is not None:
        print(f"    Trips:      {args.external_trips:>8,}")
    else:
        print(f"    Status:     NOT PROVIDED")
        print(f"    (run with --external-trips <number> to compare)")

    # ── Summary Table ──
    ov2_completed = ov2["completed"]
    v1_completed = v1.get("completed", 0)

    external = args.external_trips
    print(f"\n{'-' * 72}")
    print(f"  RECONCILIATION SUMMARY")
    print(f"{'-' * 72}")
    print(f"  {'Source':<22} {'Trips':>8} {'Delta %':>10} {'Status':>12}")
    print(f"  {'-' * 22} {'-' * 8} {'-' * 10} {'-' * 12}")

    def _row(label, count):
        d = _delta_pct(count, external) if external else None
        ds = f"{d:+.2f}%" if d is not None else "N/A"
        st = _classify_delta(count, external) if external else "NOT_COMPUTED"
        print(f"  {label:<22} {count:>8,} {ds:>10} {st:>12}")

    _row("External (Fleet/API)", external if external else 0)
    if external is None:
        print(f"  {'(provide with --external-trips)':>54}")
    _row("OV2 Raw (orders_raw)", ov2_completed)
    _row("OV2 MV  (mv_orders_day)", ov2_mv)
    if v1.get("available"):
        _row("V1 Raw (trips_all)", v1_completed)
    else:
        print(f"  {'V1 Raw (trips_all)':<22} {'--':>8} {'UNAVAILABLE':>10} {'DATA_GAP':>12}")
    if v1ct.get("available"):
        _row("V1 CT  (day_fact)", v1ct["trips"])
    else:
        print(f"  {'V1 CT  (day_fact)':<22} {'--':>8} {'UNAVAILABLE':>10} {'DATA_GAP':>12}")

    print(f"\n  Verdict: {_classify_status({'external_trips': external, 'ov2_completed': ov2_completed, 'v1_completed': v1_completed})}")

    # ── Status Definitions ──
    print(f"\n{'-' * 72}")
    print(f"  STATUS COMPLETED DEFINITIONS")
    print(f"{'-' * 72}")
    print(f"  OV2:  order_status = 'complete'  (raw_yango.orders_raw)")
    print(f"  V1:   condicion = 'Completado'    (public.trips_all)")
    print(f"  Fleet/API: user-provided (--external-trips)")
    print(f"  Timezone: {args.timezone} (UTC-5)")
    print(f"  V1 raw date range: only has data until 2026-01-25")

    # ── Export CSV ──
    csv_path = os.path.join(args.output_dir, "park_lima_external_truth.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "generated_at", "park_id", "park_name", "start_dt", "end_dt", "timezone",
            "external_trips", "external_provided",
            "ov2_raw_total", "ov2_raw_completed", "ov2_raw_cancelled",
            "ov2_mv_completed",
            "v1_raw_total", "v1_raw_completed", "v1_raw_available",
            "v1_ct_trips", "v1_ct_available",
            "ov2_vs_external_delta_pct", "v1_vs_external_delta_pct",
            "verdict",
        ])
        w.writerow([
            datetime.now(PET).isoformat(),
            args.park_id, args.park_name, start_dt, end_dt, args.timezone,
            external if external is not None else "",
            "yes" if external is not None else "no",
            ov2["total"], ov2_completed, ov2["cancelled"],
            ov2_mv,
            v1.get("total", 0), v1_completed, "yes" if v1.get("available") else "no",
            v1ct.get("trips", 0), "yes" if v1ct.get("available") else "no",
            _delta_pct(ov2_completed, external) if external else "",
            _delta_pct(v1_completed, external) if external else "",
            _classify_status({
                "external_trips": external, "ov2_completed": ov2_completed, "v1_completed": v1_completed
            }),
        ])
    print(f"\n[export] CSV: {csv_path}")

    # ── Export JSON ──
    json_path = os.path.join(args.output_dir, "park_lima_external_truth.json")
    report = {
        "generated_at": datetime.now(PET).isoformat(),
        "park": {"id": args.park_id, "name": args.park_name},
        "range": {"start": start_dt, "end": end_dt, "timezone": args.timezone},
        "external": {"trips": external, "provided": external is not None},
        "ov2_raw": ov2,
        "ov2_mv": {"completed": ov2_mv},
        "v1_raw": v1,
        "v1_ct": v1ct,
        "deltas": {
            "ov2_vs_external_pct": _delta_pct(ov2_completed, external) if external else None,
            "v1_vs_external_pct": _delta_pct(v1_completed, external) if external else None,
        },
        "verdict": _classify_status({
            "external_trips": external, "ov2_completed": ov2_completed, "v1_completed": v1_completed,
        }),
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[export] JSON: {json_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
