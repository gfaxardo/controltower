"""
Serving enforcement validation script.

Checks:
1. All critical features are registered in SERVING_REGISTRY
2. Policy declarations exist in critical services
3. Forbidden sources are not used in serving code paths
4. Registry and policy consistency

Usage:
    python -m scripts.check_serving_enforcement
"""
from __future__ import annotations

import os
import re
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.utils.source_trace import SERVING_REGISTRY, get_feature_entry
from app.services.serving_guardrails import FORBIDDEN_SERVING_SOURCES


CRITICAL_FEATURES = [
    "Omniview monthly",
    "Omniview weekly",
    "Omniview daily",
    "Omniview Matrix",
    "Control Loop Plan vs Real",
    "Real LOB monthly",
    "Real LOB monthly v2",
    "Real LOB weekly v2",
    "Real LOB v2 data",
]

SERVICES_WITH_POLICY = {
    "business_slice_omniview_service.py": "Omniview Matrix",
    "control_loop_plan_vs_real_service.py": "Control Loop Plan vs Real",
    "real_lob_service.py": "Real LOB monthly",
    "real_lob_service_v2.py": "Real LOB monthly v2",
    "real_lob_v2_data_service.py": "Real LOB v2 data",
}

SERVICES_DIR = os.path.join(BACKEND_DIR, "app", "services")


def check_registry() -> tuple[int, int, list[str]]:
    ok = 0
    fail = 0
    issues = []
    for name in CRITICAL_FEATURES:
        entry = get_feature_entry(name)
        if entry:
            ok += 1
        else:
            fail += 1
            issues.append(f"MISSING_REGISTRY: {name}")
    return ok, fail, issues


def check_policies() -> tuple[int, int, list[str]]:
    ok = 0
    fail = 0
    issues = []
    for filename, feature in SERVICES_WITH_POLICY.items():
        filepath = os.path.join(SERVICES_DIR, filename)
        if not os.path.exists(filepath):
            fail += 1
            issues.append(f"FILE_MISSING: {filename}")
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        if "_SERVING_POLICY" in content and "ServingPolicy" in content:
            ok += 1
        else:
            fail += 1
            issues.append(f"NO_POLICY: {filename} (feature: {feature})")
    return ok, fail, issues


def check_forbidden_sources() -> tuple[int, int, list[str]]:
    ok = 0
    violations = 0
    issues = []

    serving_files = [
        "business_slice_omniview_service.py",
        "control_loop_plan_vs_real_service.py",
        "real_lob_service.py",
        "real_lob_service_v2.py",
        "real_lob_v2_data_service.py",
        "real_lob_daily_service.py",
        "real_operational_service.py",
    ]

    forbidden_patterns = []
    for src in FORBIDDEN_SERVING_SOURCES:
        escaped = re.escape(src)
        forbidden_patterns.append(
            re.compile(rf'FROM\s+{escaped}', re.IGNORECASE)
        )

    for filename in serving_files:
        filepath = os.path.join(SERVICES_DIR, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        file_ok = True
        for i, pat in enumerate(forbidden_patterns):
            matches = pat.findall(content)
            if matches:
                src_name = FORBIDDEN_SERVING_SOURCES[i]
                is_string_const = f'= "{src_name}"' in content or f"= '{src_name}'" in content
                has_policy = "assert_serving_source" in content or "SERVING_DISCIPLINE" in content

                if is_string_const and not any(
                    f"FROM {src_name}" in line and "def " not in line
                    for line in content.split("\n")
                    if not line.strip().startswith("#")
                    and "forbidden" not in line.lower()
                    and "policy" not in line.lower()
                ):
                    continue

                if has_policy:
                    continue

                violations += 1
                file_ok = False
                issues.append(
                    f"FORBIDDEN_IN_SERVING: {filename} uses {src_name} without enforcement"
                )
        if file_ok:
            ok += 1

    return ok, violations, issues


def check_consistency() -> tuple[int, int, list[str]]:
    ok = 0
    fail = 0
    issues = []

    for filename, feature in SERVICES_WITH_POLICY.items():
        filepath = os.path.join(SERVICES_DIR, filename)
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        entry = get_feature_entry(feature)
        if entry is None:
            fail += 1
            issues.append(f"CONSISTENCY: {feature} has policy in {filename} but no registry entry")
            continue

        if entry.preferred_source in content or "FACT_" in content or "MV_" in content:
            ok += 1
        else:
            fail += 1
            issues.append(f"CONSISTENCY: {filename} may not use preferred source {entry.preferred_source}")

    return ok, fail, issues


def main():
    print("=" * 60)
    print("SERVING ENFORCEMENT CHECK")
    print("=" * 60)

    total_ok = 0
    total_fail = 0
    total_warn = 0
    all_issues: list[str] = []

    print("\n--- 1. Registry completeness ---")
    ok, fail, issues = check_registry()
    total_ok += ok
    total_fail += fail
    all_issues.extend(issues)
    print(f"  Registered: {ok}/{len(CRITICAL_FEATURES)}")
    for i in issues:
        print(f"  [FAIL] {i}")

    print("\n--- 2. Policy declarations ---")
    ok, fail, issues = check_policies()
    total_ok += ok
    total_fail += fail
    all_issues.extend(issues)
    print(f"  With policy: {ok}/{len(SERVICES_WITH_POLICY)}")
    for i in issues:
        print(f"  [FAIL] {i}")

    print("\n--- 3. Forbidden source scan ---")
    ok, violations, issues = check_forbidden_sources()
    total_ok += ok
    total_warn += violations
    all_issues.extend(issues)
    print(f"  Clean files: {ok}, Violations: {violations}")
    for i in issues:
        print(f"  [WARN] {i}")

    print("\n--- 4. Policy-registry consistency ---")
    ok, fail, issues = check_consistency()
    total_ok += ok
    total_fail += fail
    all_issues.extend(issues)
    print(f"  Consistent: {ok}/{len(SERVICES_WITH_POLICY)}")
    for i in issues:
        print(f"  [FAIL] {i}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  total_features_checked: {len(CRITICAL_FEATURES)}")
    print(f"  compliant:             {total_ok}")
    print(f"  warnings:              {total_warn}")
    print(f"  non_compliant:         {total_fail}")
    print(f"  missing_registry:      {sum(1 for i in all_issues if 'MISSING_REGISTRY' in i)}")
    print(f"  forbidden_usage:       {sum(1 for i in all_issues if 'FORBIDDEN_IN_SERVING' in i)}")
    print(f"  no_policy:             {sum(1 for i in all_issues if 'NO_POLICY' in i)}")

    if total_fail > 0:
        print(f"\nRESULT: NON_COMPLIANT ({total_fail} failures)")
        return 1
    elif total_warn > 0:
        print(f"\nRESULT: WARNING ({total_warn} warnings)")
        return 0
    else:
        print("\nRESULT: COMPLIANT")
        return 0


if __name__ == "__main__":
    sys.exit(main())
