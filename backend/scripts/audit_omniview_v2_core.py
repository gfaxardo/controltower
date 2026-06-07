#!/usr/bin/env python3
"""
OV2-C.0 — Omniview V2 Core Smoke Tests

Tests all OV2 core endpoints:
- /sources
- /summary (CT_TRIPS_2026 day)
- /summary (YANGO_API_RAW day)
- /health
- /compare (CT vs Yango)

Outputs:
  backend/exports/audits/omniview_v2_core/summary.md
  backend/exports/audits/omniview_v2_core/compare.csv
"""
from __future__ import annotations

import csv
import json
import os
import sys
from datetime import date as dt_date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "omniview_v2_core",
)

CT_SOURCE = "CT_TRIPS_2026"
YANGO_SOURCE = "YANGO_API_RAW"


def _json_dump(obj, indent=2):
    return json.dumps(obj, indent=indent, default=str, ensure_ascii=False)


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}
    all_passed = True

    # ── Test 1: /sources ──────────────────────────────────────
    print("[TEST 1] /sources")
    try:
        from app.services.omniview_v2_source_registry import get_supported_sources
        sources = get_supported_sources()
        assert len(sources) == 2, f"Expected 2 sources, got {len(sources)}"
        assert sources[0]["source_system"] == "CT_TRIPS_2026"
        assert sources[1]["source_system"] == "YANGO_API_RAW"
        assert sources[1]["canonical_ready"] == False
        results["sources"] = {"ok": True, "count": len(sources)}
        print(f"  PASS: {len(sources)} sources registered")
    except Exception as e:
        results["sources"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Test 2: /summary CT_TRIPS_2026 day ────────────────────
    print("[TEST 2] /summary source=CT_TRIPS_2026 grain=day")
    try:
        from app.services.omniview_v2_core_service import get_omniview_v2_summary
        resp_ct = get_omniview_v2_summary(
            source_system=CT_SOURCE,
            grain="day",
            date_from="2026-06-04",
            date_to="2026-06-04",
            filters={"country": "peru", "city": "lima"},
        )
        d = resp_ct.to_dict()
        assert d["source_system"] == CT_SOURCE
        assert d["canonical_ready"] == True
        assert d["grain"] == "day"
        assert len(d["kpis"]) > 0
        orders_kpi = next((k for k in d["kpis"] if k["metric_id"] == "orders"), None)
        assert orders_kpi is not None, "orders KPI missing"
        assert orders_kpi.get("value", 0) > 0, f"orders value is 0: {orders_kpi}"
        print(f"  PASS: orders={orders_kpi['value']:,}, revenue_kpi_present={any(k['metric_id']=='revenue' for k in d['kpis'])}")
        results["ct_summary"] = {"ok": True, "orders": orders_kpi["value"]}
    except Exception as e:
        results["ct_summary"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Test 3: /summary YANGO_API_RAW day ─────────────────────
    print("[TEST 3] /summary source=YANGO_API_RAW grain=day")
    try:
        from app.services.omniview_v2_core_service import get_omniview_v2_summary
        resp_yg = get_omniview_v2_summary(
            source_system=YANGO_SOURCE,
            grain="day",
            date_from="2026-06-04",
            date_to="2026-06-04",
            filters={"park_id": "08e20910d81d42658d4334d3f6d10ac0"},
        )
        d = resp_yg.to_dict()
        assert d["source_system"] == YANGO_SOURCE
        assert d["canonical_ready"] == False
        assert d["grain"] == "day"
        assert len(d["warnings"]) > 0  # Should have PARTIAL_PARK_COVERAGE etc
        orders_kpi = next((k for k in d["kpis"] if k["metric_id"] == "orders"), None)
        assert orders_kpi is not None
        assert orders_kpi.get("value", 0) > 0
        print(f"  PASS: orders={orders_kpi['value']:,}, canonical_ready=false, warnings={len(d['warnings'])}")
        results["yango_summary"] = {"ok": True, "orders": orders_kpi["value"]}
    except Exception as e:
        results["yango_summary"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Test 4: /health ──────────────────────────────────────
    print("[TEST 4] /health")
    try:
        from app.services.omniview_v2_core_service import get_omniview_v2_health
        health = get_omniview_v2_health()
        assert "sources" in health
        assert CT_SOURCE in health["sources"]
        assert YANGO_SOURCE in health["sources"]
        assert health["sources"][YANGO_SOURCE]["canonical_ready"] == False
        print(f"  PASS: ct_cov={health['sources'][CT_SOURCE].get('coverage_pct')}%, yg_cov={health['sources'][YANGO_SOURCE].get('coverage_pct')}%")
        results["health"] = {"ok": True}
    except Exception as e:
        results["health"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Test 5: /compare ─────────────────────────────────────
    print("[TEST 5] /compare CT_TRIPS_2026 vs YANGO_API_RAW")
    try:
        from app.services.omniview_v2_core_service import get_source_comparison
        cmp = get_source_comparison(
            source_a=CT_SOURCE,
            source_b=YANGO_SOURCE,
            grain="day",
            date_from="2026-06-04",
            date_to="2026-06-04",
        )
        d = cmp.to_dict()
        assert "source_a" in d
        assert "source_b" in d
        assert d["source_a"]["canonical_ready"] == True
        assert d["source_b"]["canonical_ready"] == False
        print(f"  PASS: source_a={d['source_a']['source_system']}, source_b={d['source_b']['source_system']}")
        results["compare"] = {"ok": True}

        # Write compare CSV
        csv_path = os.path.join(OUTPUT_DIR, "compare.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["metric_id", "source_a_value", "source_b_value", "unit"])
            for kpi_a in d["source_a"]["kpis"]:
                mid = kpi_a["metric_id"]
                kpi_b = next((k for k in d["source_b"]["kpis"] if k["metric_id"] == mid), {})
                w.writerow([mid, kpi_a.get("value"), kpi_b.get("value"), kpi_a.get("unit", "")])
        print(f"  CSV: {csv_path}")
    except Exception as e:
        results["compare"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Write Summary ────────────────────────────────────────
    md_lines = [
        "# OV2-C.0 — Omniview V2 Core Smoke Test Report",
        "",
        f"**Date:** {dt_date.today().isoformat()}",
        f"**Status:** {'PASS' if all_passed else 'FAIL'}",
        "",
        "| Test | Result | Detail |",
        "|------|--------|--------|",
    ]
    for name, r in results.items():
        status = "PASS" if r.get("ok") else "FAIL"
        detail = r.get("error") or r.get("orders", r.get("count", ""))
        md_lines.append(f"| {name} | {status} | {detail} |")

    summary_path = os.path.join(OUTPUT_DIR, "summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))
    print(f"\n[smoke] Report: {summary_path}")
    print(f"[smoke] Overall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
