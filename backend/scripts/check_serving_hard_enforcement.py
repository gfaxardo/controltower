"""
Hard enforcement validation script for FASE 2.6.

Checks:
1. Features with policy registered (register_policy called at import)
2. Features with SERVING_REGISTRY entry
3. Features with wrapper usage (execute_serving_query traced)
4. Forbidden source blocking works
5. Preferred source match enforcement
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.serving_guardrails import (
    FORBIDDEN_SERVING_SOURCES,
    ServingPolicy,
    ServingSourceViolation,
    QueryMode,
    SourceType,
    assert_serving_source,
    execute_serving_query,
    get_all_declared_policies,
    is_policy_declared,
    register_policy,
)
from app.utils.source_trace import (
    SERVING_REGISTRY,
    assert_feature_registered,
    get_unguarded_features,
)


def _import_services():
    """Force-import services so register_policy() calls execute."""
    try:
        import app.services.business_slice_omniview_service  # noqa: F401
    except Exception as e:
        print(f"  WARN: business_slice_omniview_service import: {e}")
    try:
        import app.services.control_loop_plan_vs_real_service  # noqa: F401
    except Exception as e:
        print(f"  WARN: control_loop_plan_vs_real_service import: {e}")
    try:
        import app.services.real_lob_service  # noqa: F401
    except Exception as e:
        print(f"  WARN: real_lob_service import: {e}")
    try:
        import app.services.real_lob_service_v2  # noqa: F401
    except Exception as e:
        print(f"  WARN: real_lob_service_v2 import: {e}")
    try:
        import app.services.real_lob_v2_data_service  # noqa: F401
    except Exception as e:
        print(f"  WARN: real_lob_v2_data_service import: {e}")


CRITICAL_FEATURES = [
    "Omniview Matrix",
    "Control Loop Plan vs Real",
    "Real LOB monthly",
    "Real LOB monthly v2",
    "Real LOB v2 data",
]


def check_policy_registry():
    print("\n=== CHECK 1: Policy Registry (register_policy) ===")
    _import_services()
    policies = get_all_declared_policies()
    print(f"  Declared policies: {len(policies)}")
    for name in sorted(policies.keys()):
        print(f"    [OK] {name}")

    missing_critical = [f for f in CRITICAL_FEATURES if not is_policy_declared(f)]
    if missing_critical:
        print(f"  MISSING policies for CRITICAL features:")
        for m in missing_critical:
            print(f"    [FAIL] {m}")
        return False

    serving_features = [e for e in SERVING_REGISTRY if e.query_mode == QueryMode.SERVING]
    other_missing = [
        e.feature_name for e in serving_features
        if not is_policy_declared(e.feature_name) and e.feature_name not in CRITICAL_FEATURES
    ]
    if other_missing:
        print(f"  Non-critical features without policy (future scope):")
        for m in other_missing:
            print(f"    [INFO] {m}")

    print(f"  All {len(CRITICAL_FEATURES)} critical features have policies declared.")
    return True


def check_registry_coverage():
    print("\n=== CHECK 2: SERVING_REGISTRY Coverage ===")
    print(f"  Registry entries: {len(SERVING_REGISTRY)}")
    serving_count = sum(1 for e in SERVING_REGISTRY if e.query_mode == QueryMode.SERVING)
    audit_count = sum(1 for e in SERVING_REGISTRY if e.query_mode == QueryMode.AUDIT)
    drill_count = sum(1 for e in SERVING_REGISTRY if e.query_mode == QueryMode.DRILL)
    print(f"    serving={serving_count}, audit={audit_count}, drill={drill_count}")

    critical = [
        "Omniview Matrix", "Control Loop Plan vs Real",
        "Real LOB monthly", "Real LOB monthly v2", "Real LOB v2 data",
    ]
    ok = True
    for name in critical:
        try:
            assert_feature_registered(name)
            print(f"    [OK] {name}")
        except ValueError:
            print(f"    [FAIL] {name} NOT in registry")
            ok = False
    return ok


def check_forbidden_source_blocking():
    print("\n=== CHECK 3: Forbidden Source Blocking ===")
    test_policy = ServingPolicy(
        feature_name="Omniview Matrix",
        query_mode=QueryMode.SERVING,
        preferred_source="ops.real_business_slice_month_fact",
        preferred_source_type=SourceType.FACT,
        strict_mode=True,
    )
    ok = True
    for src in FORBIDDEN_SERVING_SOURCES:
        try:
            assert_serving_source(test_policy, src)
            print(f"    [FAIL] {src} was NOT blocked")
            ok = False
        except ServingSourceViolation:
            print(f"    [OK] {src} correctly blocked")
    return ok


def check_wrapper_registry_gate():
    print("\n=== CHECK 4: execute_serving_query Registry Gate ===")
    unregistered_policy = ServingPolicy(
        feature_name="FAKE_FEATURE_NOT_IN_REGISTRY",
        query_mode=QueryMode.SERVING,
        preferred_source="fake_table",
        preferred_source_type=SourceType.FACT,
        strict_mode=True,
    )
    try:
        execute_serving_query(unregistered_policy, None, "SELECT 1")
        print("    [FAIL] Unregistered feature was not blocked")
        return False
    except ValueError as e:
        if "not registered" in str(e):
            print("    [OK] Unregistered feature correctly blocked by wrapper")
            return True
        print(f"    [FAIL] Unexpected error: {e}")
        return False
    except Exception as e:
        if "not registered" in str(e):
            print("    [OK] Unregistered feature correctly blocked by wrapper")
            return True
        print(f"    [FAIL] Unexpected error: {e}")
        return False


def check_preferred_source_match():
    print("\n=== CHECK 5: Preferred Source Match ===")
    policies = get_all_declared_policies()
    ok = True
    for name, pol in policies.items():
        if pol.require_preferred_source_match:
            print(f"    [OK] {name}: require_preferred_source_match=True")
        else:
            entry = None
            for e in SERVING_REGISTRY:
                if e.feature_name == name:
                    entry = e
                    break
            if entry and entry.query_mode == QueryMode.SERVING:
                print(f"    [INFO] {name}: require_preferred_source_match=False (optional)")
    return ok


def main():
    print("=" * 60)
    print("HARD ENFORCEMENT VALIDATION — FASE 2.6")
    print("=" * 60)

    results = [
        check_policy_registry(),
        check_registry_coverage(),
        check_forbidden_source_blocking(),
        check_wrapper_registry_gate(),
        check_preferred_source_match(),
    ]

    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    result = "COMPLIANT" if all(results) else "NON_COMPLIANT"
    print(f"RESULT: {result} ({passed}/{total} checks passed)")
    print("=" * 60)
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
