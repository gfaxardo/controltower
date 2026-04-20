"""
Plan Reconciliation Service — Fase 3.3 / Real-First

Cross-referencia Plan vs Real para un plan_version dado.
Responde la pregunta: "¿por qué tal tajada no aparece en la matriz?"

Categorías de resultado:
  matched           - plan y real se cruzan correctamente
  missing_plan      - real existe, sin plan correspondiente
  plan_without_real - plan resuelto, sin real visible en ese período
  unresolved_plan   - plan cuyo raw_lob no mapeó a business_slice_name

Para unresolved_plan, separa:
  alias_missing     - el raw_lob no está en ningún alias conocido
  city_slice_missing- el alias existe (canonical_lob resuelto) pero la ciudad
                      no tiene esa tajada activa en ops.business_slice_mapping_rules

Audit especial: YMA / YMM por mes (para diagnóstico de filas fragmentadas).

Ciudades QA: Lima, Trujillo, Arequipa, Cali, Bogotá, Barranquilla, Medellín, Cúcuta.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from psycopg2.extras import RealDictCursor

from app.config.control_loop_lob_mapping import (
    list_alias_map_for_audit,
    resolve_excel_line_to_canonical,
)
from app.contracts.data_contract import remove_accents
from app.db.connection import get_db
from app.services.control_loop_business_slice_resolve import (
    SliceRulesIndex,
    load_map_fallback_rows,
    load_rules_index_for_geos,
    resolve_to_business_slice_name,
)

logger = logging.getLogger(__name__)

_COUNTRY_NORM = {
    "peru": "pe", "perú": "pe", "pe": "pe",
    "colombia": "co", "col": "co", "co": "co",
}
_COUNTRY_FULL = {"pe": "peru", "co": "colombia"}
_COUNTRY_FOR_RULES = {"pe": "Perú", "co": "Colombia"}

QA_CITIES = {
    "lima", "trujillo", "arequipa",
    "cali", "bogota", "bogotá", "barranquilla", "medellin", "medellín", "cucuta", "cúcuta",
}

YMA_YMM_LOBS = {"yma", "ymm"}


def _norm_country_code(raw: str) -> str:
    return _COUNTRY_NORM.get((raw or "").strip().lower(), (raw or "").strip().lower())


def _country_full(code: str) -> str:
    return _COUNTRY_FULL.get(code, code)


def _country_for_rules(raw: str) -> str:
    code = _norm_country_code(raw)
    return _COUNTRY_FOR_RULES.get(code, raw)


def _city_canonical(raw: str) -> str:
    return remove_accents((raw or "").strip()).lower()


def _month_key_str(d: Any) -> str:
    if hasattr(d, "strftime"):
        return d.strftime("%Y-%m")
    return str(d)[:7]


# ─────────────────────────────────────────────────────────────────────────────
# Carga de datos
# ─────────────────────────────────────────────────────────────────────────────

def _load_plan_rows(plan_version: str) -> List[Dict[str, Any]]:
    sql = """
        SELECT
            plan_version,
            month              AS period_date,
            country,
            city,
            lob_base           AS raw_lob,
            projected_trips,
            projected_revenue,
            projected_drivers  AS projected_active_drivers,
            created_at
        FROM ops.plan_trips_monthly
        WHERE plan_version = %s
        ORDER BY month, country, city, lob_base
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, [plan_version])
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return rows


def _load_real_rows(
    plan_rows: List[Dict[str, Any]],
) -> Dict[Tuple[str, str, str, str], Dict[str, Any]]:
    """Carga real mensual para todas las geos y períodos del plan."""
    if not plan_rows:
        return {}

    # Inferir rango de meses y geos del plan
    months = set()
    countries = set()
    cities = set()
    for r in plan_rows:
        months.add(_month_key_str(r["period_date"]))
        cn = _country_full(_norm_country_code(str(r.get("country") or "")))
        ci = _city_canonical(str(r.get("city") or ""))
        countries.add(cn)
        cities.add(ci)

    min_month = min(months) + "-01"
    max_month = max(months) + "-01"

    sql = """
        SELECT month, country, city, business_slice_name,
               trips_completed  AS real_trips,
               COALESCE(revenue_yego_final, revenue_yego_net) AS real_revenue,
               active_drivers   AS real_active_drivers
        FROM ops.real_business_slice_month_fact
        WHERE (NOT is_subfleet OR is_subfleet IS NULL)
          AND month >= %s::date
          AND month <= %s::date
    """
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, [min_month, max_month])
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()

    result: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    for r in rows:
        mk = _month_key_str(r["month"])
        co = (r["country"] or "").strip().lower()
        ci = (r["city"] or "").strip().lower()
        bsn = (r["business_slice_name"] or "").strip().lower()
        result[(mk, co, ci, bsn)] = r
    return result


