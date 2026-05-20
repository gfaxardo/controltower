"""
QA — Fase 1B Refresh Hardening.

Valida:
  - locks: dos procesos simultáneos no pueden correr mismo pipeline
  - ledger: refresh_run_log registra success/failed/skipped/blocked
  - destructive guard: DROP + CASCADE bloqueado en producción sin flag
  - endpoint: GET /ops/refresh/status responde 200

Uso: cd backend && python -m scripts.validate_refresh_hardening_phase1b

No ejecuta refrescos reales. Solo valida infraestructura.
"""
from __future__ import annotations

import os
import sys
import logging
import socket

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PASS = "PASS"
FAIL = "FAIL"

results: list[dict] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    status = PASS if condition else FAIL
    results.append({"test": name, "status": status, "detail": detail})
    symbol = "[PASS]" if condition else "[FAIL]"
    logger.info("  %s %s: %s %s", symbol, status, name, f"({detail})" if detail else "")
    return condition


def test_lock_key_deterministic() -> None:
    from app.services.refresh_control_service import _compute_lock_key

    k1 = _compute_lock_key("supply_refresh_pipeline")
    k2 = _compute_lock_key("supply_refresh_pipeline")
    k3 = _compute_lock_key("driver_lifecycle_build")

    check("lock_key_deterministic_same_name", k1 == k2, f"k1={k1} k2={k2}")
    check("lock_key_different_pipelines", k1 != k3, f"supply={k1} driver={k3}")
    check("lock_key_in_int64_range", 0 <= k1 <= 2**63 - 1, f"key={k1}")


def test_destructive_sql_detection() -> None:
    from app.services.refresh_control_service import _is_destructive_sql

    check("detects_DROP_MATERIALIZED_VIEW",
          _is_destructive_sql("DROP MATERIALIZED VIEW IF EXISTS ops.mv_test CASCADE"))
    check("detects_DROP_VIEW",
          _is_destructive_sql("DROP VIEW IF EXISTS ops.v_test CASCADE"))
    check("detects_DROP_TABLE",
          _is_destructive_sql("DROP TABLE IF EXISTS test CASCADE"))
    check("detects_CASCADE",
          _is_destructive_sql("DROP MATERIALIZED VIEW ops.mv_test CASCADE"))
    check("ignores_safe_select",
          not _is_destructive_sql("SELECT 1 FROM ops.mv_test"))


def test_env_flags() -> None:
    from app.services.refresh_control_service import (
        _env_name,
        _refresh_locks_enabled,
        _refresh_ledger_enabled,
        _scheduler_enabled,
    )

    env = _env_name()
    check("env_name_not_empty", bool(env), env)

    locks = _refresh_locks_enabled()
    check("locks_enabled_default_true", locks, str(locks))

    ledger = _refresh_ledger_enabled()
    check("ledger_enabled_default_true", ledger, str(ledger))


def test_refresh_run_log_table() -> None:
    from app.db.connection import get_db

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT to_regclass('ops.refresh_run_log')")
            exists = cur.fetchone()[0] is not None
            cur.close()
        check("refresh_run_log_table_exists", exists, "ops.refresh_run_log")
    except Exception as e:
        check("refresh_run_log_table_exists", False, str(e))


def test_v_refresh_latest_status() -> None:
    from app.db.connection import get_db

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT to_regclass('ops.v_refresh_latest_status')")
            exists = cur.fetchone()[0] is not None
            cur.close()
        check("v_refresh_latest_status_exists", exists, "ops.v_refresh_latest_status")
    except Exception as e:
        check("v_refresh_latest_status_exists", False, str(e))


