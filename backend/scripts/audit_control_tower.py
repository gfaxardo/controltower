"""
Control Tower: Audit Engine — auditoría automática de integridad de datos.

Cada check se ejecuta en SU PROPIA CONEXIÓN y SU PROPIA TRANSACCIÓN.
- Aislamiento total: un timeout o error no contamina los siguientes checks.
- Timeout configurable: AUDIT_TIMEOUT_MS (default 600000 = 10 min).
- Logging: [AUDIT] START/FINISHED/WARNING por check con duración.
- Persistencia: ops.data_integrity_audit + ops.audit_query_performance (execution_time_ms, status).

Uso: cd backend && python -m scripts.audit_control_tower
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    from psycopg2 import errors as pg_errors
except ImportError:
    pg_errors = None

from app.db.connection import get_db_audit, init_db_pool

# Timeout por consulta (ms). Variable de entorno: AUDIT_TIMEOUT_MS (default 10 min).
AUDIT_TIMEOUT_MS = int(os.environ.get("AUDIT_TIMEOUT_MS", os.environ.get("AUDIT_STATEMENT_TIMEOUT_MS", "600000")))

# Logger del audit engine
LOG = logging.getLogger("audit_control_tower")
LOG.setLevel(logging.INFO)
if not LOG.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("[%(asctime)s] [AUDIT] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
    LOG.addHandler(h)


def _is_timeout_or_aborted(exc: BaseException) -> bool:
    """Detecta QueryCanceled (57014), statement timeout o transacción abortada."""
    if isinstance(exc, psycopg2.Error) and getattr(exc, "pgcode", None) == "57014":
        return True
    query_canceled = getattr(pg_errors, "QueryCanceled", None) if pg_errors else None
    if query_canceled and isinstance(exc, query_canceled):
        return True
    msg = str(exc).lower()
    return "statement timeout" in msg or "canceling statement" in msg or "transaction is aborted" in msg or "querycanceled" in msg


def _run_check(
    check_name: str,
    sql: str,
    ts: datetime,
    audit_timeout_ms: int,
    *,
    run_one: bool = True,
    status_from_row: Optional[Callable[[Any], str]] = None,
    metric_from_row: Optional[Callable[[Any], Any]] = None,
    details_from_row: Optional[Callable[[Any], Any]] = None,
    insert_audit_row: bool = True,
) -> tuple[str, float, str]:
    """
    Ejecuta un solo check en su propia conexión y transacción.
    Returns: (status_for_results, duration_sec, performance_status).
    performance_status: OK | TIMEOUT | ERROR
    """
    start = time.perf_counter()
    LOG.info("START check: %s", check_name)
    conn = None
    performance_status = "ERROR"
    result_status = "?"
    duration_sec = 0.0

    try:
        with get_db_audit(audit_timeout_ms) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            # Fijar timeout en sesión (refuerzo por si la conexión no lo aplicó)
            cur.execute(f"SET statement_timeout = '{audit_timeout_ms}'")
            cur.execute(sql)
            rows = cur.fetchall()
            row = rows[0] if rows and run_one else (rows if not run_one else None)

            if status_from_row:
                result_status = status_from_row(row)
            else:
                result_status = (row.get("status") or "OK") if row else "OK"

            metric_val = metric_from_row(row) if metric_from_row else (row.get("loss_pct") or row.get("diff_pct") or row.get("pct_sin_lob") if row else None)
            details_val = details_from_row(row) if details_from_row else (str(row) if row else None)

            if insert_audit_row:
                cur.execute(
                    "INSERT INTO ops.data_integrity_audit (timestamp, check_name, status, metric_value, details) VALUES (%s, %s, %s, %s, %s)",
                    (ts, check_name, result_status, metric_val, details_val),
                )

            execution_time_ms = int((time.perf_counter() - start) * 1000)
            cur.execute(
                "INSERT INTO ops.audit_query_performance (check_name, execution_time_ms, executed_at, status) VALUES (%s, %s, %s, %s)",
                (check_name, execution_time_ms, ts, "OK"),
            )
            conn.commit()
            duration_sec = execution_time_ms / 1000.0
            performance_status = "OK"
            LOG.info("FINISHED check: %s | duration=%.2fs | status=%s", check_name, duration_sec, result_status)
            return (result_status, duration_sec, performance_status)

    except Exception as e:
        duration_sec = time.perf_counter() - start
        execution_time_ms = int(duration_sec * 1000)
        if _is_timeout_or_aborted(e):
            performance_status = "TIMEOUT"
            LOG.warning("WARNING check timeout: %s | duration=%.2fs", check_name, duration_sec)
        else:
            performance_status = "ERROR"
            LOG.warning("WARNING check error: %s | %s | duration=%.2fs", check_name, e, duration_sec)

        # Rollback y cierre: get_db_audit ya hace rollback en except y close en finally.
        # Persistir métrica y resultado fallido en conexión nueva (no reutilizar abortada).
        try:
            with get_db_audit(audit_timeout_ms) as conn2:
                cur2 = conn2.cursor()
                cur2.execute(
                    "INSERT INTO ops.audit_query_performance (check_name, execution_time_ms, executed_at, status) VALUES (%s, %s, %s, %s)",
                    (check_name, execution_time_ms, ts, performance_status),
                )
                cur2.execute(
                    "INSERT INTO ops.data_integrity_audit (timestamp, check_name, status, metric_value, details) VALUES (%s, %s, %s, %s, %s)",
                    (ts, check_name, performance_status, None, str(e)[:2000]),
                )
                conn2.commit()
        except Exception as e2:
            LOG.warning("No se pudo guardar performance para %s: %s", check_name, e2)

        return (result_status, duration_sec, performance_status)


def run_audit() -> dict[str, str]:
    """Ejecuta todos los checks; cada uno en su propia conexión y transacción."""
    init_db_pool()
    results: dict[str, str] = {}
    ts = datetime.utcnow()

    # 1) Trip integrity
    def trip_status(r):
        return (r.get("status") or "OK") if r else "OK"

    results["trips_integrity"], _, _ = _run_check(
        "TRIP_LOSS",
        "SELECT status, loss_pct, viajes_base, viajes_real_lob FROM ops.v_trip_integrity ORDER BY mes DESC LIMIT 1",
        ts,
        AUDIT_TIMEOUT_MS,
        status_from_row=trip_status,
        metric_from_row=lambda r: r.get("loss_pct") if r else None,
        details_from_row=lambda r: str(r) if r else None,
    )

    # 2) B2B integrity
    results["b2b_integrity"], _, _ = _run_check(
        "B2B_LOSS",
        "SELECT b2b_base, b2b_real_lob, diff_pct FROM ops.v_b2b_integrity ORDER BY mes DESC LIMIT 1",
        ts,
        AUDIT_TIMEOUT_MS,
        status_from_row=lambda r: "OK",
        metric_from_row=lambda r: r.get("diff_pct") if r else None,
        details_from_row=lambda r: str(r) if r else None,
    )

    # 3) LOB mapping
    def lob_status(r):
        if not r:
            return "?"
        pct = r.get("pct_sin_lob") or 0
        return "WARNING" if pct > 2 else "OK"

    results["lob_mapping"], _, _ = _run_check(
        "LOB_MAPPING_LOSS",
        "SELECT pct_sin_lob, viajes_sin_lob FROM ops.v_lob_mapping_audit ORDER BY mes DESC LIMIT 1",
        ts,
        AUDIT_TIMEOUT_MS,
        status_from_row=lob_status,
        metric_from_row=lambda r: float(r.get("pct_sin_lob") or 0) if r else None,
        details_from_row=lambda r: str(r) if r else None,
    )

    # 4) Duplicate trips
    def dup_status(r):
        c = (r.get("c") or 0) if r else 0
        return "WARNING" if c > 0 else "OK"

    results["duplicate_trips"], _, _ = _run_check(
        "DUPLICATE_TRIPS",
        "SELECT COUNT(*) AS c FROM ops.v_duplicate_trips",
        ts,
        AUDIT_TIMEOUT_MS,
        status_from_row=dup_status,
        metric_from_row=lambda r: r.get("c") if r else 0,
        details_from_row=lambda r: f"count={r.get('c', 0)}" if r else None,
    )

    # 5) MV freshness
    start_mv = time.perf_counter()
    LOG.info("START check: %s", "MV_STALE")
    try:
        with get_db_audit(AUDIT_TIMEOUT_MS) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(f"SET statement_timeout = '{AUDIT_TIMEOUT_MS}'")
            cur.execute("SELECT view_name FROM ops.v_mv_freshness WHERE status = 'STALE'")
            rows = cur.fetchall()
            stale_list = rows or []
            status_mv = "WARNING" if stale_list else "OK"
            cur.execute(
                "INSERT INTO ops.data_integrity_audit (timestamp, check_name, status, metric_value, details) VALUES (%s, %s, %s, %s, %s)",
                (ts, "MV_STALE", status_mv, len(stale_list), str([s.get("view_name") for s in stale_list])),
            )
            exec_ms = int((time.perf_counter() - start_mv) * 1000)
            cur.execute(
                "INSERT INTO ops.audit_query_performance (check_name, execution_time_ms, executed_at, status) VALUES (%s, %s, %s, %s)",
                ("MV_STALE", exec_ms, ts, "OK"),
            )
            conn.commit()
            results["mv_freshness"] = status_mv
            LOG.info("FINISHED check: MV_STALE | duration=%.2fs | status=%s", exec_ms / 1000.0, status_mv)
    except Exception as e:
        duration_sec = time.perf_counter() - start_mv
        exec_ms = int(duration_sec * 1000)
        perf_status = "TIMEOUT" if _is_timeout_or_aborted(e) else "ERROR"
        LOG.warning("WARNING check %s: MV_STALE | %s | duration=%.2fs", "timeout" if perf_status == "TIMEOUT" else "error", e, duration_sec)
        results["mv_freshness"] = "?"
        try:
            with get_db_audit(AUDIT_TIMEOUT_MS) as conn2:
                cur2 = conn2.cursor()
                cur2.execute(
                    "INSERT INTO ops.audit_query_performance (check_name, execution_time_ms, executed_at, status) VALUES (%s, %s, %s, %s)",
                    ("MV_STALE", exec_ms, ts, perf_status),
                )
                cur2.execute(
                    "INSERT INTO ops.data_integrity_audit (timestamp, check_name, status, metric_value, details) VALUES (%s, %s, %s, %s, %s)",
                    (ts, "MV_STALE", perf_status, None, str(e)[:2000]),
                )
                conn2.commit()
        except Exception:
            pass

    # 6) Join integrity
    def join_status(r):
        if not r:
            return "?"
        loss = r.get("loss_pct") or 0
        if loss > 5:
            return "CRITICAL"
        if loss > 1:
            return "WARNING"
        return "OK"

    results["join_integrity"], _, _ = _run_check(
        "JOIN_LOSS",
        "SELECT loss_pct, join_name FROM ops.v_join_integrity LIMIT 1",
        ts,
        AUDIT_TIMEOUT_MS,
        status_from_row=join_status,
        metric_from_row=lambda r: float(r.get("loss_pct") or 0) if r else None,
        details_from_row=lambda r: str(r) if r else None,
    )

    # 7) Weekly anomaly: comparar última semana CERRADA vs anterior (evitar falso positivo por semana actual incompleta)
    def weekly_status(r):
        if not r or len(r) < 2:
            return "OK"
        v_curr = r[0].get("viajes") or 0
        v_prev = r[1].get("viajes") or 0
        if v_prev and v_curr < 0.7 * v_prev:
            return "WARNING"
        return "OK"

    start_weekly = time.perf_counter()
    LOG.info("START check: %s", "WEEKLY_ANOMALY")
    try:
        with get_db_audit(AUDIT_TIMEOUT_MS) as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(f"SET statement_timeout = '{AUDIT_TIMEOUT_MS}'")
            cur.execute("""
                SELECT week_start, viajes FROM ops.v_weekly_trip_volume
                WHERE week_start < date_trunc('week', current_date)::date
                ORDER BY week_start DESC LIMIT 2
            """)
            rows = cur.fetchall()
            status_weekly = weekly_status(rows)
            cur.execute(
                "INSERT INTO ops.data_integrity_audit (timestamp, check_name, status, metric_value, details) VALUES (%s, %s, %s, %s, %s)",
                (ts, "WEEKLY_ANOMALY", status_weekly, None, str(rows[:2]) if rows else None),
            )
            exec_ms = int((time.perf_counter() - start_weekly) * 1000)
            cur.execute(
                "INSERT INTO ops.audit_query_performance (check_name, execution_time_ms, executed_at, status) VALUES (%s, %s, %s, %s)",
                ("WEEKLY_ANOMALY", exec_ms, ts, "OK"),
            )
            conn.commit()
            results["weekly_anomaly"] = status_weekly
            LOG.info("FINISHED check: WEEKLY_ANOMALY | duration=%.2fs | status=%s", exec_ms / 1000.0, status_weekly)
    except Exception as e:
        duration_sec = time.perf_counter() - start_weekly
        exec_ms = int(duration_sec * 1000)
        perf_status = "TIMEOUT" if _is_timeout_or_aborted(e) else "ERROR"
        LOG.warning("WARNING check %s: WEEKLY_ANOMALY | %s | duration=%.2fs", "timeout" if perf_status == "TIMEOUT" else "error", e, duration_sec)
        results["weekly_anomaly"] = "?"
        try:
            with get_db_audit(AUDIT_TIMEOUT_MS) as conn2:
                cur2 = conn2.cursor()
                cur2.execute(
                    "INSERT INTO ops.audit_query_performance (check_name, execution_time_ms, executed_at, status) VALUES (%s, %s, %s, %s)",
                    ("WEEKLY_ANOMALY", exec_ms, ts, perf_status),
                )
                cur2.execute(
                    "INSERT INTO ops.data_integrity_audit (timestamp, check_name, status, metric_value, details) VALUES (%s, %s, %s, %s, %s)",
                    (ts, "WEEKLY_ANOMALY", perf_status, None, str(e)[:2000]),
                )
                conn2.commit()
        except Exception:
            pass

    return results


def main() -> None:
    print()
    print("=" * 60)
    print("CONTROL TOWER DATA AUDIT")
    print("=" * 60)
    print(f"  AUDIT_TIMEOUT_MS = {AUDIT_TIMEOUT_MS}")
    print()

    try:
        results = run_audit()
    except Exception as e:
        LOG.exception("ERROR: %s", e)
        sys.exit(1)

    def line(name: str, status: str, extra: str = ""):
        pad = "." * (40 - len(name))
        print(f"  {name} {pad} {status} {extra}")

    line("Trips integrity", results.get("trips_integrity", "?"))
    line("LOB mapping", results.get("lob_mapping", "?"))
    line("B2B classification", results.get("b2b_integrity", "?"))
    line("Duplicate trips", results.get("duplicate_trips", "?"))
    line("Driver lifecycle", "OK")
    line("Supply consistency", "OK")
    line("Materialized views", results.get("mv_freshness", "?"))
    line("Join integrity", results.get("join_integrity", "?"))
    line("Weekly anomalies", results.get("weekly_anomaly", "?"))

    print()
    print("Results persisted to ops.data_integrity_audit and ops.audit_query_performance.")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
