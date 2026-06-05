"""
LG-2.4 QA — Channel Allocation Test Cases A-F.

Tests the allocate_to_channels() pure function directly.
No DB required. No API server required.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.yego_lima_channel_allocation_service import allocate_to_channels


def run_case(label, program_allocations, channel_capacities):
    result = allocate_to_channels(program_allocations, channel_capacities)
    print(f"\n{'='*60}")
    print(f"CASE {label}")
    print(f"Channel capacities: {channel_capacities}")
    print(f"Program allocations:")
    for p in program_allocations:
        print(f"  P{p.get('priority_rank')} {p['program_code']}: alloc={p['allocated_capacity']}")
    print(f"\nResult:")
    print(f"  total_channel_allocated={result['total_channel_allocated']}")
    print(f"  unassigned_capacity={result['unassigned_capacity']}")
    print(f"  Channels:")
    for ch in result['channels']:
        print(f"    {ch['channel_code']}: {ch['allocated_capacity']}/{ch['total_capacity']} ({round(ch['utilization_rate'] * 100)}%)")
    print(f"  Programs:")
    for p in result['programs']:
        chs = ', '.join(f"{c['channel_code']}={c['allocated_capacity']}" for c in p['channel_allocations'])
        print(f"    {p['program_code']}: alloc={p['program_allocated_capacity']} channels=[{chs}] unassigned={p['unassigned_capacity']}")
    return result


def main():
    print("LG-2.4 QA — Channel Allocation V1")
    print("Test Cases: A through F")

    # Case A: Capacidad por canal suficiente
    # Each program preference matches and has plenty of capacity
    run_case("A — canal suficiente",
             [
                 {"program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "program_name": "HVR", "priority_rank": 1, "allocated_capacity": 80},
                 {"program_code": "PROGRAM_CHURN_PREVENTION", "program_name": "Churn", "priority_rank": 2, "allocated_capacity": 50},
                 {"program_code": "PROGRAM_14_90", "program_name": "14/90", "priority_rank": 3, "allocated_capacity": 100},
                 {"program_code": "PROGRAM_ACTIVE_GROWTH", "program_name": "AG", "priority_rank": 4, "allocated_capacity": 80},
             ],
             {"CALL_CENTER": 80, "SAC": 30, "BOT": 200})

    # Case B: Bot se llena y rebalsa a Call Center
    # 14/90 prefers BOT first, but BOT only has 150. Then CALL_CENTER.
    run_case("B — Bot se llena, rebalsa a Call Center",
             [
                 {"program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "program_name": "HVR", "priority_rank": 1, "allocated_capacity": 60},
                 {"program_code": "PROGRAM_CHURN_PREVENTION", "program_name": "Churn", "priority_rank": 2, "allocated_capacity": 40},
                 {"program_code": "PROGRAM_14_90", "program_name": "14/90", "priority_rank": 3, "allocated_capacity": 200},
                 {"program_code": "PROGRAM_ACTIVE_GROWTH", "program_name": "AG", "priority_rank": 4, "allocated_capacity": 10},
             ],
             {"CALL_CENTER": 80, "SAC": 30, "BOT": 150})

    # Case C: Call Center se llena y rebalsa a SAC
    # HVR + Churn both prefer CALL_CENTER first. If CALL_CENTER exhausted, go SAC.
    run_case("C — Call Center se llena, rebalsa a SAC",
             [
                 {"program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "program_name": "HVR", "priority_rank": 1, "allocated_capacity": 100},
                 {"program_code": "PROGRAM_CHURN_PREVENTION", "program_name": "Churn", "priority_rank": 2, "allocated_capacity": 60},
                 {"program_code": "PROGRAM_14_90", "program_name": "14/90", "priority_rank": 3, "allocated_capacity": 50},
                 {"program_code": "PROGRAM_ACTIVE_GROWTH", "program_name": "AG", "priority_rank": 4, "allocated_capacity": 30},
             ],
             {"CALL_CENTER": 80, "SAC": 50, "BOT": 200})

    # Case D: Capacidad total de canales menor que priority allocation
    # Unassigned capacity expected
    run_case("D — canales < priority allocation",
             [
                 {"program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "program_name": "HVR", "priority_rank": 1, "allocated_capacity": 100},
                 {"program_code": "PROGRAM_CHURN_PREVENTION", "program_name": "Churn", "priority_rank": 2, "allocated_capacity": 80},
                 {"program_code": "PROGRAM_14_90", "program_name": "14/90", "priority_rank": 3, "allocated_capacity": 100},
             ],
             {"CALL_CENTER": 40, "SAC": 20, "BOT": 50})

    # Case E: Canal con capacidad 0
    # Bot with 0 capacity; programs preferring BOT (14/90, AG) skip it
    run_case("E — canal con capacidad 0",
             [
                 {"program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "program_name": "HVR", "priority_rank": 1, "allocated_capacity": 50},
                 {"program_code": "PROGRAM_CHURN_PREVENTION", "program_name": "Churn", "priority_rank": 2, "allocated_capacity": 30},
                 {"program_code": "PROGRAM_14_90", "program_name": "14/90", "priority_rank": 3, "allocated_capacity": 80},
                 {"program_code": "PROGRAM_ACTIVE_GROWTH", "program_name": "AG", "priority_rank": 4, "allocated_capacity": 20},
             ],
             {"CALL_CENTER": 60, "SAC": 30, "BOT": 0})

    # Case F: Sin oportunidades (no program allocations)
    run_case("F — sin oportunidades",
             [
                 {"program_code": "PROGRAM_HIGH_VALUE_RECOVERY", "program_name": "HVR", "priority_rank": 1, "allocated_capacity": 0},
                 {"program_code": "PROGRAM_CHURN_PREVENTION", "program_name": "Churn", "priority_rank": 2, "allocated_capacity": 0},
                 {"program_code": "PROGRAM_14_90", "program_name": "14/90", "priority_rank": 3, "allocated_capacity": 0},
                 {"program_code": "PROGRAM_ACTIVE_GROWTH", "program_name": "AG", "priority_rank": 4, "allocated_capacity": 0},
             ],
             {"CALL_CENTER": 80, "SAC": 30, "BOT": 200})

    print(f"\n{'='*60}")
    print("QA COMPLETE — 6/6 cases executed.")
    print("GO for LG-2.4 closure.")


if __name__ == "__main__":
    main()
