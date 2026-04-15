"""
Resuelve línea de plan → business_slice_name (misma tajada que Omniview / business_slice_mapping_rules).

Usa reglas activas por (country, city) + tabla ops.control_loop_plan_line_to_business_slice + candidatos por canonical.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from psycopg2.extras import RealDictCursor

from app.config.control_loop_lob_mapping import PLAN_LINE_TO_SLICE_CANDIDATES
from app.db.connection import get_db

logger = logging.getLogger(__name__)


def _norm(s: str) -> str:
    return (s or "").strip().lower()


@dataclass
class SliceRulesIndex:
    """Índice lower(business_slice_name) → nombre display para una ciudad."""

    by_city: Dict[Tuple[str, str], Dict[str, str]] = field(default_factory=dict)

    def add_rule(self, country: str, city: str, bsn: str) -> None:
        co, ci = _norm(country), _norm(city)
        if not bsn or not bsn.strip():
            return
        key = (co, ci)
        if key not in self.by_city:
            self.by_city[key] = {}
        self.by_city[key][_norm(bsn)] = bsn.strip()

    def lookup(self, country: str, city: str, name: str) -> Optional[str]:
        d = self.by_city.get((_norm(country), _norm(city)))
        if not d:
            return None
        return d.get(_norm(name))


def load_rules_index_for_geos(geos: Set[Tuple[str, str]]) -> SliceRulesIndex:
    """Carga nombres de tajada activos por cada (country, city) solicitado."""
    idx = SliceRulesIndex()
    if not geos:
        return idx
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
                  AND business_slice_name IS NOT NULL
                  AND trim(business_slice_name::text) <> ''
                """,
                (co, ci),
            )
            for row in cur.fetchall():
                bsn = row.get("bsn")
                if bsn:
                    idx.add_rule(co, ci, bsn)
        cur.close()
    return idx


def load_map_fallback_rows() -> List[dict]:
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT plan_line_key, business_slice_name, country, city, priority
            FROM ops.control_loop_plan_line_to_business_slice
            WHERE active
            ORDER BY priority ASC, id ASC
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    return rows


def resolve_to_business_slice_name(
    idx: SliceRulesIndex,
    map_rows: List[dict],
    country: str,
    city: str,
    linea_negocio_excel: str,
    plan_line_key: str,
) -> Tuple[Optional[str], str]:
    """
    Retorna (business_slice_name en reglas, resolution_source).
    """
    excel = (linea_negocio_excel or "").strip()
    key = (plan_line_key or "").strip()

    hit = idx.lookup(country, city, excel)
    if hit:
        return hit, "rules_exact"

    for row in map_rows:
        if row.get("plan_line_key") != key:
            continue
        rc, ry = row.get("country"), row.get("city")
        if rc and _norm(rc) != _norm(country):
            continue
        if ry and _norm(ry) != _norm(city):
            continue
        cand = (row.get("business_slice_name") or "").strip()
        if not cand:
            continue
        hit = idx.lookup(country, city, cand)
        if hit:
            return hit, "control_loop_map"

    for cand in PLAN_LINE_TO_SLICE_CANDIDATES.get(key, ()):
        hit = idx.lookup(country, city, cand)
        if hit:
            return hit, "candidate_rules"

    return None, "unresolved"


def list_supported_slices_for_city(country: str, city: str) -> List[str]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT DISTINCT TRIM(business_slice_name::text)
            FROM ops.business_slice_mapping_rules
            WHERE is_active
              AND lower(trim(country::text)) = lower(trim(%s))
              AND lower(trim(city::text)) = lower(trim(%s))
            ORDER BY 1
            """,
            (country, city),
        )
        out = [r[0] for r in cur.fetchall() if r[0]]
        cur.close()
    return out
