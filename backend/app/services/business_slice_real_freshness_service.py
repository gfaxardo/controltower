"""
Freshness de la capa REAL que alimenta Omniview Matrix (business slice facts).

Monthly: ops.real_business_slice_month_fact
Weekly:  ops.real_business_slice_week_fact
Daily:   ops.real_business_slice_day_fact

Incluye chequeo upstream (trips base) y payload unificado para /real-freshness.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from app.omniview_real_scheduler_info import (
    get_next_omniview_refresh_run_iso,
    get_next_omniview_watchdog_run_iso,
)
from app.services.business_slice_service import FACT_DAILY, FACT_MONTHLY, FACT_WEEKLY
from app.services.upstream_real_status_service import get_upstream_real_status
from app.settings import settings

logger = logging.getLogger(__name__)

# Peor al final: fresh < stale < unknown < critical < empty
_STATUS_RANK = {
    "fresh": 0,
    "stale": 1,
    "unknown": 2,
    "critical": 3,
    "empty": 4,
}


def worst_status(*statuses: str) -> str:
    return max(statuses, key=lambda s: _STATUS_RANK.get(s, 3))


def _d(v: Any) -> Optional[date]:
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


def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _ts(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _aggregated_status_from_lag(lag: Optional[int], stale_days: int, crit_days: int) -> str:
    if lag is None:
        return "empty"
    if lag >= crit_days:
        return "critical"
    if lag >= stale_days:
        return "stale"
    return "fresh"


def _collect_aggregated_slice_metrics(cur, today: date, stale_days: int, crit_days: int) -> Dict[str, Any]:
    """Métricas de facts + status solo agregado (day_fact)."""
    out: Dict[str, Any] = {
        "day_fact": {},
        "week_fact": {},
        "month_fact": {},
        "by_country": [],
        "status": "unknown",
        "lag_days_vs_today": None,
    }

    cur.execute(
        f"SELECT MAX(trip_date), MAX(loaded_at), MAX(refreshed_at) FROM {FACT_DAILY}"
    )
    r = cur.fetchone()
    max_day = _d(r[0]) if r else None
    out["day_fact"] = {
        "source_name": FACT_DAILY,
        "max_trip_date": _iso(max_day),
        "max_loaded_at": _ts(r[1]) if r else None,
        "max_refreshed_at": _ts(r[2]) if r else None,
    }

    cur.execute(
        f"SELECT MAX(week_start), MAX(loaded_at), MAX(refreshed_at) FROM {FACT_WEEKLY}"
    )
    rw = cur.fetchone()
    max_ws = _d(rw[0]) if rw else None
    out["week_fact"] = {
        "source_name": FACT_WEEKLY,
        "max_week_start": _iso(max_ws),
        "max_loaded_at": _ts(rw[1]) if rw else None,
        "max_refreshed_at": _ts(rw[2]) if rw else None,
        "note": "week_start es lunes ISO; la semana en curso puede existir con datos parciales.",
    }

    cur.execute(
        f"SELECT MAX(month), MAX(loaded_at), MAX(refreshed_at) FROM {FACT_MONTHLY}"
    )
    rm = cur.fetchone()
    max_m = _d(rm[0]) if rm else None
    out["month_fact"] = {
        "source_name": FACT_MONTHLY,
        "max_month": _iso(max_m),
        "max_loaded_at": _ts(rm[1]) if rm else None,
        "max_refreshed_at": _ts(rm[2]) if rm else None,
    }

    cur.execute(
        f"""
        SELECT lower(trim(country::text)) AS c,
               MAX(trip_date) AS mx,
               MAX(loaded_at) AS ml
        FROM {FACT_DAILY}
        WHERE country IS NOT NULL AND trim(country::text) <> ''
        GROUP BY 1
        ORDER BY 1
        """
    )
    by_country: List[Dict[str, Any]] = []
    for row in cur.fetchall():
        co, mx, ml = row[0], _d(row[1]), row[2]
        lag_c = (today - mx).days if mx else None
        if lag_c is None:
            st = "unknown"
        elif lag_c >= crit_days:
            st = "critical"
        elif lag_c >= stale_days:
            st = "stale"
        else:
            st = "fresh"
        by_country.append({
            "country_key": co,
            "max_trip_date": _iso(mx),
            "max_loaded_at": _ts(ml),
            "lag_days_vs_today": lag_c,
            "status": st,
        })
    out["by_country"] = by_country

    if max_day is None:
        out["status"] = "empty"
        out["lag_days_vs_today"] = None
    else:
        lag = (today - max_day).days
        out["lag_days_vs_today"] = lag
        out["status"] = _aggregated_status_from_lag(lag, stale_days, crit_days)

    return out


def build_omniview_real_freshness_payload(conn=None) -> Dict[str, Any]:
    """
    Payload completo: upstream + aggregated + status peor + lag combinado + meta scheduler.

    Si conn es None, abre get_db() y cierra al salir.
    """
    today = date.today()
    stale_days = int(getattr(settings, "OMNIVIEW_REAL_FRESH_LAG_STALE_DAYS", 1) or 1)
    crit_days = int(getattr(settings, "OMNIVIEW_REAL_FRESH_LAG_CRITICAL_DAYS", 2) or 2)

    def _build_with_cursor(cur, db_conn) -> Dict[str, Any]:
        upstream = get_upstream_real_status(db_conn)

        aggregated = _collect_aggregated_slice_metrics(cur, today, stale_days, crit_days)

        up_st = upstream.get("status") or "unknown"
        agg_st = aggregated.get("status") or "unknown"
        global_status = worst_status(up_st, agg_st)

        lag_up = upstream.get("lag_days_vs_today")
        lag_agg = aggregated.get("lag_days_vs_today")
        lag_parts = [x for x in (lag_up, lag_agg) if isinstance(x, int)]
        lag_combined = max(lag_parts) if lag_parts else None

        last_loaded = (aggregated.get("day_fact") or {}).get("max_loaded_at")

        payload: Dict[str, Any] = {
            "as_of_server_date": today.isoformat(),
            "thresholds": {
                "stale_lag_days": stale_days,
                "critical_lag_days": crit_days,
                "upstream_lag_fresh_max_days": 1,
                "upstream_lag_stale_day": 2,
                "upstream_lag_critical_min_days": 3,
            },
            "upstream": upstream,
            "aggregated": {
                "day_fact": aggregated["day_fact"],
                "week_fact": aggregated["week_fact"],
                "month_fact": aggregated["month_fact"],
                "by_country": aggregated["by_country"],
                "status": agg_st,
                "lag_days_vs_today": lag_agg,
            },
            "status": global_status,
            "lag_days": lag_combined,
            "lag_days_upstream": lag_up,
            "lag_days_aggregated": lag_agg,
            "last_refresh_at": last_loaded,
            "next_scheduled_run": get_next_omniview_refresh_run_iso(),
            "next_watchdog_run": get_next_omniview_watchdog_run_iso(),
            "overall_status": global_status,
            "lag_days_vs_today": lag_agg,
            "day_fact": aggregated["day_fact"],
            "week_fact": aggregated["week_fact"],
            "month_fact": aggregated["month_fact"],
            "by_country": aggregated["by_country"],
            "primary_signal_source": FACT_DAILY,
        }
        return payload

    if conn is not None:
        cur = conn.cursor()
        try:
            return _build_with_cursor(cur, conn)
        finally:
            cur.close()

    try:
        with get_db() as conn:
            cur = conn.cursor()
            try:
                return _build_with_cursor(cur, conn)
            finally:
                cur.close()
    except Exception as e:
        logger.warning("build_omniview_real_freshness_payload: %s", e, exc_info=True)
        return {
            "as_of_server_date": today.isoformat(),
            "upstream": {"status": "unknown", "error": str(e)},
            "aggregated": {},
            "status": "unknown",
            "overall_status": "unknown",
            "error": str(e),
        }


def get_omniview_business_slice_real_freshness() -> Dict[str, Any]:
    """
    Alias del payload completo (GET /ops/business-slice/real-freshness, CLI check_real_freshness).
    Mantiene claves en raíz compatibles con clientes existentes.
    """
    return build_omniview_real_freshness_payload()
