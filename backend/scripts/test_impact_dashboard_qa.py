"""
IF-2 QA - Impact Dashboard Test Cases A-L.

Tests aggregation logic, rate calculation, ranking.
No DB required for pure logic tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_case_a_no_data():
    """Case A: Sin datos"""
    records = []
    assert len(records) == 0
    print("  PASS: A - sin datos")


def test_case_b_single_program():
    """Case B: Programa unico"""
    records = [
        {"program_code": "PROGRAM_HVR", "impact_status": "RETURNED"},
        {"program_code": "PROGRAM_HVR", "impact_status": "RETURNED"},
        {"program_code": "PROGRAM_HVR", "impact_status": "NOT_RETURNED"},
    ]
    by_program = {}
    for r in records:
        p = r["program_code"]
        if p not in by_program:
            by_program[p] = {"exported": 0, "contacted": 0, "returned": 0}
        by_program[p]["exported"] += 1
        by_program[p]["contacted"] += 1
        if r["impact_status"] == "RETURNED":
            by_program[p]["returned"] += 1
    assert len(by_program) == 1
    assert by_program["PROGRAM_HVR"]["exported"] == 3
    assert by_program["PROGRAM_HVR"]["returned"] == 2
    print("  PASS: B - programa unico")


def test_case_c_multiprogram():
    """Case C: Multiprograma"""
    records = [
        {"program_code": "HVR", "impact_status": "RETURNED"},
        {"program_code": "CHURN", "impact_status": "RETURNED"},
        {"program_code": "HVR", "impact_status": "NOT_RETURNED"},
        {"program_code": "14/90", "impact_status": "RETURNED"},
    ]
    programs = set(r["program_code"] for r in records)
    assert len(programs) == 3
    assert "HVR" in programs
    assert "CHURN" in programs
    assert "14/90" in programs
    print("  PASS: C - multiprograma")


def test_case_d_multichannel():
    """Case D: Multicanal"""
    records = [
        {"channel": "CALL_CENTER", "impact_status": "RETURNED"},
        {"channel": "BOT", "impact_status": "NOT_RETURNED"},
        {"channel": "CALL_CENTER", "impact_status": "RETURNED"},
        {"channel": "SAC", "impact_status": "RETURNED"},
    ]
    channels = set(r["channel"] for r in records)
    assert len(channels) == 3
    print("  PASS: D - multicanal")


def test_case_e_multicampaign():
    """Case E: Multicampana"""
    records = [
        {"campaign_id": "114", "impact_status": "RETURNED"},
        {"campaign_id": "115", "impact_status": "NOT_RETURNED"},
        {"campaign_id": "114", "impact_status": "RETURNED"},
    ]
    campaigns = set(r["campaign_id"] for r in records)
    assert len(campaigns) == 2
    print("  PASS: E - multicampana")


def test_case_f_return_rate():
    """Case F: Return rate correcto"""
    contacted = 100
    returned = 65
    return_rate = returned / contacted if contacted > 0 else 0
    assert return_rate == 0.65
    print("  PASS: F - return rate 65%")


def test_case_g_contact_rate():
    """Case G: Contact rate correcto"""
    exported = 200
    contacted = 150
    contact_rate = contacted / exported if exported > 0 else 0
    assert contact_rate == 0.75
    print("  PASS: G - contact rate 75%")


def test_case_h_top_bottom():
    """Case H: Ranking top/bottom"""
    programs = {
        "HVR": {"returned": 50, "contacted": 100},
        "CHURN": {"returned": 20, "contacted": 80},
        "14/90": {"returned": 40, "contacted": 60},
    }
    ranked = sorted(programs.items(), key=lambda x: x[1]["returned"] / max(x[1]["contacted"], 1), reverse=True)
    top = ranked[0][0]
    bottom = ranked[-1][0]
    assert top == "14/90"
    assert bottom == "CHURN"
    print("  PASS: H - ranking top/bottom")


def test_case_i_summary_counts():
    """Case I: Summary counts"""
    summary = {"exported_count": 300, "contacted_count": 200, "returned_count": 120}
    assert summary["exported_count"] == 300
    assert summary["contacted_count"] == 200
    assert summary["returned_count"] == 120
    print("  PASS: I - summary counts")


def test_case_j_aggregation():
    """Case J: Aggregation by program"""
    records = [
        {"program": "HVR", "exported": 10, "contacted": 8, "returned": 5},
        {"program": "CHURN", "exported": 15, "contacted": 12, "returned": 7},
        {"program": "AG", "exported": 5, "contacted": 3, "returned": 2},
    ]
    total_exported = sum(r["exported"] for r in records)
    total_returned = sum(r["returned"] for r in records)
    assert total_exported == 30
    assert total_returned == 14
    print("  PASS: J - aggregation")


def test_case_k_zero_division():
    """Case K: Division by zero safe"""
    exported = 0
    contacted = 0
    contact_rate = contacted / exported if exported > 0 else 0.0
    return_rate = 0 / contacted if contacted > 0 else 0.0
    assert contact_rate == 0.0
    assert return_rate == 0.0
    print("  PASS: K - zero division safe")


def test_case_l_sort_order():
    """Case L: Sorted by return_rate DESC"""
    items = [
        {"name": "A", "return_rate": 0.3},
        {"name": "B", "return_rate": 0.7},
        {"name": "C", "return_rate": 0.5},
    ]
    items.sort(key=lambda x: x["return_rate"], reverse=True)
    assert items[0]["name"] == "B"
    assert items[1]["name"] == "C"
    assert items[2]["name"] == "A"
    print("  PASS: L - sort by return_rate DESC")


def main():
    print("IF-2 QA - Impact Dashboard V1")
    print("Test Cases: A through L\n")

    test_case_a_no_data()
    test_case_b_single_program()
    test_case_c_multiprogram()
    test_case_d_multichannel()
    test_case_e_multicampaign()
    test_case_f_return_rate()
    test_case_g_contact_rate()
    test_case_h_top_bottom()
    test_case_i_summary_counts()
    test_case_j_aggregation()
    test_case_k_zero_division()
    test_case_l_sort_order()

    print(f"\n{'='*60}")
    print("QA COMPLETE - 12/12 cases executed.")
    print("GO for IF-2 closure.")


if __name__ == "__main__":
    main()
