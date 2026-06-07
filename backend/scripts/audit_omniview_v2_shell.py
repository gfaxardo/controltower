#!/usr/bin/env python3
"""
OV2-C.1 — Omniview V2 Shell Audit Script

Tests the product shell:
- Full shell for CT_TRIPS_2026
- Full shell for YANGO_API_RAW
- Sections list
- Each section by ID
- Warnings check
- canonical_ready flags

Outputs:
  backend/exports/audits/omniview_v2_shell/shell_summary.md
  backend/exports/audits/omniview_v2_shell/shell_sections.json
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date as dt_date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports", "audits", "omniview_v2_shell",
)

CT_SOURCE = "CT_TRIPS_2026"
YANGO_SOURCE = "YANGO_API_RAW"

SECTION_IDS = [
    "executive_state", "source_health", "kpi_strip",
    "plan_vs_real", "growth_movement", "operational_coverage",
    "revenue_integrity", "slice_readiness", "alerts_warnings", "lineage_audit",
]

ALLOWED_STATUSES = {"OK", "WARNING", "BLOCKED", "NOT_READY"}
ALLOWED_ACTIONS = {"VIEW_DETAIL", "VIEW_LINEAGE", "VIEW_COVERAGE", "VIEW_RECONCILIATION"}


def main() -> int:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    results = {}
    all_passed = True

    # ── Test 1: Shell CT_TRIPS_2026 ────────────────────────────
    print("[TEST 1] Shell CT_TRIPS_2026 day")
    try:
        from app.services.omniview_v2_shell_service import build_shell
        ct_shell = build_shell(
            source_system=CT_SOURCE,
            grain="day",
            date_from="2026-06-04",
            date_to="2026-06-04",
            filters={"country": "peru", "city": "lima"},
        )
        d = ct_shell.to_dict()
        assert d["source_system"] == CT_SOURCE
        assert d["canonical_ready"] == True
        assert len(d["sections"]) == 10
        executive = d["sections"][0]
        assert executive["section_id"] == "executive_state"

        statuses = {s["section_id"]: s["status"]["code"] for s in d["sections"]}
        ok_count = sum(1 for v in statuses.values() if v == "OK")
        warning_count = sum(1 for v in statuses.values() if v == "WARNING")
        print(f"  PASS: 10 sections, OK={ok_count}, WARNING={warning_count}, BLOCKED={sum(1 for v in statuses.values() if v=='BLOCKED')}")
        results["ct_shell"] = {"ok": True, "ok_sections": ok_count, "warning_sections": warning_count}
    except Exception as e:
        results["ct_shell"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Test 2: Shell YANGO_API_RAW ────────────────────────────
    print("[TEST 2] Shell YANGO_API_RAW day")
    try:
        yg_shell = build_shell(
            source_system=YANGO_SOURCE,
            grain="day",
            date_from="2026-06-04",
            date_to="2026-06-04",
            filters={"park_id": "08e20910d81d42658d4334d3f6d10ac0"},
        )
        d = yg_shell.to_dict()
        assert d["source_system"] == YANGO_SOURCE
        assert d["canonical_ready"] == False
        assert len(d["sections"]) == 10
        # Yango should have some WARNING or BLOCKED sections
        statuses = {s["section_id"]: s["status"]["code"] for s in d["sections"]}
        blocked = [k for k, v in statuses.items() if v == "BLOCKED"]
        assert len(blocked) > 0, "Expected Yango to have at least 1 BLOCKED section"
        print(f"  PASS: 10 sections, canonical_ready=false, blocked={blocked}")
        results["yango_shell"] = {"ok": True, "blocked_sections": blocked}
    except Exception as e:
        results["yango_shell"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Test 3: Sections list ─────────────────────────────────
    print("[TEST 3] /shell/sections list")
    try:
        from app.services.omniview_v2_shell_service import get_shell_sections_list
        sections_list = get_shell_sections_list()
        assert len(sections_list) == 10
        ids = [s["section_id"] for s in sections_list]
        assert ids == SECTION_IDS
        print(f"  PASS: {len(sections_list)} sections listed")
        results["sections_list"] = {"ok": True}
    except Exception as e:
        results["sections_list"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Test 4: Each section by ID ────────────────────────────
    print("[TEST 4] /shell/section/{id} for all sections")
    try:
        from app.services.omniview_v2_shell_service import get_shell_section
        section_results = {}
        for sid in SECTION_IDS:
            sec = get_shell_section(
                source_system=CT_SOURCE,
                grain="day",
                date_from="2026-06-04",
                date_to="2026-06-04",
                section_id=sid,
                filters={"country": "peru", "city": "lima"},
            )
            assert sec is not None, f"Section {sid} returned None"
            status_code = sec.status.code
            assert status_code in ALLOWED_STATUSES, f"Invalid status '{status_code}' for {sid}"
            # Check allowed actions
            for action in sec.allowed_actions:
                assert action.action_id in ALLOWED_ACTIONS, f"Disallowed action '{action.action_id}' in {sid}"
            section_results[sid] = {"status": status_code, "actions": [a.action_id for a in sec.allowed_actions]}
        print(f"  PASS: All {len(section_results)} sections, all actions valid")
        results["section_details"] = {"ok": True, "details": section_results}
    except Exception as e:
        results["section_details"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Test 5: Warnings have no ACTION_ENGINE actions ─────────
    print("[TEST 5] Warning and action validation")
    try:
        for sid, detail in section_results.items():
            for action_id in detail["actions"]:
                assert action_id in ALLOWED_ACTIONS, f"ACTION_ENGINE action found: {action_id}"
        print(f"  PASS: No ACTION_ENGINE/DECISION/EXECUTION actions found")
        results["action_validation"] = {"ok": True}
    except Exception as e:
        results["action_validation"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Test 6: canonical_ready flags ─────────────────────────
    print("[TEST 6] canonical_ready verification")
    try:
        ct_d = ct_shell.to_dict()
        yg_d = yg_shell.to_dict()
        assert ct_d["canonical_ready"] == True
        assert yg_d["canonical_ready"] == False
        print(f"  PASS: CT={ct_d['canonical_ready']}, Yango={yg_d['canonical_ready']}")
        results["canonical_flags"] = {"ok": True}
    except Exception as e:
        results["canonical_flags"] = {"ok": False, "error": str(e)}
        all_passed = False
        print(f"  FAIL: {e}")

    # ── Write outputs ─────────────────────────────────────────
    md_lines = [
        "# OV2-C.1 — Omniview V2 Shell Audit Report",
        "",
        f"**Date:** {dt_date.today().isoformat()}",
        f"**Overall:** {'PASS' if all_passed else 'FAIL'}",
        "",
        "| Test | Result | Detail |",
        "|------|--------|--------|",
    ]
    for name, r in results.items():
        status = "PASS" if r.get("ok") else "FAIL"
        detail = r.get("error") or str(r.get("ok_sections", r.get("blocked_sections", "")))
        md_lines.append(f"| {name} | {status} | {detail} |")

    summary_path = os.path.join(OUTPUT_DIR, "shell_summary.md")
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    # Write sections JSON
    sections_path = os.path.join(OUTPUT_DIR, "shell_sections.json")
    with open(sections_path, "w", encoding="utf-8") as f:
        json.dump(results.get("section_details", {}).get("details", {}), f, indent=2, default=str)

    print(f"\n[audit] Report:   {summary_path}")
    print(f"[audit] Sections: {sections_path}")
    print(f"[audit] Overall:  {'ALL PASSED' if all_passed else 'SOME FAILED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
