"""
Real LOB v2: opciones para dropdowns de filtros (countries, cities, parks, lob_groups, tipo_servicio, years).
Fuente: ops.mv_real_lob_month_v2 y ops.mv_real_lob_week_v2.
Cache en memoria 5 min para no golpear la DB en cada carga.
"""
from app.db.connection import get_db
from psycopg2.extras import RealDictCursor
from typing import Optional, List, Dict, Any
import logging
import time

logger = logging.getLogger(__name__)

MV_MONTHLY = "ops.mv_real_lob_month_v2"
MV_WEEKLY = "ops.mv_real_lob_week_v2"
FILTERS_CACHE_TTL_SEC = 300  # 5 min
_filters_cache: Optional[Dict[str, Any]] = None
_filters_cache_ts: float = 0
FILTERS_TIMEOUT_MS = 10000


def _cache_get() -> Optional[Dict[str, Any]]:
    if _filters_cache is None:
        return None
    if time.time() - _filters_cache_ts > FILTERS_CACHE_TTL_SEC:
        return None
    return _filters_cache


def _cache_set(data: Dict[str, Any]) -> None:
    global _filters_cache, _filters_cache_ts
    _filters_cache = data
    _filters_cache_ts = time.time()


def get_real_lob_filters(
    country: Optional[str] = None,
    city: Optional[str] = None,
) -> Dict[str, Any]:
    """
    GET /ops/real-lob/filters
    Retorna: countries, cities (filtrable por country), parks (filtrable por country+city),
             lob_groups, tipo_servicio, segments, years.
    """
    cached = _cache_get()
    if cached is not None:
        # Filtrar cities/parks según country/city sin re-query
        out = _apply_filter_params(cached, country, city)
        return out
    try:
        with get_db() as conn:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute("SET statement_timeout = %s", (str(FILTERS_TIMEOUT_MS),))
            # Countries (DISTINCT de ambas MVs)
            cur.execute(f"""
                SELECT DISTINCT country FROM (
                    SELECT country FROM {MV_MONTHLY} WHERE country IS NOT NULL AND TRIM(country) <> ''
                    UNION
                    SELECT country FROM {MV_WEEKLY} WHERE country IS NOT NULL AND TRIM(country) <> ''
                ) u ORDER BY country
            """)
            countries = [r["country"] for r in cur.fetchall() if r.get("country")]
            # Cities (country, city)
            cur.execute(f"""
                SELECT DISTINCT country, city FROM (
                    SELECT country, city FROM {MV_MONTHLY}
                    WHERE country IS NOT NULL AND TRIM(country) <> '' AND city IS NOT NULL AND TRIM(city) <> ''
                    UNION
                    SELECT country, city FROM {MV_WEEKLY}
                    WHERE country IS NOT NULL AND TRIM(country) <> '' AND city IS NOT NULL AND TRIM(city) <> ''
                ) u ORDER BY country, city
            """)
            cities = [dict(r) for r in cur.fetchall()]
            # Parks (country, city, park_id, park_name) - ya tiene park_name en la MV
            cur.execute(f"""
                SELECT DISTINCT country, city, park_id, park_name FROM (
                    SELECT country, city, park_id, COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text) AS park_name
                    FROM {MV_MONTHLY}
                    WHERE country IS NOT NULL AND city IS NOT NULL AND park_id IS NOT NULL
                    UNION
                    SELECT country, city, park_id, COALESCE(NULLIF(TRIM(park_name::text), ''), park_id::text) AS park_name
                    FROM {MV_WEEKLY}
                    WHERE country IS NOT NULL AND city IS NOT NULL AND park_id IS NOT NULL
                ) u ORDER BY country, city, park_name
            """)
            parks = [dict(r) for r in cur.fetchall()]
            for p in parks:
                if p.get("park_name") and hasattr(p["park_name"], "strip"):
                    pass
                else:
                    p["park_name"] = str(p.get("park_id") or "")
            # LOB groups
            cur.execute(f"""
                SELECT DISTINCT lob_group FROM (
                    SELECT lob_group FROM {MV_MONTHLY} WHERE lob_group IS NOT NULL
                    UNION SELECT lob_group FROM {MV_WEEKLY} WHERE lob_group IS NOT NULL
                ) u ORDER BY lob_group
            """)
            lob_groups = [r["lob_group"] for r in cur.fetchall() if r.get("lob_group")]
            # Tipo servicio (real_tipo_servicio_norm)
            cur.execute(f"""
                SELECT DISTINCT real_tipo_servicio_norm FROM (
                    SELECT real_tipo_servicio_norm FROM {MV_MONTHLY} WHERE real_tipo_servicio_norm IS NOT NULL
                    UNION SELECT real_tipo_servicio_norm FROM {MV_WEEKLY} WHERE real_tipo_servicio_norm IS NOT NULL
                ) u ORDER BY real_tipo_servicio_norm
            """)
            tipo_servicio = [r["real_tipo_servicio_norm"] for r in cur.fetchall() if r.get("real_tipo_servicio_norm")]
            # Years (de month_start y week_start)
            cur.execute(f"""
                SELECT DISTINCT y FROM (
                    SELECT EXTRACT(YEAR FROM month_start)::INT AS y FROM {MV_MONTHLY} WHERE month_start IS NOT NULL
                    UNION
                    SELECT EXTRACT(YEAR FROM week_start)::INT AS y FROM {MV_WEEKLY} WHERE week_start IS NOT NULL
                ) u ORDER BY y DESC
            """)
            years = [int(r["y"]) for r in cur.fetchall() if r.get("y") is not None]
            cur.close()
        raw = {
            "countries": countries,
            "cities": cities,
            "parks": parks,
            "lob_groups": lob_groups,
            "tipo_servicio": tipo_servicio,
            "segments": ["Todos", "B2B", "B2C"],
            "years": years,
        }
        _cache_set(raw)
        return _apply_filter_params(raw, country, city)
    except Exception as e:
        logger.error("Real LOB filters: %s", e)
        raise


def _apply_filter_params(raw: Dict[str, Any], country: Optional[str], city: Optional[str]) -> Dict[str, Any]:
    """Filtra cities por country y parks por country+city para respuesta."""
    cities = raw.get("cities") or []
    parks = raw.get("parks") or []
    if country:
        country_lo = str(country).strip().lower()
        cities = [c for c in cities if (c.get("country") or "").strip().lower() == country_lo]
        parks = [p for p in parks if (p.get("country") or "").strip().lower() == country_lo]
    if city:
        city_lo = str(city).strip().lower()
        parks = [p for p in parks if (p.get("city") or "").strip().lower() == city_lo]
    return {
        "countries": raw.get("countries") or [],
        "cities": cities,
        "parks": parks,
        "lob_groups": raw.get("lob_groups") or [],
        "tipo_servicio": raw.get("tipo_servicio") or [],
        "segments": raw.get("segments") or ["Todos", "B2B", "B2C"],
        "years": raw.get("years") or [],
    }
