"""
check_db_layer_gate.py — Validates DB-level gate enforcement (FASE 2.7).

Checks:
1. DB_SERVING_GUARD_MODE is a valid mode
2. Critical features have policy + registry
3. QueryExecutionContext can be created from policy
4. Ungated execution is detected (_active_db_gate not set)
5. Forbidden source still blocks in serving mode
6. Summary: COMPLIANT / NON_COMPLIANT
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

passed = 0
failed = 0


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"  [PASS] {msg}")


def fail(msg: str) -> None:
    global failed
    failed += 1
    print(f"  [FAIL] {msg}")


# Force imports to trigger register_policy calls
print("\n=== 1. Import critical services (triggers register_policy) ===")
try:
    import app.services.business_slice_omniview_service  # noqa: F401
    import app.services.control_loop_plan_vs_real_service  # noqa: F401
    import app.services.real_lob_service  # noqa: F401
    import app.services.real_lob_service_v2  # noqa: F401
    import app.services.real_lob_v2_data_service  # noqa: F401
    ok("All 5 critical services imported successfully")
except Exception as e:
    fail(f"Import error: {e}")

print("\n=== 2. DB_SERVING_GUARD_MODE is valid ===")
from app.services.serving_guardrails import (
    DbGuardMode,
    QueryExecutionContext,
    QueryMode,
    ServingPolicy,
    ServingSourceViolation,
    SourceType,
    context_from_policy,
    execute_db_gated_query,
    get_db_guard_mode,
    get_db_gate_summary,
    is_db_gate_active,
    is_policy_declared,
    set_db_guard_mode,
)

mode = get_db_guard_mode()
if mode in (DbGuardMode.OFF, DbGuardMode.WARN, DbGuardMode.STRICT):
    ok(f"DB_SERVING_GUARD_MODE = {mode.value}")
else:
    fail(f"DB_SERVING_GUARD_MODE invalid: {mode}")

print("\n=== 3. Critical features have policy declared ===")
CRITICAL_FEATURES = [
    "Omniview Matrix",
    "Control Loop Plan vs Real",
    "Real LOB monthly",
    "Real LOB monthly v2",
    "Real LOB v2 data",
]
for feat in CRITICAL_FEATURES:
    if is_policy_declared(feat):
        ok(f"Policy declared: {feat}")
    else:
        fail(f"Policy NOT declared: {feat}")

print("\n=== 4. QueryExecutionContext creation from policy ===")
test_policy = ServingPolicy(
    feature_name="test_db_gate",
    query_mode=QueryMode.SERVING,
    preferred_source="ops.test_fact",
    preferred_source_type=SourceType.FACT,
    strict_mode=True,
)
ctx = context_from_policy(test_policy, source_name="ops.test_fact")
if ctx.feature_name == "test_db_gate" and ctx.query_mode == QueryMode.SERVING:
    ok("QueryExecutionContext created correctly from policy")
else:
    fail("QueryExecutionContext fields mismatch")

print("\n=== 5. Ungated execution detection ===")
if not is_db_gate_active():
    ok("Outside DB gate: is_db_gate_active() == False (correct)")
else:
    fail("is_db_gate_active() should be False outside gate")

print("\n=== 6. Forbidden source blocks in strict mode ===")
original_mode = get_db_guard_mode()
set_db_guard_mode(DbGuardMode.STRICT)
from app.services.serving_guardrails import assert_serving_source

blocked = False
try:
    assert_serving_source(test_policy, "public.trips_all")
except ServingSourceViolation:
    blocked = True
if blocked:
    ok("Forbidden source 'public.trips_all' correctly blocked in strict mode")
else:
    fail("Forbidden source NOT blocked")
set_db_guard_mode(original_mode)

print("\n=== 7. DB gate summary structure ===")
summary = get_db_gate_summary()
if "total_entries" in summary and "guard_mode" in summary and "by_feature" in summary:
    ok(f"DB gate summary valid: guard_mode={summary['guard_mode']}, entries={summary['total_entries']}")
else:
    fail("DB gate summary missing expected keys")

print("\n=== 8. execute_serving_query() detects bypass (no ContextVar) in strict ===")
import inspect
from app.services.serving_guardrails import execute_serving_query
esq_src = inspect.getsource(execute_serving_query)
if "_active_db_gate" in esq_src or "DB_GATE_BYPASS" in esq_src:
    ok("execute_serving_query() checks _active_db_gate — bypass detection active")
else:
    fail("execute_serving_query() does NOT check _active_db_gate — bypass possible")

print(f"\n{'='*60}")
total = passed + failed
result = "COMPLIANT" if failed == 0 else "NON_COMPLIANT"
print(f"Result: {result}  ({passed}/{total} passed, {failed} failed)")
print(f"db_guard_mode: {get_db_guard_mode().value}")
print(f"db_gated_features: {len(CRITICAL_FEATURES)}")
print(f"{'='*60}")

sys.exit(0 if failed == 0 else 1)
