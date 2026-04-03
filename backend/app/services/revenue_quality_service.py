"""
Revenue Quality Service — Hardening de calidad de revenue.
Evalúa señales de calidad, genera alertas, persiste resultados.
Consumido por endpoints y scripts de monitoreo.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.db.connection import get_db
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

PROXY_WARNING_PCT = 80.0
PROXY_BLOCKED_PCT = 95.0
MISSING_WARNING_PCT = 5.0
MISSING_BLOCKED_PCT = 20.0
REAL_DROP_WARNING_PCT = 30.0
ZERO_REVENUE_WARNING_PCT = 10.0
DRIFT_WARNING_PCT = 15.0
DRIFT_BLOCKED_PCT = 40.0


def _float(v: Any) -> Optional[float]:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    try:
        f = float(v)
        if f != f:  # NaN check
            return None
        return f
    except (TypeError, ValueError):
        return None


def _run_checks(conn) -> List[Dict[str, Any]]:
    """Ejecuta todas las validaciones y retorna lista de alertas."""
    alerts: List[Dict[str, Any]] = []
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # ── Check 1: NaN en precio_yango_pro (fuente raw) ──
    for tbl in ("trips_2025", "trips_2026"):
        cur.execute(f"""
            SELECT COUNT(*) AS nan_count
            FROM public.{tbl}
            WHERE condicion = 'Completado'
              AND fecha_inicio_viaje IS NOT NULL
              AND precio_yango_pro = 'NaN'::numeric
        """)
        r = cur.fetchone()
        nan_count = int(r["nan_count"]) if r else 0
        sev = "blocked" if nan_count > 0 else "ok"
        alerts.append({
            "domain": f"raw.{tbl}",
            "severity": sev,
            "metric": "precio_yango_pro_nan",
            "observed_value": nan_count,
            "threshold": 0,
            "message": f"{nan_count} viajes completados con precio_yango_pro=NaN en {tbl}",
            "recommendation": "Investigar y limpiar NaN en fuente raw" if nan_count > 0 else None,
        })

    # ── Check 2: Revenue source distribution (último mes cerrado, hourly-first) ──
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE revenue_source = 'real') AS real_trips,
            COUNT(*) FILTER (WHERE revenue_source = 'proxy') AS proxy_trips,
            COUNT(*) FILTER (WHERE revenue_source = 'missing') AS missing_trips,
            COUNT(*) AS total_completed
        FROM ops.v_real_trip_fact_v2
        WHERE is_completed
          AND trip_month_start >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month')::date
          AND trip_month_start < date_trunc('month', CURRENT_DATE)::date
    """)
    r = cur.fetchone()
    total = int(r["total_completed"]) if r else 0
    real_t = int(r["real_trips"]) if r else 0
    proxy_t = int(r["proxy_trips"]) if r else 0
    missing_t = int(r["missing_trips"]) if r else 0

    if total > 0:
        pct_proxy = round(100.0 * proxy_t / total, 2)
        pct_missing = round(100.0 * missing_t / total, 2)
        pct_real = round(100.0 * real_t / total, 2)

        proxy_sev = "blocked" if pct_proxy >= PROXY_BLOCKED_PCT else (
            "warning" if pct_proxy >= PROXY_WARNING_PCT else "ok"
        )
        alerts.append({
            "domain": "hourly_first",
            "severity": proxy_sev,
            "metric": "pct_proxy",
            "observed_value": pct_proxy,
            "threshold": PROXY_WARNING_PCT,
            "message": f"Proxy coverage: {pct_proxy}% ({proxy_t:,} de {total:,} completados)",
            "recommendation": "Resolver ingestión de comision_empresa_asociada upstream" if proxy_sev != "ok" else None,
        })

        missing_sev = "blocked" if pct_missing >= MISSING_BLOCKED_PCT else (
            "warning" if pct_missing >= MISSING_WARNING_PCT else "ok"
        )
        alerts.append({
            "domain": "hourly_first",
            "severity": missing_sev,
            "metric": "pct_missing",
            "observed_value": pct_missing,
            "threshold": MISSING_WARNING_PCT,
            "message": f"Missing revenue: {pct_missing}% ({missing_t:,} viajes sin revenue real ni proxy)",
            "recommendation": "Verificar precio_yango_pro y comision para viajes missing" if missing_sev != "ok" else None,
        })

        alerts.append({
            "domain": "hourly_first",
            "severity": "ok",
            "metric": "pct_real",
            "observed_value": pct_real,
            "threshold": None,
            "message": f"Real revenue coverage: {pct_real}% ({real_t:,} viajes con comisión real)",
            "recommendation": None,
        })

    # ── Check 3: Revenue anomalías (gross_revenue NaN en day_v2) ──
    cur.execute("""
        SELECT COUNT(*) AS nan_rows
        FROM ops.mv_real_lob_day_v2
        WHERE gross_revenue = 'NaN'::numeric OR margin_total = 'NaN'::numeric
    """)
    r = cur.fetchone()
    nan_rows = int(r["nan_rows"]) if r else 0
    sev = "blocked" if nan_rows > 0 else "ok"
    alerts.append({
        "domain": "mv_day_v2",
        "severity": sev,
        "metric": "nan_in_aggregates",
        "observed_value": nan_rows,
        "threshold": 0,
        "message": f"{nan_rows} filas con NaN en gross_revenue/margin_total en day_v2",
        "recommendation": "Refresh MVs después de aplicar NaN guard" if nan_rows > 0 else None,
    })

    # ── Check 4: Zero revenue en ciudades activas ──
    cur.execute("""
        SELECT city, SUM(completed_trips) AS completed, SUM(gross_revenue) AS revenue
        FROM ops.mv_real_lob_day_v2
        WHERE trip_date >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY city
        HAVING SUM(completed_trips) > 100
    """)
    for row in cur.fetchall():
        city = row["city"]
        completed = int(row["completed"])
        revenue = _float(row["revenue"]) or 0
        if revenue == 0 and completed > 0:
            alerts.append({
                "domain": f"hourly_first.{city}",
                "severity": "blocked",
                "metric": "zero_revenue_active_city",
                "observed_value": 0,
                "threshold": 1,
                "message": f"Ciudad {city}: {completed:,} completados últimos 7d pero revenue=0",
                "recommendation": f"Verificar proxy y NaN para {city}",
            })

    # ── Check 5: Drift Business Slice vs hourly-first ──
    cur.execute("""
        WITH hf AS (
            SELECT date_trunc('month', trip_date)::date AS month,
                   SUM(completed_trips) AS hf_trips
            FROM ops.mv_real_lob_day_v2
            WHERE trip_date >= date_trunc('month', CURRENT_DATE - INTERVAL '2 months')::date
            GROUP BY 1
        ),
        bs AS (
            SELECT month,
                   SUM(trips_completed) AS bs_trips
            FROM ops.real_business_slice_month_fact
            WHERE month >= date_trunc('month', CURRENT_DATE - INTERVAL '2 months')::date
            GROUP BY 1
        )
        SELECT
            COALESCE(hf.month, bs.month) AS month,
            COALESCE(hf.hf_trips, 0) AS hf_trips,
            COALESCE(bs.bs_trips, 0) AS bs_trips
        FROM hf FULL OUTER JOIN bs ON hf.month = bs.month
        ORDER BY month
    """)
    for row in cur.fetchall():
        hf_t = int(row["hf_trips"])
        bs_t = int(row["bs_trips"])
        month = row["month"]
        if hf_t == 0 and bs_t == 0:
            continue
        base = max(hf_t, bs_t)
        diff_pct = round(100.0 * abs(hf_t - bs_t) / base, 2) if base > 0 else 0
        sev = "blocked" if diff_pct >= DRIFT_BLOCKED_PCT else (
            "warning" if diff_pct >= DRIFT_WARNING_PCT else "ok"
        )
        alerts.append({
            "domain": "cross_chain_drift",
            "severity": sev,
            "metric": "trips_drift_pct",
            "observed_value": diff_pct,
            "threshold": DRIFT_WARNING_PCT,
            "message": f"Drift {month}: hourly-first={hf_t:,} vs business_slice={bs_t:,} ({diff_pct}%)",
            "recommendation": "Verificar normalización de country/city entre cadenas" if sev != "ok" else None,
            "details": {"month": str(month), "hf_trips": hf_t, "bs_trips": bs_t},
        })

    cur.close()
    return alerts


