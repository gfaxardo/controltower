"""
LG-SERV-2A — Serving Operability Engine

Single unified service for system operability.
Outputs:
  - system_status: HEALTHY / WARNING / DEGRADED / CRITICAL
  - component_status: per asset
  - dependency_graph health
  - root cause when degraded

Aggregates from:
  - serving_freshness_audit (freshness fact)
  - yego_lima_refresh_governance (pipeline + facts)
  - yego_lima_freshness_chain (lineage propagation)
  - yego_lima_v2_pipeline (9-step DAG)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from app.db.connection import get_db

logger = logging.getLogger(__name__)

STATUS_HEALTHY = "HEALTHY"
STATUS_WARNING = "WARNING"
STATUS_DEGRADED = "DEGRADED"
STATUS_CRITICAL = "CRITICAL"

_LIMA_TZ = timezone(timedelta(hours=-5))

# ── LG-REL-1A: In-memory cache to reduce health endpoint latency ──
_cache: Dict[str, Any] = {}
_CACHE_TTL_SECONDS = 60


def _cached(key: str, builder, ttl: int = _CACHE_TTL_SECONDS):
    now = _now()
    entry = _cache.get(key)
    if entry and (now - entry["ts"]).total_seconds() < ttl:
        return entry["data"]
    data = builder()
    _cache[key] = {"ts": now, "data": data}
    return data

DEPENDENCY_GRAPH: Dict[str, List[str]] = {
    "activity_daily": ["lifecycle_daily"],
    "lifecycle_daily": ["taxonomy_v2", "program_v2"],
    "taxonomy_v2": ["movement_fact"],
    "program_v2": ["movement_fact", "program_assignment"],
    "program_assignment": ["serving_driver_explorer"],
    "driver_state_snapshot": ["program_assignment"],
    "movement_fact": ["observability_fact"],
    "activity_weekly": [],
    "activity_monthly": [],
    "observability_fact": ["RNA_serving"],
    "RNA_serving": [],
    "effectiveness_fact": [],
    "serving_driver_explorer": [],
}


def _now():
    return datetime.now(timezone.utc)


def get_operability_status() -> Dict[str, Any]:
    return _cached("operability", _build_operability_status)


def _build_operability_status() -> Dict[str, Any]:
    now = _now()

    components: List[Dict[str, Any]] = []
    dependency_issues: List[Dict[str, Any]] = []
    root_causes: List[str] = []

    v2_status = {}
    try:
        from app.services.yego_lima_v2_daily_pipeline_service import (
            get_v2_pipeline_status,
        )
        v2_status = get_v2_pipeline_status()
    except Exception as e:
        logger.warning("Cannot read V2 pipeline status: %s", e)

    component_status = {}
    for asset_name in [
        "activity_daily", "activity_weekly", "activity_monthly",
        "lifecycle_daily", "taxonomy_v2", "program_v2",
        "movement_fact", "observability_fact", "effectiveness_fact",
    ]:
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT freshness_status, last_refresh_at, max_data_date, rows_count "
                    "FROM growth.yego_lima_v2_freshness_registry WHERE component = %(c)s",
                    {"c": asset_name},
                )
                row = cur.fetchone()
                if row:
                    fs_status = row[0] or "UNKNOWN"
                    last_refresh = row[1]
                    max_date = row[2]
                    rows = row[3] or 0

                    age_hours = None
                    if last_refresh:
                        age_hours = round((now - last_refresh).total_seconds() / 3600, 2)

                    mapped = _map_freshness_to_operability(fs_status, age_hours)
                    component_status[asset_name] = {
                        "status": mapped,
                        "freshness": fs_status,
                        "last_refresh_at": last_refresh.isoformat() if last_refresh else None,
                        "max_data_date": str(max_date) if max_date else None,
                        "age_hours": age_hours,
                        "rows_count": rows,
                    }
                else:
                    component_status[asset_name] = {
                        "status": STATUS_CRITICAL,
                        "freshness": "MISSING",
                        "last_refresh_at": None,
                        "max_data_date": None,
                        "age_hours": None,
                        "rows_count": 0,
                    }
        except Exception as e:
            logger.warning("Cannot read V2 freshness for %s: %s", asset_name, e)
            component_status[asset_name] = {
                "status": STATUS_CRITICAL,
                "freshness": "ERROR",
                "error": str(e)[:200],
            }

    try:
        from app.services.yego_lima_refresh_governance_service import (
            get_governance_status,
        )
        gov = get_governance_status()

        for fact in gov.get("facts", []):
            name = f"serving_fact_{fact['fact_type']}"
            fs = fact.get("status", "UNKNOWN")
            mapped = STATUS_HEALTHY if fs == "OK" else STATUS_DEGRADED if fs == "STALE" else STATUS_CRITICAL
            component_status[name] = {
                "status": mapped,
                "freshness": fs,
                "generated_at": fact.get("generated_at"),
                "age_minutes": fact.get("age_minutes"),
            }

        for sc in gov.get("stale_components", []):
            if sc["component"] not in component_status:
                component_status[sc["component"]] = {
                    "status": STATUS_DEGRADED,
                    "freshness": sc.get("status", "STALE"),
                    "max_data_date": sc.get("max_data_date"),
                    "latency_minutes": sc.get("latency_minutes"),
                }

        operability = gov.get("operability", "UNKNOWN")
        mapped_gov = _map_gov_operability(operability)
    except Exception as e:
        logger.warning("Cannot read governance status: %s", e)
        mapped_gov = STATUS_CRITICAL

    for asset_name, deps in DEPENDENCY_GRAPH.items():
        comp = component_status.get(asset_name, {"status": STATUS_CRITICAL, "freshness": "UNKNOWN"})
        comp_status = comp.get("status", STATUS_CRITICAL)

        comp_entry = {
            "asset_name": asset_name,
            "status": comp_status,
            "freshness": comp.get("freshness", "UNKNOWN"),
            "last_refreshed_at": comp.get("last_refresh_at"),
            "age_hours": comp.get("age_hours"),
            "age_minutes": comp.get("age_minutes"),
            "rows_count": comp.get("rows_count"),
            "dependencies": deps,
        }
        components.append(comp_entry)

        if comp_status in (STATUS_CRITICAL, STATUS_DEGRADED):
            for dep in deps:
                dep_comp = component_status.get(dep, {})
                dep_status = dep_comp.get("status", STATUS_HEALTHY)
                if dep_status in (STATUS_CRITICAL, STATUS_DEGRADED):
                    dependency_issues.append({
                        "asset": asset_name,
                        "depends_on": dep,
                        "asset_status": comp_status,
                        "dependency_status": dep_status,
                        "issue": f"{asset_name} DEPENDS on {dep} which is {dep_status}",
                    })

    for issue in dependency_issues:
        if issue["dependency_status"] == STATUS_CRITICAL:
            root_causes.append(
                f"ROOT: {issue['depends_on']} is {issue['dependency_status']} "
                f"→ causing {issue['asset']} degradation"
            )

    critical_count = sum(1 for c in components if c["status"] == STATUS_CRITICAL)
    degraded_count = sum(1 for c in components if c["status"] == STATUS_DEGRADED)
    warning_count = sum(1 for c in components if c["status"] == STATUS_WARNING)
    healthy_count = sum(1 for c in components if c["status"] == STATUS_HEALTHY)

    if critical_count > 0:
        system_status = STATUS_CRITICAL
    elif degraded_count > 0:
        system_status = STATUS_DEGRADED
    elif warning_count > 1:
        system_status = STATUS_WARNING
    elif mapped_gov == STATUS_CRITICAL:
        system_status = STATUS_DEGRADED
    else:
        system_status = STATUS_HEALTHY

    stale_assets = [
        c["asset_name"] for c in components if c["status"] in (STATUS_DEGRADED, STATUS_CRITICAL)
    ]
    broken_assets = [
        c["asset_name"] for c in components if c["status"] == STATUS_CRITICAL
    ]

    return {
        "system_status": system_status,
        "checked_at": now.isoformat(),
        "components": components,
        "summary": {
            "healthy": healthy_count,
            "warning": warning_count,
            "degraded": degraded_count,
            "critical": critical_count,
            "total": len(components),
        },
        "stale_assets": stale_assets,
        "broken_assets": broken_assets,
        "dependency_issues": dependency_issues,
        "root_causes": root_causes,
        "governance_operability": {
            "from_refresh_governance": mapped_gov,
            "v2_pipeline_last_target_date": v2_status.get("last_target_date"),
            "v2_pipeline_operability": v2_status.get("operability"),
        },
        "remediation": _build_remediation(system_status, damaged_assets=broken_assets + stale_assets),
    }


def get_health() -> Dict[str, Any]:
    operability = get_operability_status()

    return {
        "system_status": operability["system_status"],
        "checked_at": operability["checked_at"],
        "operability": operability["system_status"],
        "components_healthy": operability["summary"]["healthy"],
        "components_degraded": operability["summary"]["degraded"],
        "components_critical": operability["summary"]["critical"],
        "stale_assets": operability["stale_assets"],
        "broken_assets": operability["broken_assets"],
        "root_causes": operability["root_causes"],
        "remediation": operability["remediation"],
    }


def get_freshness() -> Dict[str, Any]:
    return _cached("freshness", _build_freshness)


def _build_freshness() -> Dict[str, Any]:
    try:
        from app.services.serving_freshness_audit_service import (
            get_freshness_audit_status,
        )
        return get_freshness_audit_status()
    except Exception as e:
        return {
            "overall_status": STATUS_CRITICAL,
            "error": str(e),
            "assets": [],
        }


def _map_freshness_to_operability(freshness: str, age_hours: Optional[float]) -> str:
    if freshness == "FRESH":
        return STATUS_HEALTHY
    elif freshness == "WARNING":
        return STATUS_WARNING if (age_hours is None or age_hours <= 48) else STATUS_DEGRADED
    elif freshness == "STALE":
        return STATUS_DEGRADED if (age_hours is None or age_hours <= 72) else STATUS_CRITICAL
    elif freshness in ("BROKEN", "MISSING"):
        return STATUS_CRITICAL
    return STATUS_CRITICAL


def _map_gov_operability(gov_op: str) -> str:
    if gov_op in ("OPERABLE",):
        return STATUS_HEALTHY
    elif gov_op in ("OPERABLE_STALE_WARNING", "OPERABLE_WARNING"):
        return STATUS_WARNING
    elif gov_op in ("NOT_OPERABLE_MISSING_FACTS",):
        return STATUS_DEGRADED
    elif gov_op in ("NOT_OPERABLE_STALE",):
        return STATUS_CRITICAL
    return STATUS_CRITICAL


def _build_remediation(
    system_status: str,
    damaged_assets: List[str] = None,
) -> Optional[str]:
    if system_status == STATUS_HEALTHY:
        return None

    if system_status == STATUS_CRITICAL:
        assets_str = ", ".join(damaged_assets[:5]) if damaged_assets else "unknown"
        return (
            f"CRITICAL: {len(damaged_assets)} assets are broken. "
            f"Affected: {assets_str}. "
            f"Run V2 Daily Pipeline to regenerate. "
            f"Check scheduler status: GET /yego-lima-growth/refresh/governance-status"
        )

    if system_status == STATUS_DEGRADED:
        assets_str = ", ".join(damaged_assets[:3]) if damaged_assets else "unknown"
        return (
            f"DEGRADED: {len(damaged_assets)} assets are stale. "
            f"Affected: {assets_str}. "
            f"Data may be outdated. Verify scheduler is running."
        )

    if system_status == STATUS_WARNING:
        return (
            "WARNING: Some assets approaching staleness threshold. "
            "Monitor for degradation. No immediate action required."
        )

    return None
