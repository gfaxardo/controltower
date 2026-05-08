"""
FASE 4.2 / 4.2B — Sugerencias contextualizadas auditables (Omniview vs Proyección).

Solo lectura / inferencia; no ejecuta acciones, ni APIs externas, sin side effects.
Usa el DRIVER_SEGMENT_REGISTRY, MVs del ecosistema y métodos explícitos de recuperación.

Aditivo: no altera meta.suggestions; produce meta.contextual_suggestions aparte.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db
from app.services.driver_segment_registry import (
    SEGMENTS,
    SID_CASUAL_LOW_ENGAGEMENT,
    SID_DORMANT_14D,
    SID_DORMANT_30D,
    SID_ELITE_DEGRADED,
    SID_LOW_ACTIVITY_0_5_7D,
    SID_ONBOARDING_PENDING_FIRST_TRIP,
    all_registered_segment_ids,
    segment_public_meta,
)

logger = logging.getLogger(__name__)

TIMEOUT_MS = 20_000
_NS_CTX = uuid.UUID("7c9e6934-6cea-45b6-9f88-a5f4d8e3c001")

_REGISTERED_IDS = frozenset(all_registered_segment_ids())


@dataclass
class _RequestFetchCache:
    """Cache intra-request (mismo park set → una sola lectura pesada)."""

    pools: Dict[str, Any] = field(default_factory=dict)
    onboarding: Dict[str, Any] = field(default_factory=dict)
    recovery_baseline: Dict[str, Any] = field(default_factory=dict)


def _park_cache_key(park_ids: List[str]) -> str:
    if not park_ids:
        return "__no_park__"
    return "|".join(sorted({str(p) for p in park_ids}))


def _remaining_horizon_weeks(
    grain: str,
    filters: Optional[Dict[str, Any]],
) -> Tuple[int, str]:
    """
    Semanas restantes aproximadas para pacing de cierre de brecha YTD.
    No es calendario financiero exacto; solo ancla explícita auditável.
    """
    f = filters or {}
    month = int(f.get("month") or 0) or None
    year = int(f.get("year") or 0) or None
    g = (grain or "monthly").strip().lower()
    if month and year:
        remainder_m = max(0, 12 - month + 1)
        base = max(1, int(round(remainder_m * 4.33)))
        rationale = (
            f"aprox_weeks=ytd_residual_from_month(year={year},month={month}, "
            f"remainder_months_used={remainder_m}, grain_hint={g})"
        )
        return base, rationale
    return 12, f"grain={g}; filtros año/mes ausentes → horizonte default 12 semanas documentado"


def _cursor(conn: Any) -> Any:
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET statement_timeout = %s", (str(TIMEOUT_MS),))
    return c


def _stable_ctx_id(base_suggestion_id: str, action_type: str, entity: str) -> str:
    return str(uuid.uuid5(_NS_CTX, f"{base_suggestion_id}|{action_type}|{entity}"))


def _sf(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _si(x: Any) -> Optional[int]:
    f = _sf(x)
    if f is None:
        return None
    return int(round(f))


def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


def _merge_confidence(*vals: str) -> str:
    rank = {c: i for i, c in enumerate(["low", "medium", "high"])}
    m = min(rank.get(v, 1) for v in vals if v)
    return ["low", "medium", "high"][m]


def _row_public_label(r: Dict[str, Any]) -> str:
    c = str(r.get("city") or "").strip()
    b = str(r.get("business_slice_name") or "").strip()
    if c and b:
        return f"{c} - {b}"
    return c or b or ""


def _volume_affected_geos_from_alerts(
    alert: Dict[str, Any],
    ytd_alerts: Sequence[Dict[str, Any]],
) -> List[str]:
    """
    Ciudades / entidades con mayor brecha (mismo país, driver volumen).
    """
    co_a = _norm(alert.get("country"))
    scored: List[Tuple[float, str]] = []
    for a in ytd_alerts:
        if not isinstance(a, dict):
            continue
        if co_a and _norm(a.get("country")) != co_a:
            continue
        if _norm(a.get("principal_driver")) != "volume":
            continue
        gt = _sf(a.get("gap_trips"))
        if gt is None:
            continue
        label = str(a.get("city") or "").strip() or str(a.get("entity") or "").strip()
        if label:
            scored.append((abs(gt), label))
    scored.sort(key=lambda x: -x[0])
    out: List[str] = []
    seen: set = set()
    for _, lab in scored:
        key = lab.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(lab)
        if len(out) >= 8:
            break
    return out


def _pick_comparable_slice_labels(
    alert: Dict[str, Any],
    display_rows: Sequence[Dict[str, Any]],
    *,
    limit: int = 8,
) -> List[str]:
    co = _norm(alert.get("country"))
    lob = _norm(alert.get("business_slice"))
    ent_here = _norm(str(alert.get("entity") or ""))
    out: List[str] = []
    seen: set = set()
    for r in display_rows:
        if co and _norm(r.get("country")) != co:
            continue
        if lob and _norm(r.get("business_slice_name")) != lob:
            continue
        lab = _row_public_label(r)
        if not lab or _norm(lab) == ent_here:
            continue
        if lab.lower() in seen:
            continue
        seen.add(lab.lower())
        out.append(lab)
        if len(out) >= limit:
            break
    return out


def _rows_for_alert(
    alert: Dict[str, Any],
    display_rows: Sequence[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    co_a = _norm(alert.get("country"))
    ci_a = _norm(alert.get("city"))
    lob_a = _norm(alert.get("business_slice"))
    dim = _norm(alert.get("dimension"))
    out: List[Dict[str, Any]] = []
    for r in display_rows:
        rco = _norm(r.get("country"))
        rci = _norm(r.get("city"))
        rlob = _norm(r.get("business_slice_name"))
        if co_a and rco != co_a:
            continue
        if dim in ("city", "lob") and ci_a and rci != ci_a:
            continue
        if dim == "lob" and lob_a and rlob != lob_a:
            continue
        out.append(r)
    return out


def _aggregate_slice_metrics(
    rows: Sequence[Dict[str, Any]],
    ytd_summary: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Agrega métricas YTD desde ytd_slice de filas o meta.ytd_summary."""
    if rows:
        best: Optional[Dict[str, Any]] = None
        best_trips = -1.0
        for r in rows:
            ys = r.get("ytd_slice")
            if not isinstance(ys, dict):
                continue
            tr = _sf(ys.get("ytd_real_trips")) or 0.0
            if tr >= best_trips:
                best_trips = tr
                best = ys
        if best:
            return {
                "driver_productivity_ytd_real": best.get("driver_productivity_ytd_real"),
                "driver_productivity_ytd_expected": best.get("driver_productivity_ytd_expected"),
                "ytd_avg_active_drivers_real": best.get("ytd_avg_active_drivers_real"),
                "ytd_avg_active_drivers_expected": best.get("ytd_avg_active_drivers_expected"),
                "ytd_real_trips": best.get("ytd_real_trips"),
                "ytd_plan_expected_trips": best.get("ytd_plan_expected_trips"),
                "ytd_gap_trips": best.get("ytd_gap_trips"),
            }
    if isinstance(ytd_summary, dict) and not ytd_summary.get("error"):
        return {
            "driver_productivity_ytd_real": ytd_summary.get("driver_productivity_ytd_real"),
            "driver_productivity_ytd_expected": ytd_summary.get("driver_productivity_ytd_expected"),
            "ytd_avg_active_drivers_real": ytd_summary.get("ytd_avg_active_drivers_real"),
            "ytd_avg_active_drivers_expected": ytd_summary.get("ytd_avg_active_drivers_expected"),
            "ytd_real_trips": ytd_summary.get("ytd_real_trips"),
            "ytd_plan_expected_trips": ytd_summary.get("ytd_plan_expected_trips"),
            "ytd_gap_trips": ytd_summary.get("ytd_gap_trips"),
        }
    return {}


def _matview_exists(conn: Any, name: str) -> bool:
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM pg_matviews
            WHERE schemaname = 'ops' AND matviewname = %s
            LIMIT 1
            """,
            (name,),
        )
        ok = cur.fetchone() is not None
        cur.close()
        return ok
    except Exception:
        return False


def _view_exists(conn: Any, name: str) -> bool:
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT 1 FROM information_schema.views
            WHERE table_schema = 'ops' AND table_name = %s
            LIMIT 1
            """,
            (name,),
        )
        ok = cur.fetchone() is not None
        cur.close()
        return ok
    except Exception:
        return False