def run_revenue_quality_check() -> Dict[str, Any]:
    """Ejecuta check completo y retorna resultado estructurado."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SET statement_timeout = '300000'")
        cur.close()

        alerts = _run_checks(conn)

        severities = [a["severity"] for a in alerts]
        if "blocked" in severities:
            overall = "blocked"
        elif "warning" in severities:
            overall = "warning"
        else:
            overall = "ok"

        return {
            "check_ts": datetime.utcnow().isoformat(),
            "overall_status": overall,
            "alerts_count": len(alerts),
            "blocked_count": severities.count("blocked"),
            "warning_count": severities.count("warning"),
            "ok_count": severities.count("ok"),
            "alerts": alerts,
        }


def persist_alerts(alerts: List[Dict[str, Any]]) -> int:
    """Persiste alertas en ops.revenue_quality_alerts."""
    import json

    with get_db() as conn:
        cur = conn.cursor()
        count = 0
        for a in alerts:
            details_json = json.dumps(a.get("details")) if a.get("details") else None
            cur.execute("""
                INSERT INTO ops.revenue_quality_alerts
                    (domain, severity, metric, observed_value, threshold,
                     message, recommendation, details)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                a["domain"], a["severity"], a["metric"],
                a.get("observed_value"), a.get("threshold"),
                a["message"], a.get("recommendation"), details_json
            ))
            count += 1
        cur.close()
        return count


def get_latest_alerts(limit: int = 50) -> List[Dict[str, Any]]:
    """Obtiene las alertas más recientes de la tabla persistente."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT id, check_ts, domain, severity, metric,
                   observed_value, threshold, message, recommendation
            FROM ops.revenue_quality_alerts
            ORDER BY check_ts DESC, severity DESC
            LIMIT %s
        """, (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows


def get_revenue_quality_by_city(days: int = 7) -> List[Dict[str, Any]]:
    """Resumen de calidad de revenue por ciudad (últimos N días desde day_v2)."""
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT country, city,
                   SUM(completed_trips) AS completed,
                   ROUND(SUM(gross_revenue)::numeric, 2) AS total_revenue,
                   CASE WHEN SUM(completed_trips) > 0
                       THEN ROUND(SUM(gross_revenue)::numeric / SUM(completed_trips), 2)
                       ELSE NULL
                   END AS avg_revenue,
                   CASE WHEN SUM(gross_revenue) > 0 THEN 'healthy'
                        WHEN SUM(completed_trips) > 0 THEN 'zero_revenue'
                        ELSE 'no_data'
                   END AS status
            FROM ops.mv_real_lob_day_v2
            WHERE trip_date >= CURRENT_DATE - make_interval(days => %s)
            GROUP BY country, city
            HAVING SUM(completed_trips) > 0
            ORDER BY SUM(completed_trips) DESC
        """, (days,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows
