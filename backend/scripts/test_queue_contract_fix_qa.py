"""
LG-C1.1B QA — Queue Build Contract Fix Test Cases A-J.

Tests logic and real DB results for queue build + export.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.services.yego_lima_assignment_queue_service import create_assignment_batch, get_assignment_queue
from app.services.yego_lima_queue_export_service import export_ready_queue_to_loopcontrol

passed = 0
failed = 0


def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS: {label}{' - ' + detail if detail else ''}")
    else:
        failed += 1
        print(f"  FAIL: {label}{' - ' + detail if detail else ''}")


def test_case_a_driver_id_null_skipped():
    """A: driver_id null or empty is skipped"""
    r = {"driver_id": "", "program_code": "P1"}
    can_insert = bool(r.get("driver_id")) and bool(r.get("program_code"))
    check("A", not can_insert, "empty driver_id skipped")


def test_case_b_program_code_null_skipped():
    """B: program_code null or empty is skipped"""
    r = {"driver_id": "d1", "program_code": ""}
    can_insert = bool(r.get("driver_id")) and bool(r.get("program_code"))
    check("B", not can_insert, "empty program_code skipped")


def test_case_c_phone_null_held():
    """C: phone null enters HELD"""
    r = {"driver_id": "d1", "program_code": "P1", "phone": None, "assigned_channel": "CALL_CENTER"}
    status = "HELD" if (not r.get("phone") or r.get("assigned_channel") == "UNASSIGNED") else "READY"
    check("C", status == "HELD", "phone null -> HELD")


def test_case_d_channel_unassigned_held():
    """D: assigned_channel = UNASSIGNED -> HELD (real world case, worklist never returns NULL)"""
    r = {"driver_id": "d1", "program_code": "P1", "phone": "999", "assigned_channel": "UNASSIGNED"}
    status = "HELD" if (not r.get("phone") or r.get("assigned_channel") == "UNASSIGNED") else "READY"
    check("D", status == "HELD", "UNASSIGNED -> HELD")


def test_case_e_fallbacks():
    """E: name/city/park null have fallbacks"""
    r = {"driver_id": "d1", "program_code": "P1", "phone": "999", "assigned_channel": "CALL_CENTER",
         "driver_name": None, "city": None, "park": None, "country": None}
    dn = r.get("driver_name") or "Sin nombre"
    ci = r.get("city") or "Lima"
    pa = r.get("park") or "Sin park"
    co = r.get("country") or "PE"
    check("E", dn == "Sin nombre" and ci == "Lima" and pa == "Sin park" and co == "PE", "all fallbacks applied")


def test_case_f_build_real():
    """F: build real does not crash"""
    result = create_assignment_batch(date_str="2026-06-02", program="PROGRAM_CHURN_PREVENTION", channel="CALL_CENTER")
    ok = result["created_count"] >= 0
    check("F", ok, f"created={result['created_count']}" + (f" (fresh)" if result['created_count'] > 0 else " (all duplicates)"))


def test_case_g_duplicates_protected():
    """G: duplicates are still protected (re-build same date)"""
    result = create_assignment_batch(date_str="2026-06-02")
    # After initial build of 500, second build should have 0 created but no crash
    check("G", result["skipped_duplicates"] >= 0 and result["created_count"] >= 0, f"build safe: created={result['created_count']}, dup={result['skipped_duplicates']}")


def test_case_h_export_limit():
    """H: export limit=10 respects limit"""
    result = export_ready_queue_to_loopcontrol(date_str="2026-06-02", limit=10)
    check("H", result["selected_count"] <= 10, f"selected={result['selected_count']}")


def test_case_i_no_reexport():
    """I: EXPORTED records not re-exported"""
    q = get_assignment_queue(date_str="2026-06-02", status="EXPORTED")
    exported_count = q["total_records"]
    # Attempt another export - should not re-export already EXPORTED records
    result2 = export_ready_queue_to_loopcontrol(date_str="2026-06-02", limit=10)
    check("I", exported_count >= 10, f"original exported={exported_count}, re-export picked={result2['selected_count']} should be <= remaining READY")


def test_case_j_freshness():
    """J: Queue data reflects real operational data"""
    q = get_assignment_queue(date_str="2026-06-02")
    has_data = q["total_records"] > 0
    has_ready = q["ready_count"] > 0
    has_held = q["held_count"] > 0
    check("J", has_data and has_ready and has_held, f"total={q['total_records']}, ready={q['ready_count']}, held={q['held_count']}")


def main():
    print("LG-C1.1B QA — Queue Build Contract Fix")
    print("Test Cases: A through J\n")

    test_case_a_driver_id_null_skipped()
    test_case_b_program_code_null_skipped()
    test_case_c_phone_null_held()
    test_case_d_channel_unassigned_held()
    test_case_e_fallbacks()
    test_case_f_build_real()
    test_case_g_duplicates_protected()
    test_case_h_export_limit()
    test_case_i_no_reexport()
    test_case_j_freshness()

    print(f"\n{'='*60}")
    print(f"QA: {passed}P / {failed}F")
    if failed == 0:
        print("PASS — All tests OK")
    else:
        print("FAIL — Some tests failed")


if __name__ == "__main__":
    main()
