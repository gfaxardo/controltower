"""
Fase 2A — Servicio Real vs Proyección.

Expone: overview, dimensions, mapping_coverage, real_metrics, projection_template_contract,
system_segmentation_view, projection_segmentation_view.
Aditivo: no modifica lógica existente. Lee ops.v_real_metrics_monthly, projection_upload_staging,
projection_dimension_mapping, vistas comparativas.
"""
from __future__ import annotations

from typing import Any

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)


def _serialize_ts(v: Any) -> str | None:
    if v is None:
        return None
    return v.isoformat() if hasattr(v, "isoformat") else str(v)


def get_real_vs_projection_overview() -> dict[str, Any]:
    """Resumen: readiness, conteo staging proyección, conteo mapping, si hay datos reales."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            out: dict[str, Any] = {
                "ready_for_comparison": False,
                "projection_loaded": False,
                "mapping_coverage_pct": None,
                "real_metrics_available": False,
                "message": "Fase 2A Real vs Proyección.",
            }
            try:
                cur.execute("SELECT COUNT(*) AS n FROM ops.projection_upload_staging")
                r = cur.fetchone()
                staging_count = r["n"] if r else 0
                out["projection_staging_rows"] = staging_count
                out["projection_loaded"] = staging_count > 0
            except Exception:
                out["projection_staging_rows"] = 0
            try:
                cur.execute("SELECT COUNT(*) AS n FROM ops.projection_dimension_mapping")
                r = cur.fetchone()
                out["mapping_rules_count"] = r["n"] if r else 0
            except Exception:
                out["mapping_rules_count"] = 0
            try:
                cur.execute("SELECT COUNT(*) AS n FROM ops.v_real_metrics_monthly")
                r = cur.fetchone()
                real_count = r["n"] if r else 0
                out["real_metrics_rows"] = real_count
                out["real_metrics_available"] = real_count > 0
            except Exception:
                out["real_metrics_rows"] = 0
            out["ready_for_comparison"] = out["projection_loaded"] and out["real_metrics_available"]
            cur.close()
            return out
    except Exception as e:
        logger.warning("get_real_vs_projection_overview: %s", e)
        return {
            "ready_for_comparison": False,
            "projection_loaded": False,
            "real_metrics_available": False,
            "message": str(e),
            "error": True,
        }


def get_real_vs_projection_dimensions() -> list[dict[str, Any]]:
    """Dimensiones disponibles para el comparativo (sistema)."""
    return [
        {"id": "country", "label": "País", "source": "system"},
        {"id": "city", "label": "Ciudad", "source": "system"},
        {"id": "city_norm", "label": "Ciudad (normalizada)", "source": "system"},
        {"id": "line_of_business", "label": "LOB", "source": "system"},
        {"id": "segment", "label": "Segmento (b2b/b2c)", "source": "system"},
        {"id": "park_id", "label": "Park", "source": "system"},
        {"id": "period", "label": "Periodo (YYYY-MM)", "source": "system"},
    ]


def get_mapping_coverage() -> list[dict[str, Any]]:
    """Cobertura de mapping por dimension_type."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("""
                SELECT dimension_type, COUNT(*) AS rule_count,
                       COUNT(*) FILTER (WHERE matching_status = 'matched') AS matched_count
                FROM ops.projection_dimension_mapping
                GROUP BY dimension_type
                ORDER BY dimension_type
            """)
            rows = cur.fetchall()
            cur.close()
            return [
                {
                    "dimension_type": r["dimension_type"],
                    "rule_count": r["rule_count"],
                    "matched_count": r["matched_count"],
                }
                for r in rows
            ]
    except Exception as e:
        logger.warning("get_mapping_coverage: %s", e)
        return []


def get_real_metrics(
    country: str | None = None,
    city: str | None = None,
    period: str | None = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """Métricas reales mensuales desde ops.v_real_metrics_monthly."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            where = []
            params: list[Any] = []
            if country:
                where.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            if city:
                where.append("LOWER(TRIM(city_norm)) = LOWER(TRIM(%s))")
                params.append(city)
            if period:
                where.append("TO_CHAR(period_date, 'YYYY-MM') = %s")
                params.append(period)
            where_clause = " AND ".join(where) if where else "1=1"
            params.append(limit)
            cur.execute(f"""
                SELECT period_date, period, country, city, city_norm, line_of_business, segment, park_id,
                       drivers_real, trips_real, revenue_real, avg_ticket_real,
                       avg_trips_per_driver_real, revenue_per_trip_real, revenue_per_driver_real
                FROM ops.v_real_metrics_monthly
                WHERE {where_clause}
                ORDER BY period_date DESC, country, city_norm, line_of_business
                LIMIT %s
            """, params)
            rows = cur.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["period_date"] = _serialize_ts(d.get("period_date"))
                out.append(d)
            cur.close()
            return out
    except Exception as e:
        logger.warning("get_real_metrics: %s", e)
        return []


