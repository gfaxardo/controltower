"""
backfill_runner.py — Orquestador de backfill para FACT tables desde la API.

Corre en un thread background y expone el estado en tiempo real para polling
desde el frontend. Soporta progreso a nivel de mes Y chunk.
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timezone
from typing import Any

from app.db.connection import get_db_audit
from app.services.business_slice_incremental_load import (
    _materialize_enriched_for_month,
    _drop_enriched_temp,
    _RESOLVE_AND_AGG_DAY_FROM_TEMP,
    _WEEK_ROLLUP_FROM_DAY_FACT,
    apply_business_slice_load_session_settings,
    _effective_chunk_grain,
    month_first_day,
    FACT_DAY,
    FACT_WEEK,
)

import calendar
import logging

logger = logging.getLogger(__name__)

# ── Estado global de progreso ────────────────────────────────────────────────

_lock = threading.Lock()

_state: dict[str, Any] = {
    "running": False,
    "phase": None,           # "materializing_enriched" | "inserting_chunks" | "week_rollup" | "done" | "error" | "cancelled"
    "total_months": 0,
    "done_months": 0,
    "current_month": None,   # "2025-01"
    "current_chunk_idx": 0,
    "total_chunks": 0,
    "current_chunk_label": None,   # "colombia / bogota"
    "day_inserted_total": 0,
    "week_inserted_total": 0,
    "completed_months": [],
    "failed_months": [],
    "started_at": None,
    "ended_at": None,
    "error": None,
    "cancelled": False,
}


def get_progress() -> dict[str, Any]:
    with _lock:
        return dict(_state)


def _upd(**kwargs):
    with _lock:
        _state.update(kwargs)


def is_running() -> bool:
    with _lock:
        return _state["running"]


def cancel():
    with _lock:
        _state["cancelled"] = True


# ── Runner ───────────────────────────────────────────────────────────────────

def _run_backfill(months: list[date], with_week: bool, chunk_grain: str | None):
    _upd(
        running=True, cancelled=False, phase=None,
        total_months=len(months), done_months=0,
        current_month=None, current_chunk_idx=0, total_chunks=0,
        current_chunk_label=None,
        day_inserted_total=0, week_inserted_total=0,
        completed_months=[], failed_months=[],
        started_at=datetime.now(timezone.utc).isoformat(),
        ended_at=None, error=None,
    )

    grain = _effective_chunk_grain(chunk_grain)
    resolve_day_sql = _RESOLVE_AND_AGG_DAY_FROM_TEMP.format(fact_day=FACT_DAY)
    resolve_week_sql = _WEEK_ROLLUP_FROM_DAY_FACT.format(fact_week=FACT_WEEK, fact_day=FACT_DAY)

    try:
        for idx, target_month in enumerate(months):
            with _lock:
                if _state["cancelled"]:
                    _upd(phase="cancelled")
                    return

            month_str = target_month.strftime("%Y-%m")
            _upd(current_month=month_str, phase="materializing_enriched",
                 current_chunk_idx=0, total_chunks=0, current_chunk_label=None)

            last_day = calendar.monthrange(target_month.year, target_month.month)[1]
            end_date = date(target_month.year, target_month.month, last_day)

            try:
                with get_db_audit() as conn:
                    cur = conn.cursor()
                    apply_business_slice_load_session_settings(cur)

                    # 1. Borrar mes existente
                    cur.execute(
                        f"DELETE FROM {FACT_DAY} WHERE trip_date >= %s::date AND trip_date <= %s::date",
                        (target_month, end_date),
                    )
                    conn.commit()

                    # 2. Materializar enriched → temp table
                    mat_rows = _materialize_enriched_for_month(cur, target_month, conn)
                    if mat_rows == 0:
                        _drop_enriched_temp(cur)
                        _upd(done_months=idx + 1)
                        with _lock:
                            _state["completed_months"].append(month_str)
                        continue

                    # 3. Descubrir chunks
                    use_country_only = grain == "country"
                    if use_country_only:
                        cur.execute("SELECT DISTINCT country FROM _bs_enriched_month ORDER BY 1 NULLS FIRST")
                        chunks = [(r[0], None) for r in cur.fetchall()]
                    else:
                        cur.execute("SELECT DISTINCT country, city FROM _bs_enriched_month ORDER BY 1 NULLS FIRST, 2 NULLS FIRST")
                        chunks = list(cur.fetchall())

                    _upd(phase="inserting_chunks", total_chunks=len(chunks), current_chunk_idx=0)

                    day_inserted = 0
                    for ci, chunk in enumerate(chunks):
                        with _lock:
                            if _state["cancelled"]:
                                _drop_enriched_temp(cur)
                                conn.commit()
                                _upd(phase="cancelled")
                                return

                        c_country, c_city = chunk[0], chunk[1] if len(chunk) > 1 else None
                        label = f"{c_country or '—'} / {c_city or '—'}"
                        _upd(current_chunk_idx=ci + 1, current_chunk_label=label)

                        apply_business_slice_load_session_settings(cur)
                        if use_country_only:
                            cur.execute(
                                f"DELETE FROM {FACT_DAY} WHERE trip_date >= %s AND trip_date <= %s AND country IS NOT DISTINCT FROM %s",
                                (target_month, end_date, c_country),
                            )
                        else:
                            cur.execute(
                                f"DELETE FROM {FACT_DAY} WHERE trip_date >= %s AND trip_date <= %s AND country IS NOT DISTINCT FROM %s AND city IS NOT DISTINCT FROM %s",
                                (target_month, end_date, c_country, c_city),
                            )
                        cur.execute(resolve_day_sql, (c_country, c_city))
                        day_inserted += cur.rowcount
                        conn.commit()
                        with _lock:
                            _state["day_inserted_total"] += cur.rowcount

                    _drop_enriched_temp(cur)
                    conn.commit()

                    # 4. Week rollup
                    if with_week:
                        _upd(phase="week_rollup")
                        first_monday = target_month - __import__("datetime").timedelta(days=target_month.weekday())
                        next_monday = end_date + __import__("datetime").timedelta(days=(7 - end_date.weekday()) % 7 or 7)
                        apply_business_slice_load_session_settings(cur)
                        cur.execute(
                            f"DELETE FROM {FACT_WEEK} WHERE week_start >= %s AND week_start < %s",
                            (first_monday, next_monday),
                        )
                        cur.execute(resolve_week_sql, (first_monday, next_monday))
                        week_inserted = cur.rowcount
                        conn.commit()
                        with _lock:
                            _state["week_inserted_total"] += week_inserted

                with _lock:
                    _state["done_months"] = idx + 1
                    _state["completed_months"].append(month_str)

            except Exception as e:
                logger.exception("backfill_runner: error en mes %s: %s", month_str, e)
                with _lock:
                    _state["failed_months"].append(month_str)
                    _state["done_months"] = idx + 1

        _upd(phase="done", running=False, ended_at=datetime.now(timezone.utc).isoformat())

    except Exception as e:
        logger.exception("backfill_runner: error fatal: %s", e)
        _upd(phase="error", running=False, error=str(e), ended_at=datetime.now(timezone.utc).isoformat())


def start_backfill(
    from_date: date,
    to_date: date,
    with_week: bool = True,
    chunk_grain: str | None = None,
) -> bool:
    """Lanza el backfill en background. Retorna False si ya hay uno corriendo."""
    with _lock:
        if _state["running"]:
            return False

    months: list[date] = []
    y, m = from_date.year, from_date.month
    while True:
        d = month_first_day(y, m)
        if d > to_date:
            break
        months.append(d)
        m += 1
        if m > 12:
            m = 1
            y += 1

    if not months:
        return False

    t = threading.Thread(
        target=_run_backfill,
        args=(months, with_week, chunk_grain),
        daemon=True,
    )
    t.start()
    return True
