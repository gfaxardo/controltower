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

    return report