def _load_active_slices_for_geos(geos: Set[Tuple[str, str]]) -> Dict[Tuple[str, str], Set[str]]:
    """Carga tajadas activas por (country_rules, city) desde ops.business_slice_mapping_rules."""
    if not geos:
        return {}
    result: Dict[Tuple[str, str], Set[str]] = {}
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        for co, ci in geos:
            cur.execute(
                """
                SELECT DISTINCT TRIM(business_slice_name::text) AS bsn
                FROM ops.business_slice_mapping_rules
                WHERE is_active
                  AND lower(trim(country::text)) = lower(trim(%s))
                  AND lower(trim(city::text)) = lower(trim(%s))
                """,
                [co, ci],
            )
            slices = {r["bsn"] for r in cur.fetchall() if r["bsn"]}
            result[(_norm_country_code(co), _city_canonical(ci))] = slices
        cur.close()
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Clasificación de fila de plan
# ─────────────────────────────────────────────────────────────────────────────

def _classify_unresolved_plan_row(
    raw_lob: str,
    raw_country: str,
    raw_city: str,
    canon_key: Optional[str],
    active_slices_by_geo: Dict[Tuple[str, str], Set[str]],
) -> str:
    """Determina si el no-match es alias_missing o city_slice_missing."""
    if not canon_key:
        return "alias_missing"

    # El alias existe: buscar si hay tajada activa para esta ciudad con ese canonical
    co_code = _norm_country_code(raw_country)
    ci_canon = _city_canonical(raw_city)
    active = active_slices_by_geo.get((co_code, ci_canon), set())
    if not active:
        return "city_slice_missing"

    # Verificar si alguna tajada activa coincide con el canonical_lob
    # (usando PLAN_LINE_TO_SLICE_CANDIDATES)
    from app.config.control_loop_lob_mapping import PLAN_LINE_TO_SLICE_CANDIDATES
    candidates = PLAN_LINE_TO_SLICE_CANDIDATES.get(canon_key, ())
    for candidate in candidates:
        if candidate.strip().lower() in {s.strip().lower() for s in active}:
            return "resolution_failed_despite_alias"  # alias+tajada existen pero resolver falló

    return "city_slice_missing"


# ─────────────────────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────────────────────

