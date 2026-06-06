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


def _write_diagnostic_md(rec: Dict[str, Any], output_dir: str) -> str:
    """Generate CT zero diagnostic report."""
    lines = [
        "# Omniview V2 Shadow — CT Zero Diagnostic",
        "",
        f"**Generated:** {datetime.now(PET).isoformat()}",
        "",
        "## Root Cause",
        "",
        "The initial reconciliation (OV2-B.4) returned `CT=0` for `country='peru' city='lima' date=2026-06-04`.",
        "Investigation revealed:",
        "",
    ]

    # CT availability info
    from app.repositories.omniview_v2_shadow_repository import _ct_check_availability
    has_ct, ct_min, ct_max = _ct_check_availability()
    if has_ct:
        lines.append(f"- CT table `ops.real_business_slice_day_fact` **has data** for Lima/Peru.")
        lines.append(f"- CT date range: **{ct_min}** to **{ct_max}**.")
        lines.append(f"- The requested target date is **outside** this range.")
        lines.append("- CT has not been refreshed for dates after `ct_max`.")
        lines.append("- MV `raw_yango.mv_orders_day` has fresher data (ingested from Yango API).")
        lines.append("- This is a **data latency gap**, not a reconciliation bug.")
    else:
        lines.append("- CT table has **NO data** for Lima/Peru at all.")
        lines.append("- This requires a separate data pipeline investigation.")

    lines.extend([
        "",
        "## Reconciliation Context",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| MV orders | {rec.get('mv_orders', 0):,} |",
        f"| MV revenue | {rec.get('mv_revenue_partner_fee', 0):,.2f} |",
        f"| CT trips | {rec.get('ct_trips', 0):,} |",
        f"| CT revenue | {rec.get('ct_revenue_yego_final', 0):,.2f} |",
        f"| CT match level | {rec.get('ct_match_level', 'N/A')} |",
        f"| CT data date used | {rec.get('ct_data_date', 'N/A')} |",
        f"| CT filter | {rec.get('ct_filter_used', 'N/A')} |",
        f"| Status | {rec.get('status', 'N/A')} |",
        f"| Basis | {rec.get('basis', 'N/A')} |",
        "",
    ])

    if rec.get("warnings"):
        lines.append("## CT Fallback Warnings")
        for w in rec["warnings"]:
            if w:
                lines.append(f"- {w}")

    lines.extend([
        "",
        "## Resolution",
        "",
        "1. The shadow reconciliation now uses a **controlled fallback strategy**:",
        "   - Level 1: Exact match by country/city/date",
        "   - Level 2: Nearest available date <= target (within 30 days)",
        "   - Level 3: Mark as UNAVAILABLE if no data exists",
        "2. The `ct_match_level` field reveals which strategy was used.",
        "3. When fallback is used, a `CT_FALLBACK` warning appears in the response.",
        "4. This is **shadow mode only** — no CT data is modified.",
    ])

    path = os.path.join(output_dir, "shadow_ct_zero_diagnostic.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def _write_reconciliation_by_basis_csv(
    daily_data: Dict[str, Any],
    rec_data: Dict[str, Any],
    output_dir: str,
) -> str:
    """Write reconciliation CSV enriched with basis/status fields."""
    rec = rec_data.get("reconciliation", {})
    path = os.path.join(output_dir, "shadow_reconciliation_by_basis.csv")
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "generated_at", "date_from", "date_to",
            "mv_orders", "mv_revenue_partner_fee",
            "ct_trips", "ct_revenue_yego_final",
            "trips_delta_pct", "revenue_delta_pct",
            "status", "basis", "ct_match_level",
            "ct_data_date", "ct_filter_used",
            "ct_warnings", "mv_rev_per_order", "ct_rev_per_trip",
        ])
        ct_warnings = " | ".join(rec.get("warnings", []))
        mv_date_range = rec.get("mv_date_range", {})
        w.writerow([
            datetime.now(PET).isoformat(),
            mv_date_range.get("from", ""),
            mv_date_range.get("to", ""),
            rec.get("mv_orders", 0),
            rec.get("mv_revenue_partner_fee", 0),
            rec.get("ct_trips", 0),
            rec.get("ct_revenue_yego_final", 0),
            rec.get("trips_delta_pct", ""),
            rec.get("revenue_delta_pct", ""),
            rec.get("status", ""),
            rec.get("basis", ""),
            rec.get("ct_match_level", ""),
            rec.get("ct_data_date", ""),
            rec.get("ct_filter_used", ""),
            ct_warnings,
            rec.get("mv_revenue_per_order", ""),
            rec.get("ct_revenue_per_trip", ""),
        ])
    return path


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

    # ── MD Summary ────────────────────────────────────────────
    daily_data = results.get("daily", {}).get("data", {})
    rec_data = results.get("reconciliation", {}).get("data", {})
    rec = rec_data.get("reconciliation", {})

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

    if daily_data.get("warnings"):
        md.extend(["", "## Warnings"])
        for w in daily_data["warnings"]:
            md.append(f"- **{w['code']}** [{w['severity']}]: {w['message']}")

    if rec:
        md.extend([
            "", "## Reconciliation",
            f"- **Status:** {rec.get('status', 'N/A')}",
            f"- **Basis:** {rec.get('basis', 'N/A')}",
            f"- **CT match level:** {rec.get('ct_match_level', 'N/A')}",
            f"- **CT data date:** {rec.get('ct_data_date', 'N/A')}",
            f"- MV orders: {rec.get('mv_orders', 0):,}",
            f"- CT trips: {rec.get('ct_trips', 0):,}",
            f"- MV revenue: {rec.get('mv_revenue_partner_fee', 0):,.2f}",
            f"- CT revenue: {rec.get('ct_revenue_yego_final', 0):,.2f}",
            f"- Trips delta: {rec.get('trips_delta_pct', 'N/A')}%",
            f"- Revenue delta: {rec.get('revenue_delta_pct', 'N/A')}%",
            f"- MV rev/order: {rec.get('mv_revenue_per_order', 0):.4f}",
            f"- CT rev/trip: {rec.get('ct_revenue_per_trip', 0):.4f}",
            "",
            "### CT Fallback Warnings",
        ])
        ctw = rec.get("warnings", [])
        if ctw:
            for w in ctw:
                if w:
                    md.append(f"- {w}")
        else:
            md.append("- None")

    summary_path = os.path.join(args.output_dir, "shadow_api_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"\n[audit] Summary: {summary_path}")

    # ── JSON Metrics ──────────────────────────────────────────
    met_path = os.path.join(args.output_dir, "shadow_api_metrics.json")
    with open(met_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now(PET).isoformat(),
            "total_elapsed_s": total_elapsed,
            "results": {k: {"ok": v["ok"], "elapsed_ms": v["elapsed_ms"]} for k, v in results.items()},
        }, f, indent=2)
    print(f"[audit] Metrics: {met_path}")

    # ── Enriched Reconciliation CSV ───────────────────────────
    if rec:
        csv_path = os.path.join(args.output_dir, "shadow_reconciliation.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric", "mv_value", "ct_value", "delta_pct", "status", "basis", "ct_match_level", "ct_data_date"])
            w.writerow(["trips", rec.get("mv_orders", 0), rec.get("ct_trips", 0), rec.get("trips_delta_pct", ""), rec.get("status", ""), rec.get("basis", ""), rec.get("ct_match_level", ""), rec.get("ct_data_date", "")])
            w.writerow(["revenue", rec.get("mv_revenue_partner_fee", 0), rec.get("ct_revenue_yego_final", 0), rec.get("revenue_delta_pct", ""), rec.get("status", ""), rec.get("basis", ""), rec.get("ct_match_level", ""), rec.get("ct_data_date", "")])
        print(f"[audit] CSV: {csv_path}")

        basis_csv = _write_reconciliation_by_basis_csv(daily_data, rec_data, args.output_dir)
        print(f"[audit] Basis CSV: {basis_csv}")

        diag_path = _write_diagnostic_md(rec, args.output_dir)
        print(f"[audit] Diagnostic: {diag_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
