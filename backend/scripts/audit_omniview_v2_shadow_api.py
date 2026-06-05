#!/usr/bin/env python3
"""
Audit Omniview V2 Shadow API — call endpoints and validate responses.

Usage:
  cd backend
  python -m scripts.audit_omniview_v2_shadow_api
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PET = timezone(timedelta(hours=-5))


def _call_service(endpoint: str, params: dict = None) -> Dict[str, Any]:
    """Call service directly (no HTTP needed for shadow audit)."""
    params = params or {}
    if endpoint == "daily":
        from app.services.omniview_v2_shadow_service import build_shadow_response
        return build_shadow_response(**params)
    elif endpoint == "health":
        from app.services.omniview_v2_shadow_service import build_shadow_response
        return build_shadow_response(**params)
    elif endpoint == "coverage":
        from app.repositories.omniview_v2_shadow_repository import get_coverage_by_day, get_source_health
        return {
            "source": "YANGO_API_SHADOW",
            "status": "SHADOW_ONLY",
            "health": get_source_health(params.get("park_id", "08e20910d81d42658d4334d3f6d10ac0")),
            "daily": get_coverage_by_day(**params),
        }
    elif endpoint == "reconciliation":
        from app.repositories.omniview_v2_shadow_repository import get_reconciliation_vs_ct
        return {
            "source": "YANGO_API_SHADOW",
            "status": "SHADOW_ONLY",
            "canonical_ready": False,
            "reconciliation": get_reconciliation_vs_ct(**params),
        }
    return {"error": "unknown_endpoint"}


def main() -> int:
    yesterday = (datetime.now(PET) - timedelta(days=1)).strftime("%Y-%m-%d")

    ap = argparse.ArgumentParser(description="Audit Omniview V2 Shadow API")
    ap.add_argument("--park-id", default="08e20910d81d42658d4334d3f6d10ac0")
    ap.add_argument("--date-from", default=yesterday)
    ap.add_argument("--date-to", default=yesterday)
    ap.add_argument(
        "--output-dir",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "exports", "audits", "omniview_v2_shadow",
        ),
    )
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    params = {"park_id": args.park_id, "date_from": args.date_from, "date_to": args.date_to}

    results = {}
    t0 = time.perf_counter()

    for ep in ["daily", "coverage", "reconciliation", "health"]:
        t1 = time.perf_counter()
        try:
            r = _call_service(ep, params if ep != "health" else {"park_id": args.park_id})
            results[ep] = {"ok": True, "elapsed_ms": round((time.perf_counter() - t1) * 1000, 1), "data": r}
            print(f"  {ep}: OK ({results[ep]['elapsed_ms']}ms)")
        except Exception as e:
            results[ep] = {"ok": False, "elapsed_ms": round((time.perf_counter() - t1) * 1000, 1), "error": str(e)[:200]}
            print(f"  {ep}: FAIL - {e}")

    total_elapsed = round(time.perf_counter() - t0, 2)

    # MD summary
    md = [
        "# Omniview V2 Shadow API Audit",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        f"**Date Range:** {args.date_from} -> {args.date_to}",
        f"**Total elapsed:** {total_elapsed}s",
        "",
        "## Endpoints",
        "",
        "| Endpoint | Status | Elapsed (ms) |",
        "|----------|--------|-------------|",
    ]
    for ep in ["daily", "coverage", "reconciliation", "health"]:
        r = results.get(ep, {})
        status = "OK" if r.get("ok") else "FAIL"
        md.append(f"| {ep} | {status} | {r.get('elapsed_ms', 'N/A')} |")

    daily = results.get("daily", {}).get("data", {})
    if daily.get("warnings"):
        md.extend(["", "## Warnings"])
        for w in daily["warnings"]:
            md.append(f"- **{w['code']}** [{w['severity']}]: {w['message']}")

    rec = results.get("reconciliation", {}).get("data", {}).get("reconciliation", {})
    if rec:
        md.extend([
            "", "## Reconciliation",
            f"- MV trips: {rec.get('mv_trips', 0):,}",
            f"- CT trips: {rec.get('ct_trips', 0):,}",
            f"- MV revenue: {rec.get('mv_revenue_partner_fee', 0):,.2f}",
            f"- CT revenue: {rec.get('ct_revenue_yego_final', 0):,.2f}",
            f"- Revenue delta: {rec.get('revenue_delta_pct', 'N/A')}%",
            f"- MV rev/order: {rec.get('mv_revenue_per_order', 0):.4f}",
            f"- CT rev/trip: {rec.get('ct_revenue_per_trip', 0):.4f}",
        ])

    summary_path = os.path.join(args.output_dir, "shadow_api_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\n[audit] Summary: {summary_path}")

    met_path = os.path.join(args.output_dir, "shadow_api_metrics.json")
    with open(met_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(PET).isoformat(),
            "total_elapsed_s": total_elapsed,
            "results": {k: {"ok": v["ok"], "elapsed_ms": v["elapsed_ms"]} for k, v in results.items()},
        }, f, indent=2)
    print(f"[audit] Metrics: {met_path}")

    # CSV
    if rec:
        csv_path = os.path.join(args.output_dir, "shadow_reconciliation.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "mv_value", "ct_value", "delta_pct"])
            w.writerow(["trips", rec.get("mv_trips", 0), rec.get("ct_trips", 0), rec.get("trips_delta_pct")])
            w.writerow(["revenue", rec.get("mv_revenue_partner_fee", 0), rec.get("ct_revenue_yego_final", 0), rec.get("revenue_delta_pct")])
        print(f"[audit] CSV: {csv_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
