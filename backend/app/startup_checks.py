"""
Orquestación de arranque: clasificación crítica vs degradable y reporte para /health.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from app.db.connection import init_db_pool, create_plan_schema, create_ingestion_status_schema
from app.db.schema_verify import verify_schema, inspect_real_columns
from app.settings import settings

logger = logging.getLogger(__name__)


def run_startup_checks() -> Dict[str, Any]:
    """
    Ejecuta inicialización y validaciones. No sustituye init_db_pool en main si ya se llamó;
    aquí se asume llamada única desde startup_event.

    overall:
      - blocked: pool DB no disponible (no se puede operar).
      - degraded: fallo en verificación secundaria/inspección; API arranca con advertencias.
      - ok: verificaciones principales pasaron.
    """
    report: Dict[str, Any] = {
        "overall": "ok",
        "environment": settings.ENVIRONMENT,
        "checks": [],
        "schema_structures": None,
        "inspection": None,
    }

    try:
        init_db_pool()
        report["checks"].append(
            {"name": "db_pool", "status": "ok", "tier": "blocking", "detail": None}
        )
    except Exception as e:
        logger.exception("Startup bloqueado: pool DB")
        report["overall"] = "blocked"
        report["checks"].append(
            {
                "name": "db_pool",
                "status": "failed",
                "tier": "blocking",
                "detail": str(e),
            }
        )
        return report

    for name, fn in (
        ("plan_schema", create_plan_schema),
        ("ingestion_status_schema", create_ingestion_status_schema),
    ):
        try:
            fn()
            report["checks"].append(
                {"name": name, "status": "ok", "tier": "blocking", "detail": None}
            )
        except Exception as e:
            logger.exception("Startup: %s falló", name)
            report["overall"] = "degraded"
            report["checks"].append(
                {"name": name, "status": "failed", "tier": "blocking", "detail": str(e)}
            )

    try:
        report["schema_structures"] = verify_schema()
        report["checks"].append(
            {"name": "verify_schema", "status": "ok", "tier": "critical", "detail": None}
        )
    except ValueError:
        # Entorno dev: columnas críticas faltantes
        raise
    except Exception as e:
        logger.exception("verify_schema: fallo no fatal en arranque")
        report["overall"] = "degraded"
        report["checks"].append(
            {"name": "verify_schema", "status": "failed", "tier": "critical", "detail": str(e)}
        )

    try:
        report["inspection"] = inspect_real_columns()
        if report["inspection"] and report["inspection"].get("_error"):
            report["overall"] = "degraded"
            report["checks"].append(
                {
                    "name": "inspect_real_columns",
                    "status": "partial",
                    "tier": "non_blocking",
                    "detail": report["inspection"].get("_error"),
                }
            )
        else:
            report["checks"].append(
                {
                    "name": "inspect_real_columns",
                    "status": "ok",
                    "tier": "non_blocking",
                    "detail": None,
                }
            )
    except Exception as e:
        logger.exception("inspect_real_columns: degradación")
        report["overall"] = "degraded"
        report["inspection"] = {"_error": str(e)}
        report["checks"].append(
            {
                "name": "inspect_real_columns",
                "status": "failed",
                "tier": "non_blocking",
                "detail": str(e),
            }
        )

    # ── CF-H1G: Omniview Freshness Lightweight Check ──
    _run_omniview_freshness_startup_check(report)

    return report


def _run_omniview_freshness_startup_check(report: Dict[str, Any]) -> None:
    """
    Check liviano de freshness Omniview al iniciar.
    Solo consulta MAX(dates) — no ejecuta backfill.
    Loguea RAW max date, serving max date, status, y remediation.
    """
    try:
        from app.services.omniview_freshness_governance_service import get_omniview_freshness_governance

        freshness = get_omniview_freshness_governance()
        raw_max = (freshness.get("raw") or {}).get("max_date")
        status = freshness.get("status", "unknown")
        message = freshness.get("message", "")
        daily = (freshness.get("facts") or {}).get("daily", {})
        daily_max = daily.get("max_date")

        logger.info(
            "Startup Omniview Freshness: status=%s raw_max=%s daily_max=%s message=%s",
            status,
            raw_max,
            daily_max,
            message,
        )

        if status == "blocked":
            logger.warning(
                "Startup Omniview Freshness BLOCKED: remediation=%s",
                freshness.get("remediation"),
            )

        report["omniview_freshness_startup"] = {
            "status": status,
            "raw_max_date": raw_max,
            "daily_max_date": daily_max,
            "message": message,
            "remediation": freshness.get("remediation") if status != "ok" else None,
        }
        report["checks"].append(
            {
                "name": "omniview_freshness",
                "status": "ok" if status == "ok" else "warning",
                "tier": "non_blocking",
                "detail": f"status={status} raw_max={raw_max} daily_max={daily_max}",
            }
        )
    except Exception as e:
        logger.warning("Startup Omniview Freshness check error: %s", e)
        report["omniview_freshness_startup"] = {"status": "error", "error": str(e)}
        report["checks"].append(
            {
                "name": "omniview_freshness",
                "status": "failed",
                "tier": "non_blocking",
                "detail": str(e),
            }
        )
