"""Persistencia gobernada de ownership de proyecciones (Fase 0.1).

Separa la responsabilidad operativa (jefe_producto, estado) de las métricas
de staging, creando una capa de governance trazable por plan_version.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date as _date
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

OWNERSHIP_CANDIDATE_COLS = ("jefe_producto", "producto", "estado")


def _hash_row(plan_version: str, country: str, city: str, lob: str) -> str:
    raw = f"{plan_version}|{country or ''}|{city or ''}|{lob}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def _has_ownership_data(row: Dict[str, Any]) -> bool:
    for col in OWNERSHIP_CANDIDATE_COLS:
        val = row.get(col)
        if val and str(val).strip():
            return True
    return False


def _parse_period_date(raw: Any) -> Optional[_date]:
    """Convierte period strings como '2026-01' o '2026-01-01' a date."""
    if not raw:
        return None
    s = str(raw).strip()
    if not s:
        return None
    if len(s) == 7 and s[4] == '-':
        s = s + '-01'
    return _date.fromisoformat(s)


def sync_ownership_from_staging(plan_version: str) -> Dict[str, Any]:
    """
    Extrae ownership desde staging.control_loop_plan_metric_long y lo persiste
    en ops.projection_ownership.

    Deduplica por dimensiones (country, city, linea_negocio_canonica),
    ignorando métricas y períodos.

    Retorna dict con resumen de la sincronización.
    """
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                SELECT DISTINCT
                    country,
                    city,
                    linea_negocio_canonica,
                    jefe_producto,
                    producto,
                    estado,
                    MIN(period) AS source_period_first,
                    upload_batch_id
                FROM staging.control_loop_plan_metric_long
                WHERE plan_version = %s
                  AND (jefe_producto IS NOT NULL OR estado IS NOT NULL)
                GROUP BY country, city, linea_negocio_canonica,
                         jefe_producto, producto, estado, upload_batch_id
                """,
                (plan_version,),
            )
            staging_rows = cur.fetchall()
        except Exception as e:
            cur.close()
            logger.error("sync_ownership_from_staging: query failed — %s", e)
            return {"synced": 0, "conflicts": 0, "error": str(e)}

        if not staging_rows:
            cur.close()
            return {"synced": 0, "conflicts": 0, "reason": "no_ownership_data"}

        inserted = 0
        conflicts = 0
        conflict_samples: List[Dict] = []

        for row in staging_rows:
            country, city, lob_canon, jefe, prod, est, period_first, upload_id = row
            city_norm = city.lower().strip() if city else None
            row_hash = _hash_row(plan_version, country or "", city or "", lob_canon)

            try:
                cur.execute(
                    """
                    SELECT id FROM ops.projection_ownership
                    WHERE plan_version_key = %s
                      AND COALESCE(country, '') = COALESCE(%s, '')
                      AND COALESCE(city, '') = COALESCE(%s, '')
                      AND linea_negocio_canonica = %s
                    """,
                    (plan_version, country or "", city or "", lob_canon),
                )
                existing = cur.fetchone()

                if existing:
                    cur.execute(
                        """
                        UPDATE ops.projection_ownership
                        SET jefe_producto = COALESCE(%s, jefe_producto),
                            producto = COALESCE(%s, producto),
                            estado = COALESCE(%s, estado),
                            updated_at = NOW()
                        WHERE id = %s
                        """,
                        (jefe, prod, est, existing[0]),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO ops.projection_ownership (
                            plan_version_key, country, city, city_norm,
                            linea_negocio_canonica,
                            jefe_producto, producto, estado,
                            source_upload_id, source_period_first, source_row_hash
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            plan_version, country, city, city_norm,
                            lob_canon,
                            jefe, prod, est,
                            str(upload_id) if upload_id else None,
                            _parse_period_date(period_first),
                            row_hash,
                        ),
                    )
                    inserted += 1

                if jefe:
                    cur.execute(
                        """
                        SELECT jefe_producto
                        FROM ops.projection_ownership
                        WHERE plan_version_key = %s
                          AND COALESCE(country, '') = COALESCE(%s, '')
                          AND COALESCE(city, '') = COALESCE(%s, '')
                          AND linea_negocio_canonica = %s
                        """,
                        (plan_version, country or "", city or "", lob_canon),
                    )
                    current = cur.fetchone()
                    if current and current[0] and current[0] != jefe:
                        conflicts += 1
                        if len(conflict_samples) < 10:
                            conflict_samples.append(
                                {
                                    "plan_version": plan_version,
                                    "country": country,
                                    "city": city,
                                    "lob": lob_canon,
                                    "existing_jefe": current[0],
                                    "new_jefe": jefe,
                                }
                            )

            except Exception as e:
                logger.warning(
                    "sync_ownership: error en fila %s/%s/%s — %s",
                    country, city, lob_canon, e,
                )

        conn.commit()
        cur.close()

        result = {
            "synced": inserted,
            "conflicts": conflicts,
            "plan_version": plan_version,
        }
        if conflict_samples:
            result["conflict_samples"] = conflict_samples
            logger.warning(
                "sync_ownership: %d conflictos detectados (primeros %d reportados)",
                conflicts, len(conflict_samples),
            )

        return result


