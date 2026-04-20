"""
Watchdog: lag upstream vs agregado, logs de alerta, auto-recuperación acotada, webhook opcional.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.services.business_slice_real_freshness_service import build_omniview_real_freshness_payload
from app.services.business_slice_real_refresh_job import run_business_slice_real_refresh_job
from app.settings import settings

logger = logging.getLogger(__name__)


def _post_webhook(payload: Dict[str, Any]) -> None:
    url = (getattr(settings, "REAL_FRESHNESS_ALERT_WEBHOOK", None) or "").strip()
    if not url:
        return
    try:
        import httpx

        httpx.post(url, json=payload, timeout=5.0)
    except Exception as e:
        logger.debug("watchdog webhook skip: %s", e)


def run_real_data_watchdog() -> Dict[str, Any]:
    """
    Evalúa freshness; si lag agregado > 2 días loguea error; si upstream fresh y agregado stale/critical, intenta refresh (cooldown en el job).
    """
    out: Dict[str, Any] = {"ok": True, "alerts": [], "recovery_triggered": False}
    try:
        payload = build_omniview_real_freshness_payload()
    except Exception as e:
        logger.exception("REAL_WATCHDOG payload error: %s", e)
        return {"ok": False, "error": str(e)}

    lag = payload.get("lag_days")
    lag_agg = payload.get("lag_days_aggregated")
    status = payload.get("status") or "unknown"

    if isinstance(lag_agg, int) and lag_agg > 2:
        logger.error(
            "REAL DATA STALE: lag_days_aggregated=%s global_status=%s",
            lag_agg,
            status,
        )
        out["alerts"].append("stale_aggregated")
        _post_webhook({"kind": "real_data_stale", "lag_days_aggregated": lag_agg, "status": status})

    if isinstance(lag, int) and lag > 2:
        logger.error("REAL DATA STALE: lag_days=%s status=%s", lag, status)
        out["alerts"].append("lag_combined")
        _post_webhook({"kind": "real_data_stale_lag", "lag_days": lag, "status": status})

    upstream = payload.get("upstream") or {}
    aggregated = payload.get("aggregated") or {}
    up_st = upstream.get("status")
    agg_st = aggregated.get("status")

    if up_st == "fresh" and agg_st in ("stale", "critical"):
        logger.info(
            "REAL_WATCHDOG auto-recovery: upstream=%s aggregated=%s — triggering refresh (cooldown applies)",
            up_st,
            agg_st,
        )
        recovery = run_business_slice_real_refresh_job(force=False)
        out["recovery_triggered"] = not recovery.get("skipped")
        out["recovery_result"] = recovery

    logger.info(
        "REAL_WATCHDOG tick status=%s lag_days=%s upstream=%s aggregated=%s",
        status,
        lag,
        up_st,
        agg_st,
    )
    return out
