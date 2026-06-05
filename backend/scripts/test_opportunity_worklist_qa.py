"""
LG-2.5A QA — Opportunity Worklist Test Cases A-H.

Tests the pure logic: enrichment, channel assignment, sorting, filtering.
No DB required.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.yego_lima_opportunity_worklist_service import (
    _enrich_and_assign,
    _build_opportunity_reason,
    _assign_channel,
)


def test_case_a_empty():
    """Case A: Sin oportunidades"""
    result = _enrich_and_assign([], {})
    assert len(result) == 0, f"Expected 0, got {len(result)}"
    print("  PASS: A — sin oportunidades")


def test_case_b_single_program():
    """Case B: Con oportunidades de un programa"""
    drivers = [
        {"driver_profile_id": "d1", "selected_program_code": "PROGRAM_HIGH_VALUE_RECOVERY",
         "final_rank": 1, "completed_orders_week": 5, "lifecycle_state": "CHURNED",
         "performance_state": "LOW", "last_trip_at": "2026-05-20", "city": "Lima", "park_name": "Park A",
         "driver_name": "Juan Perez", "phone": "999000001"},
        {"driver_profile_id": "d2", "selected_program_code": "PROGRAM_HIGH_VALUE_RECOVERY",
         "final_rank": 2, "completed_orders_week": 3, "lifecycle_state": "CHURNED",
         "performance_state": "LOW", "last_trip_at": "2026-05-15", "city": "Lima", "park_name": "Park B",
         "driver_name": "Ana Lopez", "phone": "999000002"},
    ]
    channel_alloc = {
        "PROGRAM_HIGH_VALUE_RECOVERY": [
            {"channel_code": "CALL_CENTER", "allocated_capacity": 2},
        ]
    }
    result = _enrich_and_assign(drivers, channel_alloc)
    assert len(result) == 2, f"Expected 2, got {len(result)}"
    assert result[0]["driver_name"] == "Ana Lopez", f"Sort by recent_trips: expected Ana (3 trips) first, got {result[0]['driver_name']}"
    assert result[0]["assigned_channel"] == "CALL_CENTER"
    assert result[1]["assigned_channel"] == "CALL_CENTER"
    print("  PASS: B — single program")


def test_case_c_multiprogram():
    """Case C: Multiprograma"""
    drivers = [
        {"driver_profile_id": "d1", "selected_program_code": "PROGRAM_14_90",
         "final_rank": 5, "completed_orders_week": 10, "lifecycle_state": "EARLY_LIFE",
         "performance_state": "MEDIUM", "driver_name": "Carlos Ruiz", "phone": "999000003",
         "last_trip_at": "2026-06-01", "city": "Lima", "park_name": "Park C"},
        {"driver_profile_id": "d2", "selected_program_code": "PROGRAM_HIGH_VALUE_RECOVERY",
         "final_rank": 1, "completed_orders_week": 2, "lifecycle_state": "CHURNED",
         "performance_state": "NO_TRIPS", "driver_name": "Maria Diaz", "phone": "999000004",
         "last_trip_at": "2026-04-01", "city": "Callao", "park_name": "Park D"},
    ]
    channel_alloc = {
        "PROGRAM_HIGH_VALUE_RECOVERY": [
            {"channel_code": "CALL_CENTER", "allocated_capacity": 1},
        ],
        "PROGRAM_14_90": [
            {"channel_code": "BOT", "allocated_capacity": 1},
        ],
    }
    result = _enrich_and_assign(drivers, channel_alloc)
    assert len(result) == 2
    # HVR (priority 1) should come first
    assert result[0]["program_code"] == "PROGRAM_HIGH_VALUE_RECOVERY"
    assert result[1]["program_code"] == "PROGRAM_14_90"
    assert result[0]["assigned_channel"] == "CALL_CENTER"
    assert result[1]["assigned_channel"] == "BOT"
    print("  PASS: C — multiprograma")


def test_case_d_channel_overflow():
    """Case D: Channel overflows to UNASSIGNED"""
    drivers = [
        {"driver_profile_id": f"d{i}", "selected_program_code": "PROGRAM_HIGH_VALUE_RECOVERY",
         "final_rank": i, "completed_orders_week": i*2, "lifecycle_state": "CHURNED",
         "performance_state": "LOW", "driver_name": f"Driver {i}", "phone": f"99900000{i}",
         "last_trip_at": "2026-05-01", "city": "Lima", "park_name": "Park"}
        for i in range(1, 6)
    ]
    channel_alloc = {
        "PROGRAM_HIGH_VALUE_RECOVERY": [
            {"channel_code": "CALL_CENTER", "allocated_capacity": 2},
            {"channel_code": "SAC", "allocated_capacity": 1},
        ]
    }
    result = _enrich_and_assign(drivers, channel_alloc)
    channels = [r["assigned_channel"] for r in result]
    assert channels.count("CALL_CENTER") == 2
    assert channels.count("SAC") == 1
    assert channels.count("UNASSIGNED") == 2
    print("  PASS: D — channel overflow to UNASSIGNED")


def test_case_e_null_phone():
    """Case E: Telefono nulo"""
    drivers = [
        {"driver_profile_id": "d1", "selected_program_code": "PROGRAM_CHURN_PREVENTION",
         "final_rank": 1, "completed_orders_week": 5, "lifecycle_state": "AT_RISK",
         "driver_name": "Sin Telefono", "phone": None,
         "last_trip_at": None, "city": "Lima", "park_name": "Park E",
         "performance_state": "LOW"},
    ]
    channel_alloc = {
        "PROGRAM_CHURN_PREVENTION": [
            {"channel_code": "CALL_CENTER", "allocated_capacity": 1},
        ]
    }
    result = _enrich_and_assign(drivers, channel_alloc)
    assert len(result) == 1
    assert result[0]["phone"] is None
    assert result[0]["last_trip_date"] is None
    print("  PASS: E — telefono nulo")


def test_case_f_null_name():
    """Case F: Nombre nulo"""
    drivers = [
        {"driver_profile_id": "d1", "selected_program_code": "PROGRAM_ACTIVE_GROWTH",
         "final_rank": 1, "completed_orders_week": 8, "lifecycle_state": "ESTABLISHED",
         "driver_name": None, "phone": "999000099",
         "last_trip_at": "2026-06-02", "city": "Lima", "park_name": "Park F",
         "performance_state": "TARGET"},
    ]
    channel_alloc = {}
    result = _enrich_and_assign(drivers, channel_alloc)
    assert len(result) == 1
    assert result[0]["driver_name"] == "Sin nombre"
    assert result[0]["assigned_channel"] == "UNASSIGNED"
    print("  PASS: F — nombre nulo")


def test_case_g_opportunity_reason():
    """Case G: Opportunity reason generation"""
    d1 = {"lifecycle_state": "CHURNED", "performance_state": "NO_TRIPS", "retention_state": "CHURN_RISK", "productivity_bucket": "CRITICAL"}
    d2 = {"lifecycle_state": None, "performance_state": None, "retention_state": None, "productivity_bucket": None, "exclusion_reason": None}
    d3 = {"lifecycle_state": "ACTIVATED", "performance_state": "LOW", "retention_state": "HEALTHY", "productivity_bucket": "LOW", "exclusion_reason": "CUSTOM_REASON"}

    r1 = _build_opportunity_reason(d1)
    r2 = _build_opportunity_reason(d2)
    r3 = _build_opportunity_reason(d3)

    assert "CHURNED" in r1
    assert "NO_TRIPS" in r1
    assert r2 == "Oportunidad priorizada"
    assert r3 == "CUSTOM_REASON"
    print("  PASS: G — opportunity reason")


def test_case_h_sorting_order():
    """Case H: Sorting order (priority ASC, recent_trips ASC, name ASC)"""
    drivers = [
        {"driver_profile_id": "d1", "selected_program_code": "PROGRAM_ACTIVE_GROWTH",
         "final_rank": 10, "completed_orders_week": 5, "lifecycle_state": "ESTABLISHED",
         "performance_state": "TARGET", "driver_name": "Zoe", "phone": "999",
         "last_trip_at": None, "city": "Lima", "park_name": "P"},
        {"driver_profile_id": "d2", "selected_program_code": "PROGRAM_14_90",
         "final_rank": 5, "completed_orders_week": 20, "lifecycle_state": "EARLY_LIFE",
         "performance_state": "LOW", "driver_name": "Ana", "phone": "999",
         "last_trip_at": None, "city": "Lima", "park_name": "P"},
        {"driver_profile_id": "d3", "selected_program_code": "PROGRAM_HIGH_VALUE_RECOVERY",
         "final_rank": 1, "completed_orders_week": 10, "lifecycle_state": "CHURNED",
         "performance_state": "LOW", "driver_name": "Beta", "phone": "999",
         "last_trip_at": None, "city": "Lima", "park_name": "P"},
        {"driver_profile_id": "d4", "selected_program_code": "PROGRAM_HIGH_VALUE_RECOVERY",
         "final_rank": 2, "completed_orders_week": 5, "lifecycle_state": "CHURNED",
         "performance_state": "LOW", "driver_name": "Alfa", "phone": "999",
         "last_trip_at": None, "city": "Lima", "park_name": "P"},
    ]
    result = _enrich_and_assign(drivers, {})
    # Expected: HVR (priority 1) first, then by recent_trips, then name
    # d3: HVR, 10 trips -> HVR 1st (only one in that group)
    # d4: HVR, 5 trips -> HVR 2nd
    # d2: 14/90, 20 trips -> priority 3
    # d1: AG, 5 trips -> priority 4
    assert result[0]["driver_name"] == "Alfa", f"Expected Alfa (HVR, 5 trips), got {result[0]['driver_name']}"
    assert result[1]["driver_name"] == "Beta", f"Expected Beta (HVR, 10 trips), got {result[1]['driver_name']}"
    assert result[2]["program_code"] == "PROGRAM_14_90"
    assert result[3]["program_code"] == "PROGRAM_ACTIVE_GROWTH"
    print("  PASS: H — sorting order")


def main():
    print("LG-2.5A QA — Opportunity Worklist V1")
    print("Test Cases: A through H\n")

    test_case_a_empty()
    test_case_b_single_program()
    test_case_c_multiprogram()
    test_case_d_channel_overflow()
    test_case_e_null_phone()
    test_case_f_null_name()
    test_case_g_opportunity_reason()
    test_case_h_sorting_order()

    print(f"\n{'='*60}")
    print("QA COMPLETE — 8/8 cases executed.")
    print("GO for LG-2.5A closure.")


if __name__ == "__main__":
    main()
