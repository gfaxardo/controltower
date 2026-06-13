"""
Watchdog: lag upstream vs agregado, logs de alerta, webhook opcional.
OV2-C.1: Legacy auto-recovery via business_slice_real_refresh_job DISABLED.
Remediation for stale aggregated data: check omniview_cascade_refresh status.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.services.business_slice_real_freshness_service import build_omniview_real_freshness_payload
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
    """Evalua freshness; si lag agregado > 2 dias loguea error.
    OV2-C.1: Legacy auto-recovery DISABLED. Stale aggregated data now triggers alert, not auto-refresh.
    Remediation: check omniview_cascade_refresh scheduler status."""
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
        logger.warning(
            "REAL_WATCHDOG upstream=%s aggregated=%s — CASCADE may need investigation. "
            "Legacy auto-recovery DISABLED per OV2-C.1 ownership hardening. "
            "Do NOT run business_slice_real_refresh_job. Check omniview_cascade_refresh status.",
            up_st,
            agg_st,
        )
        out["alerts"].append("aggregated_stale_despite_fresh_upstream")
        out["recovery_triggered"] = False

    logger.info(
        "REAL_WATCHDOG tick status=%s lag_days=%s upstream=%s aggregated=%s",
        status,
        lag,
        up_st,
        agg_st,
    )
    return out
