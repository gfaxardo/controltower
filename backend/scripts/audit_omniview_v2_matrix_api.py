#!/usr/bin/env python3
"""
OV2-C.5 — Matrix API Audit Script

Tests /ops/omniview-v2/matrix endpoint via service call.
Validates MatrixResponse contract compliance.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date as dt_date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "omniview_v2_matrix",
)


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    from app.services.omniview_v2_matrix_view_model_service import build_matrix_response

    results = {}
    all_passed = True

    tests = [
        ("CT_TRIPS_2026_day", "CT_TRIPS_2026", "day", "2026-06-04", "2026-06-04"),
        ("YANGO_API_RAW_day", "YANGO_API_RAW", "day", "2026-06-04", "2026-06-04"),
        ("unsupported_grain", "YANGO_API_RAW", "week", "2026-06-04", "2026-06-04"),
    ]

    for name, source, grain, date_from, date_to in tests:
        print(f"[TEST] {name}")
        try:
            resp = build_matrix_response(
                source_system=source,
                grain=grain,
                date_from=date_from,
                date_to=date_to,
            )
            d = resp.to_dict()

            assert d["source_system"] == source, f"Expected {source}, got {d['source_system']}"
            assert d["grain"] == grain, f"Expected {grain}, got {d['grain']}"
            assert "columns" in d
            assert "rows" in d
            assert "cells" in d
            assert "warnings" in d
            assert "lineage" in d

            is_unsupported = any(w.get("code") == "GRAIN_NOT_SUPPORTED" for w in d["warnings"])
            is_no_data = any(w.get("code") == "NO_DATA" for w in d["warnings"])

            if name == "unsupported_grain":
                assert is_unsupported or is_no_data or (d["metadata"]["row_count"] == 0), "Expected unsupported/empty for Yango week"
                results[name] = {"ok": True, "status": "UNSUPPORTED_OK"}
                print(f"  PASS: unsupported grain correctly handled")
            else:
                assert d["metadata"]["row_count"] > 0, "No rows"
                assert d["metadata"]["column_count"] > 0, "No columns"
                assert d["metadata"]["cell_count"] > 0, "No cells"

                for cell in d["cells"]:
                    assert cell.get("row_id"), f"Cell missing row_id: {cell}"
                    assert cell.get("column_id"), f"Cell missing column_id: {cell}"
                    assert cell.get("source_system") == source, f"Cell has wrong source_system"
                    assert cell.get("source_table"), "Cell missing source_table"

                if source == "YANGO_API_RAW":
                    assert d["canonical_ready"] == False, "Yango must have canonical_ready=false"
                elif source == "CT_TRIPS_2026":
                    assert d["canonical_ready"] == True, "CT must have canonical_ready=true"

                results[name] = {
                    "ok": True,
                    "rows": d["metadata"]["row_count"],
                    "columns": d["metadata"]["column_count"],
                    "cells": d["metadata"]["cell_count"],
                }
                print(f"  PASS: {d['metadata']['row_count']} rows x {d['metadata']['column_count']} cols = {d['metadata']['cell_count']} cells")

        except Exception as e:
            results[name] = {"ok": False, "error": str(e)}
            all_passed = False
            print(f"  FAIL: {e}")

    # ── Save samples ────────────────────────────────────────
    for name, source, grain, df, dt in tests[:2]:
        resp = build_matrix_response(source_system=source, grain=grain, date_from=df, date_to=dt)
        sample = resp.to_dict()
        sample["cells"] = sample["cells"][:5]  # Trim for readability
        path = os.path.join(OUTPUT_DIR, f"matrix_api_sample_{name.replace('_day','')}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=2, default=str, ensure_ascii=False)

    # ── Write summary ───────────────────────────────────────
    md = [
        "# OV2-C.5 — Matrix API Audit Report",
        "",
        f"**Date:** {dt_date.today().isoformat()}",
        f"**Overall:** {'PASS' if all_passed else 'FAIL'}",
        "",
        "| Test | Result | Detail |",
        "|------|--------|--------|",
    ]
    for name, r in results.items():
        status = "PASS" if r.get("ok") else "FAIL"
        detail = r.get("error") or f"{r.get('rows',0)}r x {r.get('columns',0)}c"
        md.append(f"| {name} | {status} | {detail} |")

    summary_path = os.path.join(OUTPUT_DIR, "matrix_api_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n[audit] Summary: {summary_path}")
    print(f"[audit] Samples: {OUTPUT_DIR}")
    print(f"[audit] Overall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
