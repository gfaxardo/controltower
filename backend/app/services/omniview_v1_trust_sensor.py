"""
OMNI-V1 HARDENING — Trust Sensor specific to Omniview V1 (Evolution).

Detects operational risks in the V1 serving pipeline without breaking V2.
Does NOT block UI. Returns structured WARN/FAIL with remediation hints.

Signals checked:
- DAY_FACT_STALE / WEEK_FACT_STALE / MONTH_FACT_STALE
- SNAPSHOT_STALE
- WATERFALL_BROKEN
- MULTIPLE_WRITERS_DETECTED
- LEGACY_ROUTE_ACTIVE
- DRIVER_AGGREGATION_AMBIGUOUS
- RUNTIME_IDENTITY_MISSING
- PYCACHE_RISK
"""
from __future__ import annotations

import logging
import os
import pathlib
import subprocess
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.db.connection import get_db
from app.settings import settings

logger = logging.getLogger(__name__)

_V1_TRUST_SENSOR_CACHE_TTL_SEC = 60.0
_v1_trust_cache: tuple[float, dict[str, Any]] | None = None
_v1_trust_cache_lock = threading.Lock()

# ────────────────────────────────────────────
# helpers
# ────────────────────────────────────────────


def _d(v: Any) -> date | None:
    if v is None:
        return None
    if isinstance(v, date) and not isinstance(v, datetime):
        return v
    if hasattr(v, "date"):
        return v.date()
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _iso(d_val: date | None) -> str | None:
    return d_val.isoformat() if d_val else None


def _q(conn, sql: str, params: tuple = ()) -> Any:
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchone()
    finally:
        cur.close()


def _q_a(conn, sql: str, params: tuple = ()) -> list[tuple]:
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def _git_hash() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return None


def _pycache_risk() -> dict[str, Any]:
    backend_dir = os.path.join(os.path.dirname(__file__), "..")
    stale_count = 0
    total_count = 0
    samples: list[str] = []
    for root, dirs, files in os.walk(backend_dir):
        if "__pycache__" in root:
            for f in files:
                if not f.endswith(".pyc"):
                    continue
                total_count += 1
                py_path = os.path.join(root, f)
                pyc_mtime = os.path.getmtime(py_path)
                py_file = f.split(".cpython-")[0] + ".py"
                src_path = os.path.join(os.path.dirname(root), py_file)
                if os.path.exists(src_path):
                    src_mtime = os.path.getmtime(src_path)
                    if pyc_mtime < src_mtime:
                        stale_count += 1
                        if len(samples) < 5:
                            samples.append(py_path)
    return {
        "total_pyc": total_count,
        "stale_count": stale_count,
        "risk": stale_count > 0,
        "sample_stale": samples[:5],
    }


def _runtime_identity_missing() -> dict[str, Any]:
    try:
        import app.services.omniview_v1_runtime_identity as rid
        return {
            "missing": False,
            "endpoint": "GET /ops/v1-runtime-identity",
        }
    except ImportError:
        return {"missing": True, "detail": "Runtime identity module not loaded"}


# ────────────────────────────────────────────
# signal checks
# ────────────────────────────────────────────


