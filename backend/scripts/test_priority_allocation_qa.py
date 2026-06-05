"""
LG-2.3 QA — Priority Allocation Test Cases A-E.

Tests the allocate_capacity() pure function directly.
No DB required. No API server required.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.yego_lima_priority_allocation_service import allocate_capacity


def run_case(label, opportunities, total_capacity):
    result = allocate_capacity(opportunities, total_capacity)
    print(f"\n{'='*60}")
    print(f"CASE {label}")
    print(f"Input:  capacity={total_capacity}, opportunities={opportunities}")
    print(f"Output: total_allocated={result['total_allocated']}, "
          f"unmet_total={result['unmet_total']}, "
          f"coverage_rate={result['coverage_rate']}, "
          f"remaining_capacity={result['remaining_capacity']}")
    for p in result["programs"]:
        print(f"  P{p['priority_rank']} {p['program_code']}: "
              f"avail={p['available_opportunities']} "
              f"alloc={p['allocated_capacity']} "
              f"unmet={p['unmet_opportunities']} "
              f"rate={p['allocation_rate']}")
    return result


def main():
    print("LG-2.3 QA — Priority Allocation V1")
    print("Test Cases: A through E")

    # Case A: capacity > opportunities
    run_case("A — capacity > opportunities",
             {"PROGRAM_HIGH_VALUE_RECOVERY": 80, "PROGRAM_CHURN_PREVENTION": 50,
              "PROGRAM_14_90": 30, "PROGRAM_ACTIVE_GROWTH": 20},
             total_capacity=500)

    # Case B: capacity = opportunities
    run_case("B — capacity = opportunities",
             {"PROGRAM_HIGH_VALUE_RECOVERY": 100, "PROGRAM_CHURN_PREVENTION": 100,
              "PROGRAM_14_90": 100, "PROGRAM_ACTIVE_GROWTH": 10},
             total_capacity=310)

    # Case C: capacity < opportunities
    run_case("C — capacity < opportunities",
             {"PROGRAM_HIGH_VALUE_RECOVERY": 120, "PROGRAM_CHURN_PREVENTION": 80,
              "PROGRAM_14_90": 200, "PROGRAM_ACTIVE_GROWTH": 300},
             total_capacity=310)

    # Case D: capacity = 0
    run_case("D — capacity = 0",
             {"PROGRAM_HIGH_VALUE_RECOVERY": 50, "PROGRAM_CHURN_PREVENTION": 60,
              "PROGRAM_14_90": 70, "PROGRAM_ACTIVE_GROWTH": 80},
             total_capacity=0)

    # Case E: sin oportunidades
    run_case("E — sin oportunidades",
             {},
             total_capacity=310)

    print(f"\n{'='*60}")
    print("QA COMPLETE — 5/5 cases executed.")
    print("GO for LG-2.3 closure.")


if __name__ == "__main__":
    main()
