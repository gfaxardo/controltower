"""
Estado de la fuente base de viajes (upstream) antes del pipeline business slice.

Modos: tabla configurable (p. ej. public.trips_2026) o vista canónica ops.v_trips_real_canon.
"""
from __future__ import annotations

import logging
import re
from datetime import date
from datetime import datetime
from typing import Any, Dict, Optional

from app.settings import settings

logger = logging.getLogger(__name__)

_CANON_VIEW = "ops.v_trips_real_canon"
_SAFE_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


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


def _upstream_lag_status(lag: Optional[int]) -> str:
    """lag = today - max_date en días. Umbrales: 0-1 fresh, 2 stale, >=3 critical."""
    if lag is None:
        return "empty"
    if lag <= 1:
        return "fresh"
    if lag == 2:
        return "stale"
    return "critical"


def _table_exists(cur, schema: str, table: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, table),
    )
    return cur.fetchone() is not None


def _view_exists(cur, schema: str, name: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM information_schema.views
        WHERE table_schema = %s AND table_name = %s
        """,
        (schema, name),
    )
    return cur.fetchone() is not None


def get_upstream_real_status(conn) -> Dict[str, Any]:
    """
    Devuelve métricas de la fuente base de viajes (upstream).

    Returns:
        source: identificador legible (tabla o vista)
        max_event_date, row_count_recent, status, lag_days_vs_today
        mode: table | canon
    """
    today = date.today()
    recent_days = max(1, int(getattr(settings, "OMNIVIEW_UPSTREAM_RECENT_DAYS", 7) or 7))
    mode = str(getattr(settings, "OMNIVIEW_UPSTREAM_MODE", "table") or "table").lower().strip()

    out: Dict[str, Any] = {
        "source": "",
        "max_event_date": None,
        "row_count_recent": None,
        "status": "unknown",
        "lag_days_vs_today": None,
        "mode": mode,
        "error": None,
    }

    cur = conn.cursor()
    try:
        if mode == "canon":
            out["source"] = _CANON_VIEW
            if not _view_exists(cur, "ops", "v_trips_real_canon"):
                out["status"] = "unknown"
                out["error"] = "vista ops.v_trips_real_canon no existe"
                return out
            cur.execute(
                """
                SELECT MAX(fecha_inicio_viaje::date) AS mx
                FROM ops.v_trips_real_canon
                """
            )
            row = cur.fetchone()
            max_dt = _d(row[0]) if row else None
            out["max_event_date"] = _iso(max_dt)
            if max_dt is None:
                out["status"] = "empty"
                return out
            lag = (today - max_dt).days
            out["lag_days_vs_today"] = lag
            out["status"] = _upstream_lag_status(lag)
            cur.execute(
                """
                SELECT COUNT(*)::bigint
                FROM ops.v_trips_real_canon
                WHERE fecha_inicio_viaje >= (CURRENT_DATE - %s::integer)
                """,
                (recent_days,),
            )
            rc = cur.fetchone()
            out["row_count_recent"] = int(rc[0]) if rc and rc[0] is not None else 0
            return out

        # --- table mode ---
        full = str(getattr(settings, "OMNIVIEW_UPSTREAM_TRIPS_TABLE", "public.trips_2026") or "public.trips_2026").strip()
        parts = full.split(".")
        if len(parts) == 2:
            schema, tbl = parts[0].strip(), parts[1].strip()
        else:
            schema, tbl = "public", parts[0].strip()

        col = str(getattr(settings, "OMNIVIEW_UPSTREAM_DATE_COLUMN", "fecha_inicio_viaje") or "fecha_inicio_viaje").strip()
        if not _SAFE_IDENT.match(schema) or not _SAFE_IDENT.match(tbl) or not _SAFE_IDENT.match(col):
            out["status"] = "unknown"
            out["error"] = "identificador de tabla/columna upstream no permitido"
            return out

        out["source"] = f"{schema}.{tbl}"
        if not _table_exists(cur, schema, tbl):
            out["status"] = "empty"
            out["error"] = f"tabla {schema}.{tbl} no existe"
            return out

        # Identifier interpolation: validated above
        q_max = f'SELECT MAX("{col}"::date) FROM "{schema}"."{tbl}"'
        cur.execute(q_max)
        row = cur.fetchone()
        max_dt = _d(row[0]) if row else None
        out["max_event_date"] = _iso(max_dt)

        if max_dt is None:
            cur.execute(f'SELECT COUNT(*)::bigint FROM "{schema}"."{tbl}"')
            n = cur.fetchone()
            if n and (n[0] or 0) == 0:
                out["status"] = "empty"
            else:
                out["status"] = "unknown"
            return out

        lag = (today - max_dt).days
        out["lag_days_vs_today"] = lag
        out["status"] = _upstream_lag_status(lag)

        q_cnt = (
            f'SELECT COUNT(*)::bigint FROM "{schema}"."{tbl}" '
            f'WHERE "{col}" >= (CURRENT_DATE - %s::integer)'
        )
        cur.execute(q_cnt, (recent_days,))
        rc = cur.fetchone()
        out["row_count_recent"] = int(rc[0]) if rc and rc[0] is not None else 0
        return out

    except Exception as e:
        logger.warning("get_upstream_real_status: %s", e, exc_info=True)
        out["status"] = "unknown"
        out["error"] = str(e)
        return out
    finally:
        cur.close()