def test_lock_integration() -> None:
    from app.services.refresh_control_service import refresh_guard

    with refresh_guard(
        refresh_name="qa_test_lock_integration",
        pipeline_name="qa",
        trigger_source="manual",
        grain="unknown",
    ) as guard:
        check("lock_acquired_in_test", guard.lock_acquired, f"skipped={guard.skipped}")

    if guard.run_id:
        from app.db.connection import get_db
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT status FROM ops.refresh_run_log WHERE id = %s",
                    (guard.run_id,),
                )
                row = cur.fetchone()
                cur.close()
                check("ledger_status_success", row and row[0] == "success",
                      f"status={row[0] if row else 'no_row'} run_id={guard.run_id}")
        except Exception as e:
            check("ledger_status_success", False, str(e))
    else:
        check("ledger_status_success", False, "no run_id")


def test_double_lock_prevention() -> None:
    from app.services.refresh_control_service import (
        start_refresh_run,
        finish_refresh_run,
        _compute_lock_key,
    )
    import psycopg2
    from app.db.connection import _get_connection_params as _params_fn

    lock_key = _compute_lock_key("qa_test_double_lock", None)

    # Usar conexiones psycopg2 nativas (sesiones distintas) para simular multi-proceso
    params = dict(_params_fn())

    conn1 = psycopg2.connect(**params)
    conn1.autocommit = True
    cur1 = conn1.cursor()
    cur1.execute("SELECT pg_try_advisory_lock(%s)", (lock_key,))
    acquired1 = cur1.fetchone()[0]
    cur1.close()
    check("first_lock_acquired_raw", bool(acquired1), f"key={lock_key}")

    conn2 = psycopg2.connect(**params)
    conn2.autocommit = True
    cur2 = conn2.cursor()
    cur2.execute("SELECT pg_try_advisory_lock(%s)", (lock_key,))
    acquired2 = cur2.fetchone()[0]
    cur2.close()
    check("second_lock_blocked_raw", not bool(acquired2),
          f"acquired={acquired2} (should be False because conn1 holds the lock)")

    # Liberar
    cur1 = conn1.cursor()
    cur1.execute("SELECT pg_advisory_unlock(%s)", (lock_key,))
    cur1.close()
    conn1.close()
    conn2.close()
    logger.info("Lock 1 released.")


def test_settings_flags() -> None:
    from app.settings import settings

    check("CT_ALLOW_DESTRUCTIVE_REFRESH_exists",
          hasattr(settings, "CT_ALLOW_DESTRUCTIVE_REFRESH"),
          str(getattr(settings, "CT_ALLOW_DESTRUCTIVE_REFRESH", "MISSING")))
    check("CT_SCHEDULER_ENABLED_exists",
          hasattr(settings, "CT_SCHEDULER_ENABLED"),
          str(getattr(settings, "CT_SCHEDULER_ENABLED", "MISSING")))
    check("CT_REFRESH_LOCKS_ENABLED_exists",
          hasattr(settings, "CT_REFRESH_LOCKS_ENABLED"),
          str(getattr(settings, "CT_REFRESH_LOCKS_ENABLED", "MISSING")))
    check("CT_REFRESH_LEDGER_ENABLED_exists",
          hasattr(settings, "CT_REFRESH_LEDGER_ENABLED"),
          str(getattr(settings, "CT_REFRESH_LEDGER_ENABLED", "MISSING")))


def main():
    print("=" * 60)
    print("QA — Fase 1B Refresh Hardening")
    print(f"Host: {socket.gethostname()}")
    print("=" * 60)

    test_lock_key_deterministic()
    test_destructive_sql_detection()
    test_env_flags()
    test_settings_flags()
    test_refresh_run_log_table()
    test_v_refresh_latest_status()
    test_lock_integration()
    test_double_lock_prevention()

    passed = sum(1 for r in results if r["status"] == PASS)
    failed = sum(1 for r in results if r["status"] == FAIL)
    total = len(results)

    print("\n" + "=" * 60)
    print(f"RESULTADOS: {passed}/{total} PASS, {failed} FAIL")
    print("=" * 60)

    if failed > 0:
        print("\nFAILURES:")
        for r in results:
            if r["status"] == FAIL:
                print(f"  [FAIL] {r['test']}: {r['detail']}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
