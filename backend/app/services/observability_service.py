"""
Fase 1 — Servicio de observabilidad E2E.
Lee ops.observability_artifact_registry, ops.observability_refresh_log,
ops.v_observability_module_status, ops.v_observability_freshness, ops.v_observability_artifact_lineage.
Expone overview, módulos, artefactos, lineage y freshness para API y UI.
Aditivo: no modifica lógica de negocio existente.
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


def get_observability_overview() -> dict[str, Any]:
    """
    Resumen: módulos con estado, conteo de artefactos con/sin refresh, riesgos.
    Combina v_observability_module_status y conteos de observability_refresh_log.
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT module_name, artifact_count, with_refresh_count, latest_refresh_at,
                       all_fresh, observability_coverage_pct
                FROM ops.v_observability_module_status
                ORDER BY module_name
            """)
            rows = cur.fetchall()
            modules = []
            for r in rows:
                modules.append({
                    "module_name": r["module_name"],
                    "artifact_count": r["artifact_count"],
                    "with_refresh_count": r["with_refresh_count"],
                    "latest_refresh_at": _serialize_ts(r["latest_refresh_at"]),
                    "all_fresh": r["all_fresh"],
                    "observability_coverage_pct": float(r["observability_coverage_pct"]) if r["observability_coverage_pct"] is not None else 0,
                })
            cur.execute("SELECT COUNT(*) AS n FROM ops.observability_refresh_log WHERE refresh_started_at >= now() - interval '7 days'")
            recent = cur.fetchone()
            return {
                "modules": modules,
                "recent_refreshes_7d": recent["n"] if recent else 0,
                "message": "Fase 1 observability E2E. Supply usa supply_refresh_log; resto puede usar observability_refresh_log.",
            }
        except Exception as e:
            logger.warning("get_observability_overview: %s", e)
            return {"modules": [], "recent_refreshes_7d": 0, "message": str(e), "error": True}
        finally:
            cur.close()


def get_observability_modules() -> list[dict[str, Any]]:
    """Estado por módulo (v_observability_module_status)."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT module_name, artifact_count, with_refresh_count, latest_refresh_at,
                       all_fresh, observability_coverage_pct
                FROM ops.v_observability_module_status
                ORDER BY module_name
            """)
            rows = cur.fetchall()
            return [
                {
                    "module_name": r["module_name"],
                    "artifact_count": r["artifact_count"],
                    "with_refresh_count": r["with_refresh_count"],
                    "latest_refresh_at": _serialize_ts(r["latest_refresh_at"]),
                    "all_fresh": r["all_fresh"],
                    "observability_coverage_pct": float(r["observability_coverage_pct"]) if r["observability_coverage_pct"] is not None else 0,
                }
                for r in rows
            ]
        except Exception as e:
            logger.warning("get_observability_modules: %s", e)
            return []
        finally:
            cur.close()


def get_observability_artifacts() -> list[dict[str, Any]]:
    """Lista de artefactos del registry con último refresh si existe."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT r.artifact_name, r.artifact_type, r.module_name, r.schema_name,
                       r.refresh_owner, r.source_kind, r.active_flag, r.notes,
                       l.latest_refresh_at
                FROM ops.observability_artifact_registry r
                LEFT JOIN (
                    SELECT artifact_name, MAX(refresh_finished_at) AS latest_refresh_at
                    FROM ops.observability_refresh_log
                    WHERE refresh_status = 'ok' AND refresh_finished_at IS NOT NULL
                    GROUP BY artifact_name
                ) l ON l.artifact_name = r.artifact_name
                WHERE r.active_flag
                ORDER BY r.module_name, r.artifact_name
            """)
            rows = cur.fetchall()
            out = []
            for r in rows:
                d = dict(r)
                d["latest_refresh_at"] = _serialize_ts(d.get("latest_refresh_at"))
                out.append(d)
            # Supply: rellenar latest_refresh desde supply_refresh_log para artefactos Supply
            cur.execute("""
                SELECT MAX(finished_at) AS ts FROM ops.supply_refresh_log
                WHERE status = 'ok' AND finished_at IS NOT NULL
            """)
            supply_ts = cur.fetchone()
            supply_ts_val = supply_ts["ts"] if supply_ts else None
            for d in out:
                if d["module_name"] == "Supply Dynamics" and d.get("latest_refresh_at") is None and supply_ts_val:
                    d["latest_refresh_at"] = _serialize_ts(supply_ts_val)
            return out
        except Exception as e:
            logger.warning("get_observability_artifacts: %s", e)
            return []
        finally:
            cur.close()


def get_observability_lineage() -> list[dict[str, Any]]:
    """Lineage: artefactos activos (v_observability_artifact_lineage)."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT artifact_name, artifact_type, module_name, schema_name, refresh_owner, notes
                FROM ops.v_observability_artifact_lineage
            """)
            return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("get_observability_lineage: %s", e)
            return []
        finally:
            cur.close()


def get_observability_freshness() -> list[dict[str, Any]]:
    """Señales de frescura unificadas (v_observability_freshness + supply_refresh_log)."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            cur.execute("""
                SELECT artifact_name, latest_refresh_at, source
                FROM ops.v_observability_freshness
                ORDER BY latest_refresh_at DESC NULLS LAST
            """)
            rows = cur.fetchall()
            return [
                {"artifact_name": r["artifact_name"], "latest_refresh_at": _serialize_ts(r["latest_refresh_at"]), "source": r["source"]}
                for r in rows
            ]
        except Exception as e:
            logger.warning("get_observability_freshness: %s", e)
            return []
        finally:
            cur.close()


def log_refresh(
    artifact_name: str,
    status: str = "ok",
    script_name: str | None = None,
    trigger_type: str = "script",
    error_message: str | None = None,
    rows_affected: int | None = None,
    rows_before: int | None = None,
    rows_after: int | None = None,
    duration_seconds: float | None = None,
) -> None:
    """
    Escribe una fila en ops.observability_refresh_log.
    Llamar al INICIO del refresh con status='running', luego al FINAL con status='ok' o 'error'.
    rows_before, rows_after, duration_seconds (STEP 7) permiten detectar degradación.
    Si la tabla no existe o no tiene columnas nuevas, no falla.
    """
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if status == "running":
                cur.execute("""
                    INSERT INTO ops.observability_refresh_log
                    (artifact_name, refresh_started_at, refresh_finished_at, refresh_status, trigger_type, script_name, error_message, rows_affected_if_known)
                    VALUES (%s, now(), NULL, 'running', %s, %s, NULL, NULL)
                """, (artifact_name, trigger_type, script_name or ""))
            else:
                try:
                    cur.execute("""
                        UPDATE ops.observability_refresh_log
                        SET refresh_finished_at = now(), refresh_status = %s, error_message = %s, rows_affected_if_known = %s,
                            rows_before = COALESCE(%s, rows_before), rows_after = COALESCE(%s, rows_after), duration_seconds = COALESCE(%s, duration_seconds)
                        WHERE id = (
                            SELECT id FROM ops.observability_refresh_log
                            WHERE artifact_name = %s AND refresh_finished_at IS NULL
                            ORDER BY id DESC LIMIT 1
                        )
                    """, (status, (error_message or "")[:500] if error_message else None, rows_affected,
                          rows_before, rows_after, duration_seconds, artifact_name))
                except Exception:
                    cur.execute("""
                        UPDATE ops.observability_refresh_log
                        SET refresh_finished_at = now(), refresh_status = %s, error_message = %s, rows_affected_if_known = %s
                        WHERE id = (
                            SELECT id FROM ops.observability_refresh_log
                            WHERE artifact_name = %s AND refresh_finished_at IS NULL
                            ORDER BY id DESC LIMIT 1
                        )
                    """, (status, (error_message or "")[:500] if error_message else None, rows_affected, artifact_name))
                if cur.rowcount == 0:
                    try:
                        cur.execute("""
                            INSERT INTO ops.observability_refresh_log
                            (artifact_name, refresh_started_at, refresh_finished_at, refresh_status, trigger_type, script_name, error_message, rows_affected_if_known, rows_before, rows_after, duration_seconds)
                            VALUES (%s, now(), now(), %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (artifact_name, status, trigger_type, script_name or "", (error_message or "")[:500] if error_message else None, rows_affected,
                              rows_before, rows_after, duration_seconds))
                    except Exception:
                        cur.execute("""
                            INSERT INTO ops.observability_refresh_log
                            (artifact_name, refresh_started_at, refresh_finished_at, refresh_status, trigger_type, script_name, error_message, rows_affected_if_known)
                            VALUES (%s, now(), now(), %s, %s, %s, %s, %s)
                        """, (artifact_name, status, trigger_type, script_name or "", (error_message or "")[:500] if error_message else None, rows_affected))
            conn.commit()
    except Exception as e:
        logger.debug("log_refresh (tabla puede no existir o columnas nuevas): %s", e)