def query_ownership_serving_fact(
    plan_version_key: Optional[str] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    jefe_producto: Optional[str] = None,
    lob: Optional[str] = None,
    period: Optional[str] = None,
    ownership_assignment: Optional[str] = None,
    limit: int = 2000,
    offset: int = 0,
) -> Dict[str, Any]:
    """Consulta la MV ops.mv_ownership_serving_fact con filtros opcionales.

    Retorna rows + metadata (totals, owners detectados, grain info).
    Solo lectura. No modifica datos.
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        where = ["TRUE"]
        params: List[Any] = []

        if plan_version_key:
            where.append("plan_version = %s")
            params.append(plan_version_key)
        if country:
            where.append("TRIM(LOWER(COALESCE(country, ''))) = TRIM(LOWER(%s))")
            params.append(country)
        if city:
            where.append("TRIM(LOWER(COALESCE(city, ''))) = TRIM(LOWER(%s))")
            params.append(city)
        if jefe_producto:
            where.append("TRIM(LOWER(COALESCE(jefe_producto, ''))) = TRIM(LOWER(%s))")
            params.append(jefe_producto)
        if lob:
            where.append("TRIM(LOWER(COALESCE(lob_base, ''))) = TRIM(LOWER(%s))")
            params.append(lob)
        if period:
            where.append("to_char(period, 'YYYY-MM') = %s")
            params.append(period)
        if ownership_assignment:
            where.append("ownership_assignment = %s")
            params.append(ownership_assignment)

        clause = " AND ".join(where)

        try:
            cur.execute(
                f"""
                SELECT COUNT(*) AS total_rows
                FROM ops.mv_ownership_serving_fact
                WHERE {clause}
                """,
                params,
            )
            total = cur.fetchone()["total_rows"]

            cur.execute(
                f"""
                SELECT
                    plan_version, period, month, country, city, city_norm,
                    lob_base, segment, jefe_producto, producto_plan,
                    estado_validacion, ownership_assignment, ownership_quality,
                    conflict_detected, conflict_detail,
                    projected_trips, projected_drivers, projected_ticket,
                    projected_revenue, projected_trips_per_driver,
                    real_trips, real_trips_cancelled, real_active_drivers,
                    real_avg_ticket, real_commission_pct, real_revenue,
                    execution_pct_trips, execution_pct_revenue,
                    gap_trips, gap_revenue, momentum_status,
                    mom_pct_real_trips, mom_pct_real_revenue,
                    mom_pct_projected_trips, mom_delta_execution_pp,
                    real_fact_refreshed_at, refreshed_at
                FROM ops.mv_ownership_serving_fact
                WHERE {clause}
                ORDER BY period DESC, country, city, lob_base, jefe_producto
                LIMIT %s OFFSET %s
                """,
                params + [limit, offset],
            )
            rows = [dict(r) for r in cur.fetchall()]

            cur.execute(
                f"""
                SELECT
                    COUNT(DISTINCT jefe_producto) FILTER (WHERE jefe_producto IS NOT NULL) AS owners_detected,
                    COUNT(*) FILTER (WHERE ownership_assignment = 'assigned') AS assigned_count,
                    COUNT(*) FILTER (WHERE ownership_assignment = 'missing') AS missing_count,
                    COUNT(*) FILTER (WHERE ownership_assignment = 'conflicting') AS conflicting_count,
                    SUM(projected_trips) AS total_projected_trips,
                    SUM(projected_revenue) AS total_projected_revenue,
                    SUM(real_trips) AS total_real_trips,
                    SUM(real_revenue) AS total_real_revenue
                FROM ops.mv_ownership_serving_fact
                WHERE {clause}
                """,
                params,
            )
            totals = dict(cur.fetchone())

            cur.execute(
                f"""
                SELECT jefe_producto, COUNT(*) AS row_count,
                       SUM(projected_trips) AS projected_trips,
                       SUM(real_trips) AS real_trips,
                       SUM(projected_revenue) AS projected_revenue,
                       SUM(real_revenue) AS real_revenue
                FROM ops.mv_ownership_serving_fact
                WHERE {clause} AND jefe_producto IS NOT NULL
                GROUP BY jefe_producto
                ORDER BY row_count DESC
                """,
                params,
            )
            by_owner = [dict(r) for r in cur.fetchall()]

            cur.close()
        except Exception as e:
            cur.close()
            raise

    return {
        "rows": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
        "aggregates": totals,
        "by_owner": by_owner,
    }


def get_ownership_summary(plan_version_key: str) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT COUNT(*) FROM ops.projection_ownership WHERE plan_version_key = %s",
                (plan_version_key,),
            )
            total = cur.fetchone()[0]

            if total == 0:
                cur.close()
                return {
                    "plan_version_key": plan_version_key,
                    "total_ownership_rows": 0,
                    "owners_detected": [],
                    "conflicts_count": 0,
                    "missing_owner_count": 0,
                    "rows_by_owner": {},
                    "conflicts_sample": [],
                }

            cur.execute(
                """
                SELECT COUNT(*)
                FROM ops.projection_ownership
                WHERE plan_version_key = %s AND conflict_detected = TRUE
                """,
                (plan_version_key,),
            )
            conflicts = cur.fetchone()[0]

            cur.execute(
                """
                SELECT COUNT(*)
                FROM ops.projection_ownership
                WHERE plan_version_key = %s
                  AND (jefe_producto IS NULL OR TRIM(jefe_producto) = '')
                """,
                (plan_version_key,),
            )
            missing = cur.fetchone()[0]

            cur.execute(
                """
                SELECT jefe_producto, COUNT(*) AS cnt
                FROM ops.projection_ownership
                WHERE plan_version_key = %s AND jefe_producto IS NOT NULL
                GROUP BY jefe_producto
                ORDER BY cnt DESC
                """,
                (plan_version_key,),
            )
            by_owner = {r[0]: r[1] for r in cur.fetchall()}

            owners = list(by_owner.keys())

            cur.execute(
                """
                SELECT country, city, linea_negocio_canonica,
                       jefe_producto, estado, conflict_detail
                FROM ops.projection_ownership
                WHERE plan_version_key = %s AND conflict_detected = TRUE
                LIMIT 20
                """,
                (plan_version_key,),
            )
            conflict_samples = [
                {
                    "country": r[0],
                    "city": r[1],
                    "lob": r[2],
                    "jefe_producto": r[3],
                    "estado": r[4],
                    "detail": r[5],
                }
                for r in cur.fetchall()
            ]

            cur.close()

            return {
                "plan_version_key": plan_version_key,
                "total_ownership_rows": total,
                "owners_detected": owners,
                "conflicts_count": conflicts,
                "missing_owner_count": missing,
                "rows_by_owner": by_owner,
                "conflicts_sample": conflict_samples,
            }
        except Exception as e:
            cur.close()
            raise