def _resolve_park_ids(conn: Any, country: Optional[str], city: Optional[str]) -> List[str]:
    ids: List[str] = []
    try:
        cur = _cursor(conn)
        if city and str(city).strip():
            cur.execute(
                """
                SELECT park_id FROM ops.v_dim_park_resolved
                WHERE (%s IS NULL OR TRIM(COALESCE(country, '')) ILIKE '%%' || TRIM(%s) || '%%')
                  AND LOWER(TRIM(COALESCE(city, ''))) = LOWER(TRIM(%s))
                  AND park_id IS NOT NULL
                """,
                (country, str(country or "").strip(), str(city).strip()),
            )
        elif country and str(country).strip():
            cur.execute(
                """
                SELECT park_id FROM ops.v_dim_park_resolved
                WHERE TRIM(COALESCE(country, '')) ILIKE '%%' || TRIM(%s) || '%%'
                  AND park_id IS NOT NULL
                """,
                (str(country).strip(),),
            )
        else:
            cur.close()
            return []
        ids = [str(r["park_id"]) for r in cur.fetchall() if r.get("park_id")]
        cur.close()
    except Exception as exc:
        logger.debug("contextual_suggestions park resolve: %s", exc)
    return list(dict.fromkeys(ids))


def _fetch_recovery_baseline_aggregate(
    conn: Any,
    park_ids: List[str],
) -> Optional[Dict[str, Any]]:
    """Reactivaciones semanales históricas (parks agregados)."""
    if not park_ids:
        return None
    if not _view_exists(conn, "v_driver_weekly_churn_reactivation"):
        return None
    if not _matview_exists(conn, "mv_driver_weekly_stats"):
        return None
    try:
        cur = _cursor(conn)
        cur.execute(
            """
            WITH recent AS (
              SELECT DISTINCT week_start
              FROM ops.mv_driver_weekly_stats
              WHERE park_id = ANY(%s)
              ORDER BY week_start DESC
              LIMIT 8
            )
            SELECT
              COALESCE(AVG(cnt_react), 0)::float AS avg_reactivated_drivers,
              COALESCE(AVG(cnt_tp), 0)::float AS avg_trips_completed,
              COUNT(*)::int AS sample_weeks
            FROM recent r
            LEFT JOIN (
              SELECT
                week_start,
                COUNT(*) FILTER (WHERE reactivated_week)::numeric AS cnt_react,
                SUM(trips_completed_week)::numeric AS cnt_tp,
                COUNT(DISTINCT driver_key)::numeric AS drivers_w
              FROM ops.v_driver_weekly_churn_reactivation
              WHERE park_id = ANY(%s)
              GROUP BY week_start
            ) x ON x.week_start = r.week_start
            """,
            (park_ids, park_ids),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            return None
        d = float(row["avg_reactivated_drivers"] or 0)
        tp = float(row["avg_trips_completed"] or 0)
        sample_weeks = int(row["sample_weeks"] or 0)

        avg_tpd: Optional[float] = None
        cur2 = _cursor(conn)
        cur2.execute(
            """
            WITH recent AS (
              SELECT DISTINCT week_start
              FROM ops.mv_driver_weekly_stats
              WHERE park_id = ANY(%s)
              ORDER BY week_start DESC LIMIT 8
            )
            SELECT
              AVG(trips)::float AS avg_tpd
            FROM (
              SELECT
                w.week_start,
                SUM(w.trips_completed_week)::numeric
                  / NULLIF(COUNT(DISTINCT w.driver_key), 0) AS trips
              FROM ops.mv_driver_weekly_stats w
              JOIN recent r ON r.week_start = w.week_start
              WHERE w.park_id = ANY(%s)
              GROUP BY w.week_start
            ) q
            """,
            (park_ids, park_ids),
        )
        tr = cur2.fetchone()
        cur2.close()
        avg_tpd = float(tr["avg_tpd"]) if tr and tr.get("avg_tpd") is not None else None
        cur.close()
        return {
            "avg_reactivated_drivers_weekly": d,
            "avg_trips_completed_week_aggregate": tp,
            "avg_tpd_in_sample_weeks": avg_tpd,
            "sample_weeks": sample_weeks,
            "historical_reference_window": "last_8_distinct_weeks_with_park_activity",
            "data_sources": ["ops.v_driver_weekly_churn_reactivation", "ops.mv_driver_weekly_stats"],
        }
    except Exception as exc:
        logger.debug("recovery_baseline fetch: %s", exc)
        return None


def _fetch_driver_pool_bundle(conn: Any, park_ids: List[str]) -> Optional[Dict[str, Any]]:
    if not park_ids:
        return None
    if not _matview_exists(conn, "mv_driver_lifecycle_base"):
        return None
    if not _matview_exists(conn, "mv_driver_weekly_stats"):
        return None
    try:
        cur = _cursor(conn)
        cur.execute(
            """
            SELECT MAX(week_start) AS ws
            FROM ops.mv_driver_weekly_stats
            WHERE park_id = ANY(%s)
            """,
            (park_ids,),
        )
        row = cur.fetchone()
        ws = row["ws"] if row else None
        if not ws:
            cur.close()
            return None
        cur.execute(
            """
            SELECT
              COUNT(DISTINCT w.driver_key) FILTER (
                WHERE w.trips_completed_week BETWEEN 0 AND 5
              )::int AS low_activity,
              COUNT(DISTINCT w.driver_key) FILTER (
                WHERE LOWER(TRIM(COALESCE(w.work_mode_week::text, ''))) IN ('casual','c','pt')
                  AND w.trips_completed_week BETWEEN 0 AND 2
              )::int AS casual_low,
              COUNT(DISTINCT w.driver_key) FILTER (
                WHERE LOWER(TRIM(COALESCE(w.work_mode_week::text, ''))) = 'ft'
                  AND w.trips_completed_week >= 6
              )::int AS ft_active
            FROM ops.mv_driver_weekly_stats w
            WHERE w.park_id = ANY(%s) AND w.week_start = %s::date
            """,
            (park_ids, ws),
        )
        low_row = cur.fetchone() or {}

        mode_mix: Optional[Dict[str, int]] = None
        try:
            cur.execute(
                """
                SELECT
                  COUNT(DISTINCT w.driver_key) FILTER (
                    WHERE LOWER(TRIM(COALESCE(w.work_mode_week::text, ''))) = 'ft'
                  )::int AS ft_drivers,
                  COUNT(DISTINCT w.driver_key) FILTER (
                    WHERE LOWER(TRIM(COALESCE(w.work_mode_week::text, ''))) = 'pt'
                  )::int AS pt_drivers,
                  COUNT(DISTINCT w.driver_key) FILTER (
                    WHERE LOWER(TRIM(COALESCE(w.work_mode_week::text, ''))) IN ('casual', 'c')
                  )::int AS casual_drivers
                FROM ops.mv_driver_weekly_stats w
                WHERE w.park_id = ANY(%s) AND w.week_start = %s::date
                """,
                (park_ids, ws),
            )
            mx = cur.fetchone() or {}
            mode_mix = {
                "FT": int(mx.get("ft_drivers") or 0),
                "PT": int(mx.get("pt_drivers") or 0),
                "casual": int(mx.get("casual_drivers") or 0),
            }
        except Exception:
            mode_mix = None

        cur.execute(
            """
            SELECT COUNT(*)::int AS n
            FROM ops.mv_driver_lifecycle_base b
            LEFT JOIN public.drivers d ON d.driver_id = b.driver_key
            WHERE COALESCE(d.park_id, b.driver_park_id) = ANY(%s)
              AND b.last_completed_ts IS NOT NULL
              AND b.last_completed_ts::date < (CURRENT_DATE - INTERVAL '14 days')
            """,
            (park_ids,),
        )
        dorm14 = int((cur.fetchone() or {}).get("n") or 0)

        cur.execute(
            """
            SELECT COUNT(*)::int AS n
            FROM ops.mv_driver_lifecycle_base b
            LEFT JOIN public.drivers d ON d.driver_id = b.driver_key
            WHERE COALESCE(d.park_id, b.driver_park_id) = ANY(%s)
              AND (
                b.last_completed_ts IS NULL
                OR b.last_completed_ts::date < (CURRENT_DATE - INTERVAL '30 days')
              )
            """,
            (park_ids,),
        )
        dorm30 = int((cur.fetchone() or {}).get("n") or 0)

        elite = 0
        sources = [
            "ops.mv_driver_lifecycle_base",
            "ops.mv_driver_weekly_stats",
        ]
        if _view_exists(conn, "v_action_engine_driver_base"):
            sources.append("ops.v_action_engine_driver_base")
            cur.execute(
                """
                SELECT COUNT(DISTINCT driver_key)::int AS n
                FROM ops.v_action_engine_driver_base
                WHERE week_start = (
                    SELECT MAX(week_start) FROM ops.v_action_engine_driver_base
                    WHERE park_id = ANY(%s)
                )
                  AND park_id = ANY(%s)
                  AND cohort_type IN (
                    'high_value_deteriorating',
                    'high_value_recovery_candidates',
                    'near_drop_risk'
                  )
                """,
                (park_ids, park_ids),
            )
            er = cur.fetchone()
            elite = int(er["n"] or 0) if er else 0

        low = int(low_row.get("low_activity") or 0)
        casual_low = int(low_row.get("casual_low") or 0)
        ft = int(low_row.get("ft_active") or 0)

        cur.execute(
            """
            SELECT COUNT(DISTINCT w.driver_key)::int AS n
            FROM ops.mv_driver_weekly_stats w
            INNER JOIN ops.mv_driver_lifecycle_base b ON b.driver_key = w.driver_key
            LEFT JOIN public.drivers d ON d.driver_id = b.driver_key
            WHERE w.park_id = ANY(%s)
              AND w.week_start = %s::date
              AND COALESCE(d.park_id, b.driver_park_id) = ANY(%s)
              AND (
                w.trips_completed_week >= 1
                OR (
                  b.registered_ts IS NOT NULL
                  AND b.registered_ts::date >= (CURRENT_DATE - INTERVAL '60 days')
                )
              )
            """,
            (park_ids, ws, park_ids),
        )
        reachable = int((cur.fetchone() or {}).get("n") or 0)
        total_sum = low + dorm14 + dorm30 + elite + casual_low
        reachable_c = min(reachable, total_sum) if total_sum else reachable

        cur.close()

        segments_raw = [
            (SID_LOW_ACTIVITY_0_5_7D, low),
            (SID_DORMANT_14D, dorm14),
            (SID_DORMANT_30D, dorm30),
            (SID_ELITE_DEGRADED, elite),
            (SID_CASUAL_LOW_ENGAGEMENT, casual_low),
        ]
        segments = [
            {
                "segment_id": sid,
                "drivers": cnt,
                "display_name": segment_public_meta(sid)["display_name"],
            }
            for sid, cnt in segments_raw
            if cnt > 0
        ]
        if not segments:
            segments = [
                {
                    "segment_id": SID_LOW_ACTIVITY_0_5_7D,
                    "drivers": 0,
                    "display_name": segment_public_meta(SID_LOW_ACTIVITY_0_5_7D)["display_name"],
                }
            ]

        operability_notes: List[str] = [
            "total_candidates es suma de buckets de segmentación; pueden existir solapes entre sí.",
            "contactable_pct no disponible sin fuente canónica CRM/Reachability.",
        ]
        opr = {
            "contactable_pct": None,
            "recently_active_pct": round(100.0 * reachable / max(total_sum, 1), 2) if total_sum else None,
            "blocked_or_unreachable_pct": round(100.0 * max(0, total_sum - reachable_c) / max(total_sum, 1), 2)
            if total_sum
            else None,
            "notes": operability_notes,
        }

        return {
            "total_candidates": total_sum,
            "reachable_candidates": max(0, reachable_c),
            "segments_detail": segments,
            "pool_method": "database_parks_latest_week",
            "data_sources": sources,
            "ft_active_sample": ft,
            "weekly_mode_mix": mode_mix,
            "week_anchor": str(ws),
            "operability": opr,
            "sample_size_weekly_anchor_drivers_observed": int(sum(s["drivers"] for s in segments if s["segment_id"] != SID_DORMANT_30D)),
        }
    except Exception as exc:
        logger.warning("contextual_suggestions driver pool DB: %s", exc, exc_info=True)
        return None


def _fetch_pending_onboarding_db(conn: Any, park_ids: List[str]) -> Optional[Dict[str, Any]]:
    if not park_ids or not _matview_exists(conn, "mv_driver_lifecycle_base"):
        return None
    try:
        cur = _cursor(conn)
        cur.execute(
            """
            SELECT
              COUNT(*)::int AS pending,
              ROUND(AVG(GREATEST(0, EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - b.registered_ts)) / 86400.0))::numeric, 1) AS avg_age_days
            FROM ops.mv_driver_lifecycle_base b
            LEFT JOIN public.drivers d ON d.driver_id = b.driver_key
            WHERE COALESCE(d.park_id, b.driver_park_id) = ANY(%s)
              AND b.registered_ts IS NOT NULL
              AND (b.activation_ts IS NULL OR b.total_trips_completed = 0)
              AND b.registered_ts >= (CURRENT_DATE - INTERVAL '120 days')
            """,
            (park_ids,),
        )
        r = cur.fetchone()
        cur.close()
        if not r:
            return None
        return {
            "pending_registrations": int(r["pending"] or 0),
            "avg_pending_age_days": float(r["avg_age_days"]) if r["avg_age_days"] is not None else None,
        }
    except Exception as exc:
        logger.debug("contextual_suggestions onboarding: %s", exc)
        return None


def _fallback_pool_productivity(m: Dict[str, Any], alert: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sin MV lifecycle: solo bound operativo mínimo declarado (no pretende desagregar cohortes reales).
    """
    ad = _sf(m.get("ytd_avg_active_drivers_real"))
    pe = _sf(m.get("driver_productivity_ytd_expected"))
    gap_t = _sf(alert.get("gap_trips"))
    base_drv = int(ad) if ad and ad > 0 else None
    pacing_drv = None
    if gap_t is not None and pe and pe > 0:
        pacing_drv = max(0, int(round(abs(gap_t) / pe)))
    total = max(base_drv or 0, pacing_drv or 0, 1)
    segs_detail = [
        {
            "segment_id": SID_LOW_ACTIVITY_0_5_7D,
            "drivers": total,
            "display_name": segment_public_meta(SID_LOW_ACTIVITY_0_5_7D)["display_name"],
        }
    ]
    return {
        "total_candidates": total,
        "reachable_candidates": total,
        "segments_detail": segs_detail,
        "pool_method": "fallback_active_drivers_or_gap_norm_max_bound",
        "data_sources": [],
        "notes": [
            "Sin ops.mv_driver_lifecycle_base / mv_driver_weekly_stats: no hay segmentación real;",
            "total_candidates=max(ytd_avg_active_drivers_real, ceil(|gap_trips|/TPD_esperado),1) como upper bound declarado;",
            "solo se emite segmento oficial low_activity como proxy único hasta existan MVs.",
        ],
        "operability": {
            "contactable_pct": None,
            "recently_active_pct": None,
            "blocked_or_unreachable_pct": None,
            "notes": ["Operabilidad no medible sin funnel lifecycle semanal"],
        },
    }


def _productivity_attribution_gap_trips(ytd_summary: Optional[Dict[str, Any]]) -> Tuple[float, str]:
    if not isinstance(ytd_summary, dict) or ytd_summary.get("error"):
        return 1.0, "sin descomposición YTD disponible → atribución 100% implícita (revisar con meta.gap_decomposition)"
    gd = ytd_summary.get("gap_decomposition")
    basis: Dict[str, Any] = {}
    if isinstance(gd, dict):
        basis = gd.get("basis") if isinstance(gd.get("basis"), dict) else gd
    for k in ("productivity_share_in_gap", "productivity_share", "share_productivity"):
        v = basis.get(k)
        if v is not None:
            try:
                f = float(v)
                if 0.0 <= f <= 1.0:
                    return f, f"gap_decomposition.{k}"
                if 0.0 <= f <= 100.0:
                    return f / 100.0, f"gap_decomposition.{k}_as_pct"
            except (TypeError, ValueError):
                pass
    return 1.0, "sin campo productivity_share en gap_decomposition (asumir atribución 1.0 documentada)"


def _compute_leverage_breakdown(
    *,
    total_candidates: int,
    reachable: int,
    gap_recovery_pct: Optional[float],
    pool_from_db: bool,
    action_type: str,
    speed_hint: str,
    expected_impact_hint: str,
) -> Tuple[int, Dict[str, Any]]:
    pool_size_score = min(40.0, total_candidates / 15.0)
    reach_ratio = reachable / max(total_candidates, 1) if total_candidates else 0.0
    recoverability_score = min(30.0, (abs(gap_recovery_pct or 0) * 4.0)) if gap_recovery_pct is not None else 8.0
    data_confidence = 25.0 if pool_from_db else 10.0
    speed_map = {"fast": 18.0, "medium": 12.0, "slow": 6.0}
    speed_score = speed_map.get(speed_hint, 10.0)
    complexity_penalty = 10.0 if action_type in ("ticket_mix_review", "data_review") else 4.0
    impact_map = {"high": 20.0, "medium": 12.0, "low": 6.0}
    expected_impact_score = impact_map.get(expected_impact_hint, 10.0)
    operational_complexity_score = max(0.0, 25.0 - complexity_penalty)
    raw = (
        pool_size_score
        + min(15.0, reach_ratio * 15.0)
        + recoverability_score
        + data_confidence
        + speed_score
        + operational_complexity_score
        + expected_impact_score
        - complexity_penalty
    )
    total = int(max(0, min(100, round(raw / 2.2))))
    return total, {
        "pool_size_score": round(pool_size_score, 2),
        "recoverability_score": round(recoverability_score, 2),
        "speed_score": round(speed_score, 2),
        "operational_complexity_score": round(operational_complexity_score, 2),
        "expected_impact_score": round(expected_impact_score, 2),
        "reachability_weight": round(min(15.0, reach_ratio * 15.0), 2),
        "data_freshness_weight": round(data_confidence, 2),
        "notes": "Suma ponderada heurística de priorización (no impacto financiero garantizado).",
    }


def _recovery_productivity_gap_projection_v1(
    *,
    alert: Dict[str, Any],
    pool_reachable: int,
    prod_real: Optional[float],
    prod_exp: Optional[float],
    ytd_summary: Optional[Dict[str, Any]],
    grain: str,
    filters: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    gap_trips = _sf(alert.get("gap_trips"))
    weeks, wnote = _remaining_horizon_weeks(grain, filters)
    share, share_note = _productivity_attribution_gap_trips(ytd_summary)
    attributed = abs(gap_trips or 0.0) * share if gap_trips is not None else None
    weekly_pace = round(attributed / max(weeks, 1), 2) if attributed is not None else None
    implied_by_tpd = None
    if prod_real is not None and prod_exp is not None and prod_exp > 0 and pool_reachable > 0:
        delta = max(0.0, prod_exp - prod_real)
        implied_by_tpd = round(pool_reachable * delta, 2)
    cap_ref = implied_by_tpd if implied_by_tpd is not None else None
    potential_weekly = weekly_pace
    if cap_ref is not None and weekly_pace is not None:
        potential_weekly = min(weekly_pace, cap_ref)
    elif cap_ref is not None:
        potential_weekly = cap_ref
    gap_pct_recovery = None
    if gap_trips and attributed is not None and gap_trips != 0 and potential_weekly is not None:
        gap_pct_recovery = min(100.0, max(0.0, (potential_weekly * max(weeks, 1) / abs(gap_trips)) * 100.0))
    conf_reason = []
    conf = "medium"
    if weekly_pace is None or gap_trips is None:
        conf = "low"
        conf_reason.append("falta gap_trips o no se puede anclar pacing")
    if share < 1.0:
        conf_reason.append(f"share={share:.2f} vía {share_note}")
    elif "sin campo" in share_note:
        conf = _merge_confidence(conf, "low")
        conf_reason.append(share_note)
    if prod_real is not None and prod_exp is not None and prod_exp > 0 and abs(prod_exp - prod_real) / prod_exp > 0.08:
        conf = _merge_confidence(conf, "high")
        conf_reason.append("brecha TPD material vs plan")
    assumptions = [
        wnote,
        share_note,
        "Pacing lineal: |gap_trips|×atribución / semanas_restantes_aprox; tope opcional pool×(TPD_esperado−TPD_real) si ambos existen.",
    ]
    return {
        "potential_trips_recovered_weekly": round(potential_weekly) if potential_weekly is not None else None,
        "potential_gap_recovery_pct": round(gap_pct_recovery, 2) if gap_pct_recovery is not None else None,
        "recovery_method": "productivity_gap_projection_v1",
        "assumptions_used": assumptions,
        "confidence": conf,
        "confidence_reason": "; ".join(conf_reason) if conf_reason else "modelo de pacing + TPD coherentes con alerta",
        "historical_reference_window": f"synthetic_horizon_{weeks}w",
        "sample_size": pool_reachable,
    }


def _recovery_dormant_historical_baseline_v1(
    baseline: Optional[Dict[str, Any]],
    dormant_pool: int,
) -> Dict[str, Any]:
    if not baseline or baseline.get("sample_weeks", 0) <= 0:
        return {
            "potential_trips_recovered_weekly": None,
            "potential_gap_recovery_pct": None,
            "recovery_method": "dormant_reactivation_baseline_v1",
            "assumptions_used": [
                "vista ops.v_driver_weekly_churn_reactivation o MVs no disponibles; sin baseline histórico agregado",
            ],
            "confidence": "low",
            "confidence_reason": "sin muestra semanal de reactivaciones en parks",
            "historical_reference_window": "n/a",
            "sample_size": dormant_pool,
        }
    ar = float(baseline.get("avg_reactivated_drivers_weekly") or 0)
    tpd = baseline.get("avg_tpd_in_sample_weeks")
    sw = int(baseline.get("sample_weeks") or 0)
    tpd_f = float(tpd) if tpd is not None else None
    trips_hat = ar * tpd_f if tpd_f is not None else None
    assumptions = [
        f"Ventana ops: {baseline.get('historical_reference_window')} ({sw} semanas)",
        "Estimación: reactivaciones históricas promedio semanal × TPD medio en misma ventana (cohorte parks filtrados).",
        "No modela efectividad incremental de una acción concreta.",
    ]
    if trips_hat is None or dormant_pool <= 0:
        return {
            "potential_trips_recovered_weekly": None,
            "potential_gap_recovery_pct": None,
            "recovery_method": "dormant_reactivation_baseline_v1",
            "assumptions_used": assumptions + (["avg_tpd_in_sample_weeks ausente"] if tpd_f is None else []),
            "confidence": "low",
            "confidence_reason": "falta TPD medio histórico o pool dormido=0",
            "historical_reference_window": str(baseline.get("historical_reference_window") or ""),
            "sample_size": max(sw, dormant_pool),
        }
    conf = "medium" if sw >= 4 else "low"
    return {
        "potential_trips_recovered_weekly": round(trips_hat),
        "potential_gap_recovery_pct": None,
        "recovery_method": "dormant_reactivation_baseline_v1",
        "assumptions_used": assumptions,
        "confidence": conf,
        "confidence_reason": "baseline observada churn/reactivation × TPD semanal promedio",
        "historical_reference_window": str(baseline.get("historical_reference_window") or ""),
        "sample_size": max(sw, dormant_pool),
    }


def _recovery_onboarding_conversion_baseline_v1(
    pending: int,
    onboarding: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Banda documentada de producto (no sustituye histórico por cohorte hasta conectar pipeline).
    """
    lo, hi = 0.12, 0.22
    mid = (lo + hi) / 2.0
    weekly = round(pending * mid, 2)
    assumptions = [
        "Banda conversión registrada a primer viaje (control_tower_policy_band_v1): 12%–22% anualizada simplificada a punto medio 17% como escenario único semana-referencia.",
        "Pendiente conectar a histórico real por park vía pipeline onboarding (FASE futura).",
    ]
    if onboarding and onboarding.get("pending_registrations"):
        assumptions.append(
            f"pending_registrations MV lifecycle (120d lookback)={onboarding.get('pending_registrations')}"
        )
    conf = "low" if pending < 30 else "medium"
    return {
        "potential_trips_recovered_weekly": round(weekly) if pending else None,
        "potential_gap_recovery_pct": None,
        "recovery_method": "onboarding_conversion_baseline_v1",
        "assumptions_used": assumptions,
        "confidence": conf,
        "confidence_reason": "bandwidth estática documentada; volumen bajo reduce confianza",
        "historical_reference_window": "policy_band_static_v1",
        "sample_size": pending,
    }


def _recovery_historical_low_activity_recovery_v1(
    baseline: Optional[Dict[str, Any]],
    low_pool: int,
) -> Dict[str, Any]:
    out = _recovery_dormant_historical_baseline_v1(baseline, low_pool)
    out["recovery_method"] = "historical_low_activity_recovery_v1"
    out["assumptions_used"] = (out.get("assumptions_used") or []) + [
        "Proxy: misma señal agregada de reactivaciones semanales que dormant_baseline (vista churn); interpretación para low_activity sujeta a validación ops.",
    ]
    return out


def _recovery_volume_pacing_v1(
    gap_trips: Optional[float],
    weeks: int,
    pending: int,
    baseline: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    gt = abs(gap_trips or 0.0)
    pace = round(gt / max(weeks, 1), 2) if gt else None
    assumptions = [
        "Componente A: pacing lineal |gap_trips|/horizonte semanas (volumen).",
        "Componente B (opcional): pending×mid conversión si baseline onboarding no histórico.",
    ]
    extra = 0.0
    if pending > 0:
        extra = pending * 0.17
    combined = None
    if pace is not None:
        combined = pace + extra
    sample = baseline.get("sample_weeks") if baseline else None
    return {
        "potential_trips_recovered_weekly": round(combined) if combined is not None else None,
        "potential_gap_recovery_pct": min(100.0, (combined or 0) * max(weeks, 1) / max(gt, 1.0) * 100.0)
        if combined and gt
        else None,
        "recovery_method": "volume_supply_pacing_plus_onboarding_band_v1",
        "assumptions_used": assumptions,
        "confidence": "medium" if pending or gt else "low",
        "confidence_reason": "mezcla pacing YTD + escenario onboarding policy band",
        "historical_reference_window": f"{weeks}w_synthetic_horizon",
        "sample_size": int(sample or pending or 0),
    }


def _recovery_ticket_review_v1(alert: Dict[str, Any]) -> Dict[str, Any]:
    gp = _sf(alert.get("gap_pct"))
    return {
        "potential_trips_recovered_weekly": None,
        "potential_gap_recovery_pct": round(min(100.0, abs(gp or 0) * 0.25), 2) if gp is not None else None,
        "recovery_method": "ticket_mix_review_no_numeric_trips_v1",
        "assumptions_used": [
            "Acción analítica: no se proyectan viajes sin modelo de elasticidad ticket×demanda.",
            "potential_gap_recovery_pct es orden de magnitud ilustrativo respecto gap_pct de alerta (no ingreso).",
        ],
        "confidence": "low",
        "confidence_reason": "sin pipeline econométrico ticket",
        "historical_reference_window": "n/a",
        "sample_size": 0,
    }


def _recovery_opportunity_v1(alert: Dict[str, Any], comp_n: int) -> Dict[str, Any]:
    gp = _sf(alert.get("gap_pct"))
    return {
        "potential_trips_recovered_weekly": None,
        "potential_gap_recovery_pct": round(abs(gp), 2) if gp is not None else None,
        "recovery_method": "opportunity_replicate_qualitative_v1",
        "assumptions_used": ["Réplica operativa no cuantificada sin experimento controlado."],
        "confidence": "high" if comp_n >= 2 else "medium",
        "confidence_reason": "comparables en omniview" if comp_n >= 2 else "pocos slices comparables",
        "historical_reference_window": "n/a",
        "sample_size": comp_n,
    }


def _suggested_focus(segments: List[Dict[str, Any]], action_type: str) -> List[str]:
    focuses: List[str] = []
    top = sorted(segments, key=lambda s: -int(s.get("drivers") or 0))[:3]
    for s in top:
        sid = str(s.get("segment_id") or "")
        n = int(s.get("drivers") or 0)
        if n <= 0:
            continue
        if sid == SID_LOW_ACTIVITY_0_5_7D:
            focuses.append("reactivar low_activity")
        elif sid == SID_DORMANT_14D:
            focuses.append("despertar dormant_14d")
        elif sid == SID_DORMANT_30D:
            focuses.append("rescatar dormant_30d")
        elif sid == SID_ELITE_DEGRADED:
            focuses.append("recuperar elite_degraded")
        elif sid == SID_CASUAL_LOW_ENGAGEMENT:
            focuses.append("elevar casual / PT")
        elif sid == SID_ONBOARDING_PENDING_FIRST_TRIP:
            focuses.append("convertir onboarding pendiente")
    if not focuses and action_type.startswith("volume"):
        focuses.append("acelerar funnel a primer viaje")
    return focuses[:5]


def _build_contextual_reasoning(
    *,
    alert: Dict[str, Any],
    m: Dict[str, Any],
    pool: Dict[str, Any],
    action_type: str,
    ytd_summary: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    pacing = str(alert.get("pacing_vs_expected") or "—")
    trend = str(alert.get("ytd_trend") or "—")
    pr = _sf(m.get("driver_productivity_ytd_real"))
    pe = _sf(m.get("driver_productivity_ytd_expected"))
    gap_t = _sf(alert.get("gap_trips")) or _sf(m.get("ytd_gap_trips"))
    vol_gap_drv = None
    exd = _sf(m.get("ytd_avg_active_drivers_expected"))
    rd = _sf(m.get("ytd_avg_active_drivers_real"))
    if exd is not None and rd is not None:
        vol_gap_drv = round(exd - rd, 2)
    atr = _sf(ytd_summary.get("ytd_avg_ticket_real")) if isinstance(ytd_summary, dict) else None
    ate = _sf(ytd_summary.get("ytd_avg_ticket_expected")) if isinstance(ytd_summary, dict) else None
    ticket_gap = round(atr - ate, 4) if atr is not None and ate is not None else None
    total = int(pool.get("total_candidates") or 0)

    gap_trip = gap_t
    if gap_trip is not None:
        mp = (
            f"Pacing {pacing}, tendencia {trend}; brecha declarada gap_trips={gap_trip}; "
            f"principal_driver={alert.get('principal_driver')}."
        )
    else:
        mp = f"Pacing {pacing}, tendencia {trend}; driver={alert.get('principal_driver')}."
    why = f"Acción {action_type} alineada al driver de la alerta y al pool agregado ({total} conductores en segmentos considerados)."
    eff = "Efecto esperado declarado sólo como recuperación pacing / cohorte descrita en estimated_recovery (sin promesa)."
    constr: List[str] = []
    if pr is not None and pe is not None:
        constr.append(f"TPD Real {pr:.2f} vs Esperado {pe:.2f}")
    if vol_gap_drv is not None:
        constr.append(f"Brecha drivers YTD vs plan ~{vol_gap_drv}")
    if ticket_gap is not None:
        constr.append(f"Delta ticket R−E ~{ticket_gap}")
    return {
        "main_problem_detected": mp[:500],
        "why_this_action": why[:500],
        "expected_operational_effect": eff[:500],
        "main_constraints": constr[:8],
    }


def _build_operational_context_productivity(
    m: Dict[str, Any],
    pool: Dict[str, Any],
    alert: Dict[str, Any],
    action_type: str,
) -> Dict[str, Any]:
    pr, pe = _sf(m.get("driver_productivity_ytd_real")), _sf(m.get("driver_productivity_ytd_expected"))
    gap_pct = None
    if pr is not None and pe is not None and pe != 0:
        gap_pct = round((pr - pe) / abs(pe) * 100.0, 2)
    ad = _sf(m.get("ytd_avg_active_drivers_real"))
    low_share = None
    segs = pool.get("segments_detail") or pool.get("segments") or []
    tot = int(pool.get("total_candidates") or 1)
    low_n = next((int(s["drivers"]) for s in segs if s.get("segment_id") == SID_LOW_ACTIVITY_0_5_7D), 0)
    if tot > 0:
        low_share = round(100.0 * low_n / tot, 2)
    else:
        low_share = None
    ctx: Dict[str, Any] = {
        "current_driver_productivity": pr,
        "expected_driver_productivity": pe,
        "productivity_gap_pct": gap_pct,
        "active_drivers_ytd": round(ad, 2) if ad is not None else None,
        "low_activity_share_pct": low_share,
    }
    wm = pool.get("weekly_mode_mix")
    if isinstance(wm, dict) and any(int(wm.get(k) or 0) > 0 for k in ("FT", "PT", "casual")):
        ctx["weekly_mode_mix_active_drivers"] = wm
    if action_type == "productivity_incentive":
        pool_ft = pool.get("ft_active_sample")
        eligible = min(
            int(pool.get("total_candidates") or 0),
            int(pool_ft or 0) + int(pool.get("total_candidates") or 0) // 2,
        )
        ctx["eligible_drivers_for_incentive"] = max(0, eligible)
        ctx["elasticity_hint"] = "alta" if (gap_pct is not None and gap_pct < -15) else "media"
        ctx["incremental_trips_note"] = "Cuantificación auditada solo en estimated_recovery (sin multiplicadores ocultos en contexto)."
    return ctx


def _build_volume_context(
    m: Dict[str, Any],
    pool: Dict[str, Any],
    onboarding: Optional[Dict[str, Any]],
    alert: Dict[str, Any],
    action_type: str,
    geo_labels_prioritized: Sequence[str],
) -> Dict[str, Any]:
    exp_d = _sf(m.get("ytd_avg_active_drivers_expected"))
    real_d = _sf(m.get("ytd_avg_active_drivers_real"))
    gap_drv = None
    if exp_d is not None and real_d is not None:
        gap_drv = round(exp_d - real_d, 2)
    gap_trips = _sf(alert.get("gap_trips"))
    pace = None
    if gap_trips and gap_trips < 0:
        pace = round(abs(gap_trips) / 12.0, 1)
    geo_top = list(geo_labels_prioritized)[:3]
    ctx: Dict[str, Any] = {
        "estimated_supply_gap_drivers": gap_drv,
        "pending_first_trip_registrations": (onboarding or {}).get("pending_registrations"),
        "avg_pending_registration_age_days": (onboarding or {}).get("avg_pending_age_days"),
        "affected_geos_top": geo_top,
        "pace_registrations_needed_weekly_approx": pace,
        "expected_conversion_first_trip_pct_band": "12–22%",
    }
    if action_type == "volume_onboarding_followup":
        pend = (onboarding or {}).get("pending_registrations")
        if pend:
            ctx["registrations_pending_followup"] = pend
    return ctx


def _build_ticket_context(ytd_summary: Optional[Dict[str, Any]], m: Dict[str, Any]) -> Dict[str, Any]:
    atr = _sf(ytd_summary.get("ytd_avg_ticket_real")) if isinstance(ytd_summary, dict) else None
    ate = _sf(ytd_summary.get("ytd_avg_ticket_expected")) if isinstance(ytd_summary, dict) else None
    gd = (ytd_summary or {}).get("gap_decomposition") if isinstance(ytd_summary, dict) else None
    basis = {}
    if isinstance(gd, dict):
        basis = gd.get("basis") if isinstance(gd.get("basis"), dict) else gd
    ticket_eff = basis.get("ticket_effect_revenue") or basis.get("ticket_effect_trips")
    basis_signals: Dict[str, Any] = {}
    for k in (
        "dominant_gap_driver_code",
        "volume_share_in_gap",
        "ticket_share_in_gap",
        "productivity_share_in_gap",
    ):
        if k in basis:
            basis_signals[k] = basis[k]
    out = {
        "avg_ticket_real_ytd": atr,
        "avg_ticket_expected_ytd": ate,
        "avg_ticket_gap_pct": round((atr - ate) / ate * 100.0, 2)
        if atr is not None
        and ate is not None
        and ate != 0
        else None,
        "ticket_effect_in_gap": ticket_eff,
        "lob_mix_shift_note": "revisar si subió peso de líneas low-ticket"
        if (atr is not None and ate is not None and atr < ate)
        else None,
    }
    if basis_signals:
        out["gap_basis_signals"] = basis_signals
    return out


def _build_opportunity_narrative(
    alert: Dict[str, Any],
    base: Dict[str, Any],
    m: Dict[str, Any],
    display_rows: Sequence[Dict[str, Any]],
    ytd_summary: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    att = _sf(alert.get("ytd_attainment_pct"))
    if att is None and isinstance(ytd_summary, dict):
        att = _sf(ytd_summary.get("ytd_attainment_pct"))
    ent = str(alert.get("entity") or base.get("entity") or "")
    pr, pe = _sf(m.get("driver_productivity_ytd_real")), _sf(m.get("driver_productivity_ytd_expected"))
    prod_delta_pct: Optional[float] = None
    if pr is not None and pe is not None and pe != 0:
        prod_delta_pct = round((pr - pe) / abs(pe) * 100.0, 1)
    if prod_delta_pct is not None and prod_delta_pct >= 8.0:
        kpi = "productividad"
    elif att is not None and att >= 102.0:
        kpi = "cumplimiento"
    elif att is not None:
        kpi = "cumplimiento"
    else:
        kpi = "ejecución operativa"
    parts: List[str] = [f"{ent} está sobresaliendo en {kpi}"]
    if att is not None:
        parts.append(f"~{att:.1f}% YTD vs plan")
    if prod_delta_pct is not None:
        parts.append(f"productividad {prod_delta_pct:+.1f}% vs esperado")
    line = "; ".join(parts) + "."
    comparable_labels = _pick_comparable_slice_labels(alert, display_rows, limit=8)
    replication = (
        f"Slices comparables mismo LOB: {', '.join(comparable_labels[:4])}"
        if comparable_labels
        else "Comparar con otros slices mismo país / LOB en Omniview para estimar réplica."
    )
    return {
        "winner_slice_label": ent,
        "outperforming_kpi": kpi,
        "headline": line.strip(),
        "productivity_vs_expected_pct": prod_delta_pct,
        "comparable_slice_labels": comparable_labels,
        "replication_potential_hint": replication,
        "ytd_attainment_pct": att,
        "principal_driver_code": alert.get("principal_driver"),
    }


def _cache_pool_bundle(cache: _RequestFetchCache, conn: Any, park_ids: List[str]) -> Optional[Dict[str, Any]]:
    key = _park_cache_key(park_ids)
    if key not in cache.pools:
        cache.pools[key] = _fetch_driver_pool_bundle(conn, park_ids) if park_ids else None
    return cache.pools[key]


def _cache_onboarding(cache: _RequestFetchCache, conn: Any, park_ids: List[str]) -> Optional[Dict[str, Any]]:
    key = _park_cache_key(park_ids)
    if key not in cache.onboarding:
        cache.onboarding[key] = _fetch_pending_onboarding_db(conn, park_ids) if park_ids else None
    return cache.onboarding[key]


def _cache_recovery_baseline(cache: _RequestFetchCache, conn: Any, park_ids: List[str]) -> Optional[Dict[str, Any]]:
    key = _park_cache_key(park_ids)
    if key not in cache.recovery_baseline:
        cache.recovery_baseline[key] = (
            _fetch_recovery_baseline_aggregate(conn, park_ids) if park_ids else None
        )
    return cache.recovery_baseline[key]


def _derive_contextual_subchecks(items: List[Dict[str, Any]]) -> Dict[str, str]:
    seg_st = "ok"
    rec_st = "ok"
    pool_st = "ok"
    if not items:
        return {
            "segment_registry": "missing",
            "recovery_auditability": "missing",
            "operational_pool_quality": "missing",
        }
    for it in items:
        for sg in (it.get("operational_pool") or {}).get("segments") or []:
            sid = str(sg.get("segment_id") or "")
            if sid and sid not in _REGISTERED_IDS:
                seg_st = "missing"
            elif not sid:
                seg_st = "partial"
        er = it.get("estimated_recovery") or {}
        if not er.get("recovery_method"):
            rec_st = "missing"
        elif er.get("confidence_reason") in (None, ""):
            rec_st = "partial"
        elif not isinstance(er.get("assumptions_used"), list):
            rec_st = "partial"
        op = it.get("operational_pool") or {}
        if str(op.get("pool_method") or "").startswith("fallback"):
            pool_st = "partial"
        if op.get("reachable_candidates") is None and int(op.get("total_candidates") or 0) > 0:
            pool_st = "partial"
    return {
        "segment_registry": seg_st,
        "recovery_auditability": rec_st,
        "operational_pool_quality": pool_st,
    }


def _contextual_confidence(
    base_conf: str,
    integrity_status: Dict[str, Any],
    pool: Dict[str, Any],
    pool_from_db: bool,
    action_type: str,
) -> str:
    st = str(integrity_status.get("status") or "")
    c = base_conf
    total = int(pool.get("total_candidates") or 0)
    if st == "warning":
        c = _merge_confidence(c, "medium")
    if not pool_from_db or total <= 0:
        c = _merge_confidence(c, "medium")
    if action_type in ("data_review", "ticket_mix_review"):
        c = _merge_confidence(c, "medium")
    if total <= 0:
        c = _merge_confidence(c, "low")
    return c


def enrich_one_contextual_suggestion(
    *,
    base: Dict[str, Any],
    integrity_status: Dict[str, Any],
    ytd_alerts: Sequence[Dict[str, Any]],
    display_rows: Sequence[Dict[str, Any]],
    ytd_summary: Optional[Dict[str, Any]],
    conn: Any,
    req_cache: _RequestFetchCache,
    grain: Optional[str],
    filters: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], bool]:
    """
    Devuelve (payload contextual, partial_fail).

    partial_fail: falta MV onboarding / pool lifecycle pese a tener park_ids.
    """
    src_alert = base.get("source_alert")
    if not isinstance(src_alert, dict):
        src_alert = {}
    alert = src_alert
    action_type = str(base.get("recommended_action_id") or "")
    rows = _rows_for_alert(alert, display_rows)
    m = _aggregate_slice_metrics(rows, ytd_summary)

    country = alert.get("country")
    city = alert.get("city")
    park_ids = _resolve_park_ids(conn, str(country) if country else None, str(city) if city else None)

    onboarding = _cache_onboarding(req_cache, conn, park_ids)
    baseline = _cache_recovery_baseline(req_cache, conn, park_ids)

    pool_from_db = False
    pool: Optional[Dict[str, Any]] = None
    if park_ids:
        pool = _cache_pool_bundle(req_cache, conn, park_ids)
        pool_from_db = pool is not None

    if pool is None:
        if action_type in ("productivity_reactivation", "productivity_incentive", "data_review"):
            pool = _fallback_pool_productivity(m, alert)
        elif action_type in ("volume_scouts_push", "volume_onboarding_followup"):
            pend = onboarding["pending_registrations"] if onboarding else max(
                5, int(abs(_sf(alert.get("gap_trips")) or 0) // 80)
            )
            pool = {
                "total_candidates": pend,
                "reachable_candidates": pend,
                "segments_detail": [
                    {
                        "segment_id": SID_ONBOARDING_PENDING_FIRST_TRIP,
                        "drivers": pend,
                        "display_name": segment_public_meta(SID_ONBOARDING_PENDING_FIRST_TRIP)["display_name"],
                    }
                ],
                "pool_method": "fallback_onboarding_pending_or_gap_proxy",
                "data_sources": [],
                "operability": {
                    "contactable_pct": None,
                    "recently_active_pct": None,
                    "blocked_or_unreachable_pct": None,
                    "notes": ["Sin MV lifecycle: pending inferido o proxy de brecha de viajes"],
                },
            }
            if not onboarding:
                pool["notes"] = [
                    "Sin ops.mv_driver_lifecycle_base: pendientes estimados desde gap_trips;",
                    "Usar sólo como orden de magnitud.",
                ]
        else:
            pool = {
                "total_candidates": 0,
                "reachable_candidates": 0,
                "segments_detail": [],
                "pool_method": "n_a",
                "data_sources": [],
                "operability": {
                    "contactable_pct": None,
                    "recently_active_pct": None,
                    "blocked_or_unreachable_pct": None,
                    "notes": [],
                },
            }

    assert pool is not None
    segs_full = list(pool.get("segments_detail") or pool.get("segments") or [])
    total_candidates = int(pool.get("total_candidates") or 0)
    reachable = int(pool.get("reachable_candidates") or total_candidates)

    operational_context: Dict[str, Any] = {}
    est_recovery: Dict[str, Any] = {}
    suggested_focus: List[str] = []
    opp_block: Optional[Dict[str, Any]] = None

    pr = _sf(m.get("driver_productivity_ytd_real"))
    pe = _sf(m.get("driver_productivity_ytd_expected"))
    weeks_horizon, _week_note = _remaining_horizon_weeks(grain or "monthly", filters)

    if action_type in ("productivity_reactivation", "productivity_incentive", "data_review"):
        operational_context = _build_operational_context_productivity(m, pool, alert, action_type)
        est_recovery = _recovery_productivity_gap_projection_v1(
            alert=alert,
            pool_reachable=max(reachable, 1),
            prod_real=pr,
            prod_exp=pe,
            ytd_summary=ytd_summary,
            grain=grain or "monthly",
            filters=filters,
        )
        low_n = next((int(s["drivers"]) for s in segs_full if s.get("segment_id") == SID_LOW_ACTIVITY_0_5_7D), 0)
        if action_type == "productivity_reactivation" and baseline:
            hist = _recovery_historical_low_activity_recovery_v1(baseline, low_n)
            est_recovery["assumptions_used"] = (est_recovery.get("assumptions_used") or []) + [
                (
                    f"Referencia churn/reactivation agregada: método={hist.get('recovery_method')}, "
                    f"sample_weeks={hist.get('sample_size')}, "
                    f"weekly_trips_proxy={hist.get('potential_trips_recovered_weekly')}"
                )
            ]
        if action_type == "productivity_incentive":
            extra_assum = (
                "Incentivo: impacto incremental no modelado aparte — misma trayectoria de pacing que productivity_gap_projection_v1 "
                "(supuesto revisión Decision Engine)."
            )
            est_recovery["assumptions_used"] = (est_recovery.get("assumptions_used") or []) + [extra_assum]
            est_recovery["recovery_method"] = "productivity_gap_projection_v1_incentive_overlay"
        suggested_focus = _suggested_focus(segs_full, action_type)
        if baseline and action_type == "productivity_reactivation":
            d_n = next((int(s["drivers"]) for s in segs_full if s.get("segment_id") == SID_DORMANT_14D), 0)
            if d_n > 0:
                dst = _recovery_dormant_historical_baseline_v1(baseline, d_n)
                est_recovery["assumptions_used"] = (est_recovery.get("assumptions_used") or []) + [
                    f"Referencia dormant cohort: weekly_trips_baseline={dst.get('potential_trips_recovered_weekly')}, "
                    f"sample_size={dst.get('sample_size')}"
                ]

    elif action_type in ("volume_scouts_push", "volume_onboarding_followup"):
        geo_from_alerts = _volume_affected_geos_from_alerts(alert, ytd_alerts or [])
        merged_geo: List[str] = []
        if city:
            merged_geo.append(str(city).strip())
        seen_g = {g.lower() for g in merged_geo if g}
        for g in geo_from_alerts:
            gs = str(g).strip()
            if gs and gs.lower() not in seen_g:
                merged_geo.append(gs)
                seen_g.add(gs.lower())
        if not merged_geo and alert.get("entity"):
            merged_geo.append(str(alert["entity"]).strip())
        operational_context = _build_volume_context(
            m, pool, onboarding, alert, action_type, merged_geo
        )
        pend_int = int((onboarding or {}).get("pending_registrations") or total_candidates)
        if action_type == "volume_onboarding_followup":
            est_recovery = _recovery_onboarding_conversion_baseline_v1(pend_int, onboarding)
        else:
            est_recovery = _recovery_volume_pacing_v1(
                _sf(alert.get("gap_trips")),
                weeks_horizon,
                pend_int,
                baseline,
            )
        suggested_focus = _suggested_focus(segs_full, action_type)
    elif action_type == "ticket_mix_review":
        operational_context = _build_ticket_context(ytd_summary, m)
        est_recovery = _recovery_ticket_review_v1(alert)
        suggested_focus = ["validar mix LOB", "ticket promedio vs plan"]
    elif action_type == "opportunity_replicate_winner":
        opp_block = _build_opportunity_narrative(alert, base, m, display_rows, ytd_summary)
        operational_context = {"opportunity": opp_block}
        comp = opp_block.get("comparable_slice_labels") or []
        est_recovery = _recovery_opportunity_v1(alert, len(comp))
        suggested_focus = []
        if comp:
            suggested_focus.append("calibrar réplica vs slices mismo LOB")
        suggested_focus.extend(["extraer playbook", "priorizar KPI replicable"])
    else:
        operational_context = {
            "note": "Contexto genérico; tipo de acción no mapeado a motor contextual.",
        }
        est_recovery = {
            "potential_trips_recovered_weekly": None,
            "potential_gap_recovery_pct": None,
            "recovery_method": "unmapped_action_v1",
            "assumptions_used": ["Sin método numérico para este action_type"],
            "confidence": "low",
            "confidence_reason": "acción fuera de catálogo contextual",
            "historical_reference_window": "n/a",
            "sample_size": 0,
        }
        suggested_focus = []

    gap_rec_pct = est_recovery.get("potential_gap_recovery_pct")
    impact_raw = str(base.get("expected_impact") or "medium")
    impact_map = {"high": "high", "medium_high": "high", "medium": "medium", "low": "low", "preventive": "low"}
    expected_impact_hint = impact_map.get(impact_raw, "medium")
    speed_hint = "fast" if action_type in ("productivity_reactivation", "volume_onboarding_followup") else "medium"
    lev, lev_bd = _compute_leverage_breakdown(
        total_candidates=total_candidates,
        reachable=reachable,
        gap_recovery_pct=float(gap_rec_pct) if gap_rec_pct is not None else None,
        pool_from_db=pool_from_db,
        action_type=action_type,
        speed_hint=speed_hint,
        expected_impact_hint=expected_impact_hint,
    )

    base_conf = str(base.get("confidence") or "medium")
    pool_for_conf = {"total_candidates": total_candidates}
    conf = _contextual_confidence(base_conf, integrity_status, pool_for_conf, pool_from_db, action_type)
    st_int = str(integrity_status.get("status") or "")
    if (
        st_int == "ok"
        and pool_from_db
        and total_candidates >= 8
        and action_type in ("productivity_reactivation", "productivity_incentive")
        and _norm(str(alert.get("principal_driver") or "")) == "productivity"
        and alert.get("gap_trips") is not None
        and conf != "low"
    ):
        conf = "high"
    conf = _merge_confidence(conf, str(est_recovery.get("confidence") or "medium"))

    partial_fail = False
    if bool(park_ids) and not pool_from_db and action_type.startswith("productivity"):
        partial_fail = True
    if (
        bool(park_ids)
        and action_type in ("volume_scouts_push", "volume_onboarding_followup")
        and onboarding is None
    ):
        partial_fail = True

    top_segments = sorted(segs_full, key=lambda s: -int(s.get("drivers") or 0))[:3]
    contextual_reasoning = _build_contextual_reasoning(
        alert=alert, m=m, pool=pool, action_type=action_type, ytd_summary=ytd_summary
    )

    preview_entity = "drivers"
    if action_type == "ticket_mix_review":
        preview_entity = "analysis"
    elif action_type == "opportunity_replicate_winner":
        preview_entity = "slices"

    pool_out_notes = []
    if isinstance(pool.get("notes"), list):
        pool_out_notes.extend(pool["notes"])
    if pool_from_db:
        pool_out_notes.append(
            f"Muestra ancla semanal (ISO) week_start={pool.get('week_anchor')}; drivers contados pueden solaparse entre segmentos."
        )

    operational_pool_out = {
        "total_candidates": total_candidates,
        "reachable_candidates": reachable,
        "segments": top_segments,
        "pool_method": pool.get("pool_method"),
        "data_sources": pool.get("data_sources") or [],
        "operability": pool.get("operability"),
        "pool_notes": pool_out_notes,
    }

    out: Dict[str, Any] = {
        "suggestion_id": _stable_ctx_id(str(base.get("suggestion_id") or ""), action_type, str(base.get("entity") or "")),
        "base_suggestion_id": str(base.get("suggestion_id") or ""),
        "entity": str(base.get("entity") or ""),
        "action_type": action_type,
        "recommended_action_name": base.get("recommended_action_name"),
        "operational_pool": operational_pool_out,
        "estimated_recovery": est_recovery,
        "operational_context": operational_context,
        "contextual_reasoning": contextual_reasoning,
        "suggested_operational_focus": suggested_focus,
        "next_step_preview": {
            "entity_type": preview_entity,
            "preview_count": min(25, max(5, total_candidates)),
            "preview_enabled": False,
        },
        "priority_score": base.get("priority_score"),
        "operational_leverage_score": lev,
        "operational_leverage_breakdown": lev_bd,
        "confidence": conf,
    }
    return out, partial_fail


def build_projection_contextual_suggestions(
    *,
    integrity_status: Dict[str, Any],
    base_suggestions: Any,
    ytd_alerts: Any,
    display_rows: Optional[Sequence[Dict[str, Any]]],
    ytd_summary: Optional[Dict[str, Any]],
    grain: Optional[str],
    filters: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, str]]:
    """
    Retorna (contextual_suggestions, check agregado ok|partial|missing, subchecks FASE 4.2B).
    """
    empty_sub = _derive_contextual_subchecks([])
    st = str(integrity_status.get("status") or "")
    if st == "broken":
        return [], "missing", empty_sub
    if not isinstance(base_suggestions, list) or len(base_suggestions) == 0:
        return [], "missing", empty_sub

    display_rows = list(display_rows or [])
    y_alerts_list = ytd_alerts if isinstance(ytd_alerts, list) else []

    out: List[Dict[str, Any]] = []
    any_partial = False
    try:
        with get_db() as conn:
            req_cache = _RequestFetchCache()
            for base in base_suggestions:
                if not isinstance(base, dict):
                    continue
                try:
                    item, pfail = enrich_one_contextual_suggestion(
                        base=base,
                        integrity_status=integrity_status,
                        ytd_alerts=y_alerts_list,
                        display_rows=display_rows,
                        ytd_summary=ytd_summary,
                        conn=conn,
                        req_cache=req_cache,
                        grain=grain,
                        filters=filters,
                    )
                    out.append(item)
                    any_partial = any_partial or pfail
                except Exception as exc:
                    logger.warning("contextual one suggestion: %s", exc, exc_info=True)
                    any_partial = True
    except Exception as exc:
        logger.warning("contextual_suggestions conn: %s", exc, exc_info=True)
        return [], "missing", empty_sub

    if not out:
        return [], "missing", empty_sub

    subchecks = _derive_contextual_subchecks(out)
    check = "ok"
    if any_partial:
        check = "partial"
    if st == "warning":
        check = "partial" if check == "ok" else check
    if subchecks.get("recovery_auditability") == "missing":
        check = "partial" if check == "ok" else check
    if subchecks.get("segment_registry") == "missing":
        check = "partial" if check == "ok" else check

    return out, check, subchecks


def safe_build_projection_contextual_suggestions(
    **kwargs: Any,
) -> Tuple[List[Dict[str, Any]], str, Dict[str, str]]:
    try:
        return build_projection_contextual_suggestions(**kwargs)
    except Exception as exc:
        logger.warning("safe_build_projection_contextual_suggestions: %s", exc, exc_info=True)
        return [], "missing", _derive_contextual_subchecks([])


def merge_integrity_with_contextual_check(
    integrity_status: Dict[str, Any],
    contextual_check: str,
    contextual_detail_checks: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    ch = dict(integrity_status.get("checks") or {})
    ch["contextual_suggestions"] = contextual_check
    if contextual_detail_checks:
        for k, v in contextual_detail_checks.items():
            ch[k] = v
    return {**integrity_status, "checks": ch}
