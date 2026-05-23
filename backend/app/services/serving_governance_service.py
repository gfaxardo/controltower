"""
Serving Governance Service — FASE 1H.1
Capa de gobernanza operacional de serving facts y refreshes.

Protege contra:
- Runtime fallback automático (facts inexistentes o stale)
- Bloqueo de UI por consultas pesadas
- Falta de cobertura en grains/países/ciudades
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

STALE_THRESHOLD_HOURS = 24

# ─── Registry ────────────────────────────────────────────────────────────────

def register_serving_fact(
    serving_key: str,
    entity_name: str,
    grain: str,
    plan_version: Optional[str] = None,
    coverage_scope: Optional[Dict] = None,
    source_dependencies: Optional[List[str]] = None,
    fallback_allowed: bool = False,
    runtime_protected: bool = True,
) -> Dict[str, Any]:
    """Registra o actualiza un serving fact en el registry."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO ops.serving_registry
                (serving_key, entity_name, grain, plan_version, coverage_scope,
                 source_dependencies, fallback_allowed, runtime_protected, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s, NOW())
            ON CONFLICT (serving_key) DO UPDATE SET
                entity_name = EXCLUDED.entity_name,
                grain = EXCLUDED.grain,
                plan_version = EXCLUDED.plan_version,
                coverage_scope = EXCLUDED.coverage_scope,
                source_dependencies = EXCLUDED.source_dependencies,
                fallback_allowed = EXCLUDED.fallback_allowed,
                runtime_protected = EXCLUDED.runtime_protected,
                updated_at = NOW()
            RETURNING id, serving_key, created_at
        """, (
            serving_key, entity_name, grain, plan_version,
            coverage_scope or {}, source_dependencies or [],
            fallback_allowed, runtime_protected,
        ))
        row = cur.fetchone()
        cur.close()
        conn.commit()
    return dict(row) if row else {}


def mark_refresh_start(serving_key: str, triggered_by: str = "manual") -> str:
    """Marca inicio de refresh y devuelve refresh_id."""
    refresh_id = uuid.uuid4().hex[:12]
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE ops.serving_registry SET refresh_status = 'running', updated_at = NOW()
            WHERE serving_key = %s
        """, (serving_key,))
        cur.execute("""
            INSERT INTO ops.serving_refresh_log (refresh_id, serving_key, started_at, triggered_by)
            VALUES (%s, %s, NOW(), %s)
        """, (refresh_id, serving_key, triggered_by))
        cur.close()
        conn.commit()
    return refresh_id


def mark_refresh_end(
    serving_key: str,
    refresh_id: str,
    success: bool,
    rows_generated: int = 0,
    duration_ms: int = 0,
    error_message: Optional[str] = None,
):
    """Marca fin de refresh con resultado."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE ops.serving_refresh_log
            SET finished_at = NOW(), duration_ms = %s, rows_generated = %s,
                success = %s, error_message = %s
            WHERE refresh_id = %s
        """, (duration_ms, rows_generated, success, error_message, refresh_id))

        status = 'success' if success else 'failed'
        failure_at = 'NOW()' if not success else 'NULL'
        failure_reason = error_message if not success else 'NULL'
        cur.execute(f"""
            UPDATE ops.serving_registry
            SET refresh_status = '{status}',
                last_{'success' if success else 'failure'}_at = NOW(),
                last_failure_reason = {failure_reason},
                row_count = CASE WHEN %s > 0 THEN %s ELSE row_count END,
                generated_at = CASE WHEN %s THEN NOW() ELSE generated_at END,
                freshness_status = CASE WHEN %s THEN 'fresh' ELSE freshness_status END,
                updated_at = NOW()
            WHERE serving_key = %s
        """, (rows_generated, rows_generated, success, success, serving_key))
        cur.close()
        conn.commit()


# ─── Validation ──────────────────────────────────────────────────────────────

def validate_serving_coverage() -> Dict[str, Any]:
    """Valida cobertura de serving facts vs UI filters."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Grains materializados
        cur.execute("""
            SELECT grain, COUNT(*) as facts, SUM(row_count) as total_rows
            FROM ops.serving_registry
            WHERE active_flag = TRUE AND freshness_status != 'broken'
            GROUP BY grain
            ORDER BY grain
        """)
        grains = list(cur.fetchall())

        # Hechos stale
        cur.execute(f"""
            SELECT serving_key, entity_name, grain, freshness_status,
                   generated_at, EXTRACT(EPOCH FROM (NOW() - generated_at))/3600 AS hours_since
            FROM ops.serving_registry
            WHERE active_flag = TRUE
              AND generated_at < NOW() - INTERVAL '{STALE_THRESHOLD_HOURS} hours'
            ORDER BY generated_at
        """)
        stale = list(cur.fetchall())

        # Granos faltantes
        cur.execute("""
            SELECT unnest(ARRAY['daily','weekly','monthly']) AS grain
            EXCEPT
            SELECT grain FROM ops.serving_registry WHERE active_flag = TRUE
        """)
        missing_grains = [r['grain'] for r in cur.fetchall()]

        # Fallos recientes
        cur.execute("""
            SELECT serving_key, started_at, error_message
            FROM ops.serving_refresh_log
            WHERE success = FALSE
            ORDER BY started_at DESC LIMIT 20
        """)
        failures = list(cur.fetchall())

        cur.close()

    return {
        "grains": grains,
        "stale_facts": stale,
        "missing_grains": missing_grains,
        "recent_failures": failures,
        "stale_threshold_hours": STALE_THRESHOLD_HOURS,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def get_serving_health() -> Dict[str, Any]:
    """Estado de salud de la serving layer."""
    coverage = validate_serving_coverage()

    total_facts = sum(g['facts'] for g in coverage['grains'])
    total_rows = sum(g['total_rows'] for g in coverage['grains'])
    stale_count = len(coverage['stale_facts'])
    failure_count = len(coverage['recent_failures'])

    status = 'healthy'
    if stale_count > 0:
        status = 'degraded'
    if failure_count > 0 or coverage['missing_grains']:
        status = 'attention'

    return {
        "status": status,
        "total_facts": total_facts,
        "total_rows": total_rows,
        "stale_count": stale_count,
        "missing_grains": coverage['missing_grains'],
        "recent_failures_count": failure_count,
        "details": coverage,
    }


def detect_missing_grains() -> List[str]:
    """Detecta grains que la UI expone pero no tienen serving facts."""
    return validate_serving_coverage()['missing_grains']


def detect_stale_facts() -> List[Dict]:
    """Detecta serving facts con datos desactualizados."""
    return validate_serving_coverage()['stale_facts']


def detect_runtime_risk() -> List[Dict[str, Any]]:
    """Detecta serving facts que exponen riesgo de runtime fallback."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT serving_key, entity_name, grain, freshness_status, row_count,
                   fallback_allowed, runtime_protected
            FROM ops.serving_registry
            WHERE active_flag = TRUE
              AND (freshness_status IN ('stale','empty','broken') OR row_count = 0)
        """)
        rows = list(cur.fetchall())
        cur.close()

    at_risk = []
    for r in rows:
        risk = 'high'
        if r['fallback_allowed']:
            risk = 'medium'
        if r['runtime_protected']:
            risk = 'controlled'
        r['risk_level'] = risk
        at_risk.append(r)

    return at_risk


def compute_serving_integrity() -> Dict[str, Any]:
    """Integridad de la serving layer."""
    risk = detect_runtime_risk()
    health = get_serving_health()
    missing = detect_missing_grains()

    score = 100
    if health['stale_count'] > 0:
        score -= 20
    if missing:
        score -= 30 * len(missing)
    if health['recent_failures_count'] > 0:
        score -= 25

    return {
        "integrity_score": max(0, score),
        "status": health['status'],
        "runtime_risks": len(risk),
        "risk_details": [r['serving_key'] for r in risk],
        "missing_grains": missing,
        "stale_facts": health['stale_count'],
        "recommendation": (
            "All systems operational" if score >= 80
            else "Refresh recommended for stale/missing facts" if score >= 40
            else "URGENT: serving layer degraded — run refresh"
        ),
    }