def _check_day_fact_stale(conn) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    row = _q(conn, "SELECT MAX(trip_date) AS max_date FROM ops.real_business_slice_day_fact")
    max_date = _d(row[0]) if row else None
    today = date.today()
    expected = today - timedelta(days=1)

    if not max_date:
        return [{
            "code": "DAY_FACT_STALE",
            "severity": "FAIL",
            "affected_asset": "ops.real_business_slice_day_fact",
            "observed_value": "NULL (empty table)",
            "expected_value": _iso(expected),
            "remediation": "Ejecutar rebuild_day_from_bridge.py o refresh_omniview_real_slice_incremental.py",
            "blocking": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

    lag = (today - max_date).days
    status = "OK"
    severity = "OK"
    blocking = False

    if lag > 1:
        severity = "WARN"
        status = "WARN"
        blocking = False
    if lag > 3:
        severity = "FAIL"
        status = "FAIL"
        blocking = True

    results.append({
        "code": "DAY_FACT_STALE",
        "severity": severity,
        "affected_asset": "ops.real_business_slice_day_fact",
        "observed_value": _iso(max_date),
        "expected_value": _iso(expected),
        "lag_days": max(lag, 0),
        "remediation": "Ejecutar rebuild_day_from_bridge.py o refresh_omniview_real_slice_incremental.py",
        "blocking": blocking,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return results


def _check_week_fact_stale(conn) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    row = _q(conn, "SELECT MAX(week_start) AS max_week FROM ops.real_business_slice_week_fact")
    max_week = _d(row[0]) if row else None
    today = date.today()
    # expected: last closed ISO week (Monday of previous week)
    today_iso = today.isocalendar()
    current_week_monday = today - timedelta(days=today.weekday())
    expected = current_week_monday - timedelta(weeks=1)

    if not max_week:
        return [{
            "code": "WEEK_FACT_STALE",
            "severity": "FAIL",
            "affected_asset": "ops.real_business_slice_week_fact",
            "observed_value": "NULL (empty table)",
            "expected_value": _iso(expected),
            "remediation": "Ejecutar rebuild_week_from_day_and_bridge.py",
            "blocking": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

    lag_days = (today - max_week).days
    severity = "OK"
    blocking = False
    if lag_days > 7:
        severity = "WARN"
    if lag_days > 14:
        severity = "FAIL"
        blocking = True

    results.append({
        "code": "WEEK_FACT_STALE",
        "severity": severity,
        "affected_asset": "ops.real_business_slice_week_fact",
        "observed_value": _iso(max_week),
        "expected_value": _iso(expected),
        "lag_days": max(lag_days, 0),
        "remediation": "Ejecutar rebuild_week_from_day_and_bridge.py",
        "blocking": blocking,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return results


def _check_month_fact_stale(conn) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    row = _q(conn, "SELECT MAX(month) AS max_month FROM ops.real_business_slice_month_fact")
    max_month = _d(row[0]) if row else None
    today = date.today()
    expected = date(today.year, today.month, 1) - timedelta(days=1)
    expected = date(expected.year, expected.month, 1)

    if not max_month:
        return [{
            "code": "MONTH_FACT_STALE",
            "severity": "FAIL",
            "affected_asset": "ops.real_business_slice_month_fact",
            "observed_value": "NULL (empty table)",
            "expected_value": _iso(expected),
            "remediation": "Ejecutar rebuild_month_from_day_and_bridge.py",
            "blocking": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

    lag_days = (today - max_month).days
    severity = "OK"
    blocking = False
    if lag_days > 31:
        severity = "WARN"
    if lag_days > 62:
        severity = "FAIL"
        blocking = True

    results.append({
        "code": "MONTH_FACT_STALE",
        "severity": severity,
        "affected_asset": "ops.real_business_slice_month_fact",
        "observed_value": _iso(max_month),
        "expected_value": _iso(expected),
        "lag_days": max(lag_days, 0),
        "remediation": "Ejecutar rebuild_month_from_day_and_bridge.py",
        "blocking": blocking,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return results


def _check_snapshot_stale(conn) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    # check monthly snapshot vs month_fact freshness
    row = _q(conn, """
        SELECT MAX(created_at) AS max_snap,
               (SELECT MAX(month) FROM ops.real_business_slice_month_fact) AS max_fact_month
        FROM ops.real_business_slice_month_snapshot
        WHERE snapshot_status = 'active'
    """)
    max_snap = row[0] if row else None
    max_fact = row[1] if row and len(row) > 1 else None
    # max_fact is already a date from the query

    count_row = _q(conn, """
        SELECT COUNT(*) AS cnt FROM ops.real_business_slice_month_snapshot
        WHERE snapshot_status = 'active'
    """)
    snap_count = int(count_row[0]) if count_row else 0

    if snap_count == 0:
        return [{
            "code": "SNAPSHOT_STALE",
            "severity": "WARN",
            "affected_asset": "ops.real_business_slice_month_snapshot",
            "observed_value": "0 active snapshots",
            "expected_value": ">=1 active snapshot for last closed month",
            "remediation": "Ejecutar period_closure_service.close_period() o verificar cierre de periodos",
            "blocking": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

    # Check if any active snapshot is for a period later than the max fact month
    row2 = _q(conn, """
        SELECT MAX(period_start) FROM ops.real_business_slice_month_snapshot
        WHERE snapshot_status = 'active'
    """)
    max_snap_period = _d(row2[0]) if row2 else None

    if max_snap_period and hasattr(max_fact, 'isoformat'):
        if max_snap_period > max_fact:
            results.append({
                "code": "SNAPSHOT_AHEAD_OF_FACT",
                "severity": "FAIL",
                "affected_asset": "ops.real_business_slice_month_snapshot",
                "observed_value": f"snapshot max={_iso(max_snap_period)} > fact max={_iso(max_fact)}",
                "expected_value": "snapshot <= fact max",
                "remediation": "Auditar generacion de snapshots: no deben adelantarse al fact base",
                "blocking": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    return results


def _check_multiple_writers() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    writers = {
        "day_fact": [
            "business_slice_incremental_load._RESOLVE_AND_AGG_DAY_FROM_TEMP",
            "rebuild_day_from_bridge.py",
            "refresh_omniview_real_slice_incremental.py",
            "refresh_business_slice_mvs.py (legacy)",
        ],
        "week_fact": [
            "business_slice_incremental_load._RESOLVE_AND_AGG_WEEK_FROM_TEMP",
            "rebuild_week_from_day_and_bridge.py",
            "rebuild_week_fact_from_day_fact.py (BROKEN for drivers)",
            "refresh_business_slice_mvs.py (legacy)",
        ],
        "month_fact": [
            "business_slice_incremental_load._RESOLVE_AND_AGG_FROM_TEMP",
            "rebuild_month_from_day_and_bridge.py",
            "refresh_business_slice_mvs.py (legacy)",
        ],
    }

    for fact, paths in writers.items():
        if len(paths) > 1:
            results.append({
                "code": "MULTIPLE_WRITERS_DETECTED",
                "severity": "WARN",
                "affected_asset": f"ops.real_business_slice_{fact}",
                "observed_value": f"{len(paths)} write paths: {', '.join(paths)}",
                "expected_value": "1 canonical writer",
                "remediation": "Estandarizar un solo writer canónico (bridge cascade). Deprecar legacy paths documentados: refresh_business_slice_mvs.py, rebuild_week_fact_from_day_fact.py.",
                "blocking": False,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    return results


def _check_legacy_routes() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    legacy_routes = [
        ("/core/summary/monthly", "Orphan: MonthlyView.jsx unused in App.jsx"),
        ("/ops/real/monthly", "Consumed by MonthlySplitView.jsx, reads legacy MV"),
        ("/ops/real-lob/monthly (v1)", "Consumed by RealLOBView.jsx alongside v2"),
        ("/ops/real-lob/weekly (v1)", "Consumed by RealLOBView.jsx alongside v2"),
    ]

    for path, note in legacy_routes:
        results.append({
            "code": "LEGACY_ROUTE_ACTIVE",
            "severity": "WARN",
            "affected_asset": path,
            "observed_value": f"Active consumer exists: {note}",
            "expected_value": "Migrated to canonical or deprecated",
            "remediation": f"Migrar consumidor de {path} a canonical, luego marcar deprecated",
            "blocking": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    return results


def _check_driver_aggregation() -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    # Primary paths are EXACT: COUNT(DISTINCT driver_id) at correct grain
    # But broken path exists: rebuild_week_fact_from_day_fact.py uses SUM(daily distincts) = BROKEN
    results.append({
        "code": "DRIVER_AGGREGATION_AMBIGUOUS",
        "severity": "WARN",
        "affected_asset": "week_fact active_drivers (multiple writer paths)",
        "observed_value": "2 exact paths (inline DISTINCT, bridge) + 1 BROKEN path (rebuild_week_fact_from_day_fact.py: SUM of daily distincts) not blocked",
        "expected_value": "Single canonical path with BROKEN paths blocked by guard",
        "remediation": "Agregar safety guard a rebuild_week_fact_from_day_fact.py (como refresh_omniview_real_slice.py). Semanal debe usar COUNT(DISTINCT via bridge).",
        "blocking": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return results


def _check_waterfall_broken(conn) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    # Check: day_max >= week_max_covered >= month_max_covered
    day_row = _q(conn, "SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact")
    week_row = _q(conn, """
        SELECT MAX(week_start) FROM ops.real_business_slice_week_fact
        WHERE week_start <= (SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact)
    """)
    month_row = _q(conn, """
        SELECT MAX(month) FROM ops.real_business_slice_month_fact
        WHERE month <= (SELECT MAX(trip_date) FROM ops.real_business_slice_day_fact)
    """)

    day_max = _d(day_row[0]) if day_row else None
    week_max = _d(week_row[0]) if week_row else None
    month_max = _d(month_row[0]) if month_row else None

    issues = []

    if day_max and week_max:
        expected_week = day_max - timedelta(days=day_max.weekday())
        if week_max < expected_week - timedelta(weeks=1):
            issues.append(f"week_max ({_iso(week_max)}) behind day_max ({_iso(day_max)}) by >1 week")

    if week_max and month_max:
        expected_month = date(week_max.year, week_max.month, 1)
        if month_max < expected_month - timedelta(days=31):
            issues.append(f"month_max ({_iso(month_max)}) behind week_max ({_iso(week_max)})")

    if issues:
        return [{
            "code": "WATERFALL_BROKEN",
            "severity": "WARN" if len(issues) <= 1 else "FAIL",
            "affected_asset": "day_fact -> week_fact -> month_fact cascade",
            "observed_value": "; ".join(issues),
            "expected_value": "day >= week >= month within expected freshness windows",
            "remediation": "Ejecutar run_ov2_refresh_cascade.py para alinear todos los grains",
            "blocking": len(issues) > 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]

    return []


def _check_pycache_risk() -> list[dict[str, Any]]:
    pr = _pycache_risk()
    if pr["risk"]:
        return [{
            "code": "PYCACHE_RISK",
            "severity": "WARN",
            "affected_asset": "Python __pycache__/",
            "observed_value": f"{pr['stale_count']}/{pr['total_pyc']} stale .pyc files",
            "expected_value": "0 stale .pyc files",
            "remediation": "Ejecutar find . -name '*.pyc' -delete y reiniciar backend",
            "blocking": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }]
    return []


def _check_runtime_identity() -> list[dict[str, Any]]:
    gh = _git_hash()
    if gh:
        return []

    return [{
        "code": "RUNTIME_IDENTITY_MISSING",
        "severity": "WARN",
        "affected_asset": "Runtime identity (git hash, build_time, etc.)",
        "observed_value": "git hash not retrievable",
        "expected_value": "GET /health returns git_hash, build_time, app_start_time",
        "remediation": "Verificar acceso a git desde el backend y que health endpoint incluya runtime identity",
        "blocking": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }]


# ────────────────────────────────────────────
# orchestrator
# ────────────────────────────────────────────


def run_omniview_v1_trust_sensor(force: bool = False) -> dict[str, Any]:
    global _v1_trust_cache

    if not force and _v1_trust_cache:
        ts, cached = _v1_trust_cache
        if time.time() - ts < _V1_TRUST_SENSOR_CACHE_TTL_SEC:
            return cached

    with _v1_trust_cache_lock:
        try:
            with get_db() as conn:
                all_checks: list[dict[str, Any]] = []

                # freshness
                all_checks.extend(_check_day_fact_stale(conn))
                all_checks.extend(_check_week_fact_stale(conn))
                all_checks.extend(_check_month_fact_stale(conn))

                # snapshot
                all_checks.extend(_check_snapshot_stale(conn))

                # waterfall
                all_checks.extend(_check_waterfall_broken(conn))

                # static checks (no DB needed)
                all_checks.extend(_check_multiple_writers())
                all_checks.extend(_check_legacy_routes())
                all_checks.extend(_check_driver_aggregation())
                all_checks.extend(_check_pycache_risk())
                all_checks.extend(_check_runtime_identity())

                fail_count = sum(1 for c in all_checks if c["severity"] == "FAIL")
                warn_count = sum(1 for c in all_checks if c["severity"] == "WARN")
                blocked = any(c["blocking"] for c in all_checks if c["severity"] == "FAIL")

                if blocked or fail_count > 0:
                    status = "FAIL"
                elif warn_count > 0:
                    status = "WARN"
                else:
                    status = "OK"

                payload = {
                    "status": status,
                    "service": "Omniview V1 Trust Sensor",
                    "summary": {
                        "ok_count": sum(1 for c in all_checks if c["severity"] == "OK"),
                        "warn_count": warn_count,
                        "fail_count": fail_count,
                        "blocked": blocked,
                    },
                    "checks": all_checks,
                }

                _v1_trust_cache = (time.time(), payload)
                return payload
        except Exception as e:
            return {
                "status": "FAIL",
                "error": f"DB connection failed: {e}",
                "checks": [],
            }
