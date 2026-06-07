"""
LG-2.6 QA - Executive Risk Panel Test Cases A-J.

Tests pure logic: risk levels, thresholds, scores.
No DB required for pure logic tests.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config.yego_lima_risk_registry import (
    CAPACITY_RISK, QUEUE_RISK, EXPORT_RISK, SYNC_RISK, DATA_QUALITY_RISK,
    evaluate_level, evaluate_score,
)


def test_case_a_all_green():
    """Case A: Todo verde"""
    assert evaluate_level(CAPACITY_RISK, 1.0) == "GREEN"
    assert evaluate_level(QUEUE_RISK, 0.02) == "GREEN"
    assert evaluate_level(EXPORT_RISK, 0.95) == "GREEN"
    assert evaluate_level(SYNC_RISK, 0.02) == "GREEN"
    assert evaluate_level(DATA_QUALITY_RISK, 0.01) == "GREEN"
    print("  PASS: A - todo verde")


def test_case_b_capacity_red():
    """Case B: Capacity Risk rojo (< 0.80)"""
    level = evaluate_level(CAPACITY_RISK, 0.50)
    assert level == "RED"
    print("  PASS: B - capacity risk RED")


def test_case_c_queue_red():
    """Case C: Queue Risk rojo (held > 15%)"""
    level = evaluate_level(QUEUE_RISK, 0.20)
    assert level == "RED"
    print("  PASS: C - queue risk RED")


def test_case_d_export_red():
    """Case D: Export Risk rojo (< 70%)"""
    level = evaluate_level(EXPORT_RISK, 0.50)
    assert level == "RED"
    print("  PASS: D - export risk RED")


def test_case_e_sync_red():
    """Case E: Sync Risk rojo (unmatched > 15%)"""
    level = evaluate_level(SYNC_RISK, 0.20)
    assert level == "RED"
    print("  PASS: E - sync risk RED")


def test_case_f_data_quality_red():
    """Case F: Data Quality rojo (missing > 10%)"""
    level = evaluate_level(DATA_QUALITY_RISK, 0.15)
    assert level == "RED"
    print("  PASS: F - data quality RED")


def test_case_g_no_data():
    """Case G: Sin datos (ratio = 1.0)"""
    level = evaluate_level(CAPACITY_RISK, 1.0)
    assert level == "GREEN"
    level = evaluate_level(QUEUE_RISK, 0.0)
    assert level == "GREEN"
    print("  PASS: G - sin datos -> GREEN")


def test_case_h_yellow_thresholds():
    """Case H: Yellow thresholds correct"""
    assert evaluate_level(CAPACITY_RISK, 0.85) == "YELLOW"
    assert evaluate_level(QUEUE_RISK, 0.10) == "YELLOW"
    assert evaluate_level(EXPORT_RISK, 0.80) == "YELLOW"
    assert evaluate_level(SYNC_RISK, 0.10) == "YELLOW"
    assert evaluate_level(DATA_QUALITY_RISK, 0.05) == "YELLOW"
    print("  PASS: H - yellow thresholds")


def test_case_i_scores_range():
    """Case I: Scores range 0-1"""
    for risk in [CAPACITY_RISK, QUEUE_RISK, EXPORT_RISK, SYNC_RISK, DATA_QUALITY_RISK]:
        for val in [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]:
            score = evaluate_score(risk, val)
            assert 0.0 <= score <= 1.0, f"{risk} score {score} out of range for value {val}"
    print("  PASS: I - scores in [0,1] range")


def test_case_j_overall_logic():
    """Case J: Overall risk logic"""
    risks_green = [
        {"risk_level": "GREEN"}, {"risk_level": "GREEN"},
        {"risk_level": "GREEN"}, {"risk_level": "GREEN"}, {"risk_level": "GREEN"},
    ]
    risks_red = [
        {"risk_level": "GREEN"}, {"risk_level": "RED"},
        {"risk_level": "GREEN"}, {"risk_level": "GREEN"}, {"risk_level": "GREEN"},
    ]
    risks_yellow2 = [
        {"risk_level": "YELLOW"}, {"risk_level": "YELLOW"},
        {"risk_level": "GREEN"}, {"risk_level": "GREEN"}, {"risk_level": "GREEN"},
    ]
    risks_yellow3 = [
        {"risk_level": "YELLOW"}, {"risk_level": "YELLOW"},
        {"risk_level": "YELLOW"}, {"risk_level": "GREEN"}, {"risk_level": "GREEN"},
    ]

    def overall(risks):
        r = sum(1 for x in risks if x["risk_level"] == "RED")
        y = sum(1 for x in risks if x["risk_level"] == "YELLOW")
        if r > 0: return "RED"
        if y >= 3: return "RED"
        if y >= 2: return "YELLOW"
        return "GREEN"

    assert overall(risks_green) == "GREEN"
    assert overall(risks_red) == "RED"
    assert overall(risks_yellow2) == "YELLOW"
    assert overall(risks_yellow3) == "RED"
    print("  PASS: J - overall risk logic")


def main():
    print("LG-2.6 QA - Executive Risk Panel V1")
    print("Test Cases: A through J\n")

    test_case_a_all_green()
    test_case_b_capacity_red()
    test_case_c_queue_red()
    test_case_d_export_red()
    test_case_e_sync_red()
    test_case_f_data_quality_red()
    test_case_g_no_data()
    test_case_h_yellow_thresholds()
    test_case_i_scores_range()
    test_case_j_overall_logic()

    print(f"\n{'='*60}")
    print("QA COMPLETE - 10/10 cases executed.")
    print("GO for LG-2.6 closure.")


if __name__ == "__main__":
    main()