def get_projection_template_contract() -> dict[str, Any]:
    """Contrato esperado del Excel de proyección (placeholder hasta plantilla real)."""
    return {
        "description": "Contrato esperado para carga de proyección. Ver docs/projection_template_contract.md.",
        "expected_columns_suggested": [
            "period",
            "period_type",
            "raw_country",
            "raw_city",
            "raw_line_of_business",
            "raw_segment",
            "drivers_plan",
            "trips_plan",
            "revenue_plan",
            "avg_ticket_plan",
        ],
        "staging_table": "ops.projection_upload_staging",
        "mapping_table": "ops.projection_dimension_mapping",
    }


def get_system_segmentation_view(
    country: str | None = None,
    period: str | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    """Vista comparativa por segmentación del sistema (ops.v_real_vs_projection_system_segmentation)."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            where = []
            params: list[Any] = []
            if country:
                where.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            if period:
                where.append("TO_CHAR(period_date, 'YYYY-MM') = %s")
                params.append(period)
            where_clause = " AND ".join(where) if where else "1=1"
            params.append(limit)
            cur.execute(f"""
                SELECT period_date, period, country, city, city_norm, line_of_business, segment, park_id,
                       drivers_real, trips_real, avg_trips_per_driver_real, avg_ticket_real, revenue_real,
                       drivers_plan, trips_plan, avg_trips_per_driver_plan, avg_ticket_plan, revenue_plan,
                       drivers_gap, trips_gap, revenue_gap,
                       gap_explained_by_driver_count, gap_explained_by_productivity, gap_explained_by_ticket
                FROM ops.v_real_vs_projection_system_segmentation
                WHERE {where_clause}
                ORDER BY period_date DESC, country, city_norm
                LIMIT %s
            """, params)
            rows = cur.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["period_date"] = _serialize_ts(d.get("period_date"))
                out.append(d)
            cur.close()
            return out
    except Exception as e:
        logger.warning("get_system_segmentation_view: %s", e)
        return []


def get_projection_segmentation_view(
    country: str | None = None,
    period: str | None = None,
    limit: int = 300,
) -> list[dict[str, Any]]:
    """Vista comparativa por segmentación proyección (placeholder)."""
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            where = []
            params: list[Any] = []
            if country:
                where.append("LOWER(TRIM(country)) = LOWER(TRIM(%s))")
                params.append(country)
            if period:
                where.append("TO_CHAR(period_date, 'YYYY-MM') = %s")
                params.append(period)
            where_clause = " AND ".join(where) if where else "1=1"
            params.append(limit)
            cur.execute(f"""
                SELECT period_date, period, country, city, line_of_business,
                       drivers_real, trips_real, avg_trips_per_driver_real, avg_ticket_real, revenue_real,
                       drivers_plan, trips_plan, avg_ticket_plan, revenue_plan,
                       drivers_gap, trips_gap, revenue_gap
                FROM ops.v_real_vs_projection_projection_segmentation
                WHERE {where_clause}
                ORDER BY period_date DESC, country, city
                LIMIT %s
            """, params)
            rows = cur.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["period_date"] = _serialize_ts(d.get("period_date"))
                out.append(d)
            cur.close()
            return out
    except Exception as e:
        logger.warning("get_projection_segmentation_view: %s", e)
        return []