def get_plan_reconciliation_audit(
    plan_version: str,
    lob_filter: Optional[str] = None,
) -> Dict[str, Any]:
    """Auditoría completa de reconciliación Plan vs Real.

    Args:
        plan_version: versión del plan a auditar.
        lob_filter: si se proporciona, filtra por raw_lob (ej. 'yma', 'ymm').

    Retorna:
        {
          plan_version, total_plan_rows, total_real_rows,
          matched, missing_plan, plan_without_real, unresolved_plan,
          alias_missing, city_slice_missing,
          duplicate_visual_keys,
          qa_cities_summary,
          yma_ymm_audit,
          items: { matched, missing_plan, plan_without_real, unresolved_plan }
        }
    """
    plan_rows = _load_plan_rows(plan_version)

    if lob_filter:
        lf = lob_filter.strip().lower()
        plan_rows = [r for r in plan_rows if lf in (r.get("raw_lob") or "").lower()]

    if not plan_rows:
        return {
            "plan_version": plan_version,
            "total_plan_rows": 0,
            "total_real_rows": 0,
            "matched": 0, "missing_plan": 0,
            "plan_without_real": 0, "unresolved_plan": 0,
            "alias_missing": 0, "city_slice_missing": 0,
            "duplicate_visual_keys": [],
            "qa_cities_summary": {},
            "yma_ymm_audit": [],
            "items": {"matched": [], "missing_plan": [], "plan_without_real": [], "unresolved_plan": []},
            "message": f"No hay filas de plan para plan_version='{plan_version}'"
                       + (f" y lob_filter='{lob_filter}'" if lob_filter else ""),
        }

    # ── Cargar real ──────────────────────────────────────────────────────────
    real_map = _load_real_rows(plan_rows)

    # ── Preparar resolver ────────────────────────────────────────────────────
    geos_for_rules: Set[Tuple[str, str]] = set()
    geos_for_slices: Set[Tuple[str, str]] = set()
    for r in plan_rows:
        co_raw = str(r.get("country") or "")
        ci_raw = str(r.get("city") or "")
        co_rules = _country_for_rules(co_raw)
        geos_for_rules.add((co_rules, ci_raw))
        co_code = _norm_country_code(co_raw)
        ci_canon = _city_canonical(ci_raw)
        geos_for_slices.add((co_code, ci_canon))

    idx      = load_rules_index_for_geos(geos_for_rules)
    map_rows = load_map_fallback_rows()
    active_slices_by_geo = _load_active_slices_for_geos(geos_for_rules)

    # ── Procesar plan ────────────────────────────────────────────────────────
    seen_real_keys: Set[Tuple[str, str, str, str]] = set()

    items_matched: List[Dict] = []
    items_plan_without_real: List[Dict] = []
    items_unresolved: List[Dict] = []
    alias_missing_count = 0
    city_slice_missing_count = 0

    for row in plan_rows:
        raw_country = str(row.get("country") or "")
        raw_city    = str(row.get("city") or "")
        raw_lob     = str(row.get("raw_lob") or "")
        period      = _month_key_str(row["period_date"])

        co_code     = _norm_country_code(raw_country)
        co_full     = _country_full(co_code)
        co_rules    = _country_for_rules(raw_country)
        ci_canon    = _city_canonical(raw_city)

        canon_key, norm_key = resolve_excel_line_to_canonical(raw_lob)
        plan_line_key = canon_key or raw_lob

        bsn, source = resolve_to_business_slice_name(
            idx, map_rows,
            co_rules, raw_city,
            raw_lob, plan_line_key,
        )
        is_resolved = bool(bsn) and source not in ("unresolved", "")

        item_base = {
            "period":          period,
            "raw_country":     raw_country,
            "raw_city":        raw_city,
            "raw_lob":         raw_lob,
            "canonical_country":  co_full,
            "canonical_city":     ci_canon,
            "canonical_lob_base": canon_key,
            "business_slice_name": bsn,
            "visual_row_key":  f"{co_full}::{ci_canon}::{(bsn or '').lower()}",
            "resolution_status": "resolved" if is_resolved else "unresolved",
            "resolution_source": source,
        }

        if not is_resolved:
            failure_type = _classify_unresolved_plan_row(
                raw_lob, raw_country, raw_city, canon_key, active_slices_by_geo
            )
            item_base["failure_type"] = failure_type
            item_base["resolution_note"] = (
                f"raw_lob '{raw_lob}' sin alias conocido"
                if failure_type == "alias_missing"
                else f"canonical_lob '{canon_key}' sin tajada activa en {co_rules}/{raw_city}"
            )
            if failure_type == "alias_missing":
                alias_missing_count += 1
            else:
                city_slice_missing_count += 1
            items_unresolved.append(item_base)
            continue

        # Resuelto → buscar en real
        real_key = (period, co_full, ci_canon, bsn.strip().lower())
        real_data = real_map.get(real_key)

        if real_data:
            seen_real_keys.add(real_key)
            item_base.update({
                "real_trips":    real_data.get("real_trips"),
                "real_revenue":  real_data.get("real_revenue"),
                "real_drivers":  real_data.get("real_active_drivers"),
            })
            items_matched.append(item_base)
        else:
            items_plan_without_real.append(item_base)

    # ── Real sin plan ────────────────────────────────────────────────────────
    items_missing_plan: List[Dict] = []
    for real_key, real_data in real_map.items():
        if real_key in seen_real_keys:
            continue
        period, co_n, ci_n, bsn_n = real_key
        items_missing_plan.append({
            "period":            period,
            "canonical_country": co_n,
            "canonical_city":    ci_n,
            "business_slice_name": real_data.get("business_slice_name", bsn_n),
            "visual_row_key":   f"{co_n}::{ci_n}::{bsn_n}",
            "real_trips":       real_data.get("real_trips"),
            "real_revenue":     real_data.get("real_revenue"),
            "real_drivers":     real_data.get("real_active_drivers"),
        })

    # ── Duplicate visual keys ────────────────────────────────────────────────
    from collections import Counter
    all_vkeys = (
        [i["visual_row_key"] for i in items_matched]
        + [i["visual_row_key"] for i in items_plan_without_real]
        + [i["visual_row_key"] for i in items_missing_plan]
    )
    dup_counter = Counter(all_vkeys)
    duplicate_visual_keys = [
        {"visual_row_key": k, "count": v}
        for k, v in dup_counter.items()
        if v > 1
    ]

    # ── QA por ciudad ────────────────────────────────────────────────────────
    qa_cities_summary: Dict[str, Dict] = {}
    all_items = (
        [(i, "matched") for i in items_matched]
        + [(i, "missing_plan") for i in items_missing_plan]
        + [(i, "plan_without_real") for i in items_plan_without_real]
        + [(i, "unresolved_plan") for i in items_unresolved]
    )
    for item, status in all_items:
        ci = item.get("canonical_city") or item.get("raw_city", "")
        if not ci:
            continue
        ci_lower = ci.strip().lower()
        if ci_lower not in QA_CITIES:
            continue
        if ci_lower not in qa_cities_summary:
            qa_cities_summary[ci_lower] = {
                "city": ci, "matched": 0, "missing_plan": 0,
                "plan_without_real": 0, "unresolved_plan": 0,
            }
        qa_cities_summary[ci_lower][status] = qa_cities_summary[ci_lower].get(status, 0) + 1

    # ── YMA / YMM audit ──────────────────────────────────────────────────────
    yma_ymm_items: List[Dict] = []
    for item, status in all_items:
        raw_lob  = (item.get("raw_lob") or "").lower()
        canon    = (item.get("canonical_lob_base") or "").lower()
        bsn_val  = (item.get("business_slice_name") or "").lower()
        if any(x in raw_lob or x in canon or x in bsn_val for x in YMA_YMM_LOBS):
            yma_ymm_items.append({
                "period":            item.get("period"),
                "raw_city":          item.get("raw_city") or item.get("canonical_city"),
                "raw_lob":           item.get("raw_lob"),
                "canonical_lob":     item.get("canonical_lob_base"),
                "business_slice_name": item.get("business_slice_name"),
                "resolution_status": item.get("resolution_status", "resolved" if status != "unresolved_plan" else "unresolved"),
                "visual_row_key":    item.get("visual_row_key"),
                "status":            status,
            })

    return {
        "plan_version":          plan_version,
        "total_plan_rows":       len(plan_rows),
        "total_real_rows":       len(real_map),
        "matched":               len(items_matched),
        "missing_plan":          len(items_missing_plan),
        "plan_without_real":     len(items_plan_without_real),
        "unresolved_plan":       len(items_unresolved),
        "alias_missing":         alias_missing_count,
        "city_slice_missing":    city_slice_missing_count,
        "duplicate_visual_keys": duplicate_visual_keys,
        "qa_cities_summary":     qa_cities_summary,
        "yma_ymm_audit":         sorted(yma_ymm_items, key=lambda x: (x.get("period") or "", x.get("raw_city") or "", x.get("raw_lob") or "")),
        "items": {
            "matched":           items_matched,
            "missing_plan":      items_missing_plan,
            "plan_without_real": items_plan_without_real,
            "unresolved_plan":   items_unresolved,
        },
    }
