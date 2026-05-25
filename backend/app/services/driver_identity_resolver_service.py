"""
Driver Identity Resolver Service
Shared service for enriching driver records with human-readable identity fields.

Sources:
  - ops.v_dim_driver_resolved (driver_name from conductor_nombre)
  - ops.v_dim_park_resolved (park_name, city, country)
  - ops.driver_daily_activity_fact (driver activity metadata)

Returns:
  - driver_id (original)
  - display_name (driver_name or driver_id fallback)
  - city, country, park_label (resolved park info)
  - lifecycle_state, risk_level, archetype, recoverability_bucket (if available)

Never fails: if resolution fails, returns driver_id as display_name and nulls for others.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

TIMEOUT_MS = 30000

# Cache at module level (TTL in-memory)
_cache: dict[str, dict] = {}
_cache_park: dict[str, dict] = {}


def _cursor(conn, timeout_ms=TIMEOUT_MS):
    c = conn.cursor(cursor_factory=RealDictCursor)
    c.execute("SET statement_timeout = %s", (str(timeout_ms),))
    return c


def resolve_driver_identity(driver_id: str) -> dict[str, Any]:
    """Resolve a single driver_id to human-readable fields."""
    if not driver_id:
        return _empty_identity(driver_id)

    if driver_id in _cache:
        return _cache[driver_id]

    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute(
                """
                SELECT driver_name
                FROM ops.v_dim_driver_resolved
                WHERE driver_id = %(driver_id)s
                LIMIT 1
                """,
                {"driver_id": driver_id},
            )
            row = cur.fetchone()
            driver_name = row["driver_name"].strip() if row and row.get("driver_name") else ""
    except Exception as e:
        logger.warning("driver_identity_resolver: failed for %s: %s", driver_id, e)
        driver_name = ""

    display_name = driver_name if driver_name else str(driver_id)

    result = {
        "driver_id": driver_id,
        "display_name": display_name,
        "license": None,
        "phone": None,
        "city": None,
        "country": None,
        "park_label": None,
    }

    _cache[driver_id] = result
    return result


def resolve_driver_batch(driver_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Resolve multiple driver_ids efficiently in a single query."""
    if not driver_ids:
        return {}

    uncached = [did for did in driver_ids if did not in _cache]
    if uncached:
        try:
            with get_db() as conn:
                cur = _cursor(conn)
                cur.execute(
                    """
                    SELECT driver_id, driver_name
                    FROM ops.v_dim_driver_resolved
                    WHERE driver_id = ANY(%(ids)s)
                    """,
                    {"ids": uncached},
                )
                for row in (cur.fetchall() or []):
                    did = row["driver_id"]
                    name = (row.get("driver_name") or "").strip()
                    _cache[did] = {
                        "driver_id": did,
                        "display_name": name if name else str(did),
                        "license": None,
                        "phone": None,
                        "city": None,
                        "country": None,
                        "park_label": None,
                    }
        except Exception as e:
            logger.warning("driver_identity_resolver batch failed: %s", e)

    return {did: _cache.get(did, _empty_identity(did)) for did in driver_ids}


def resolve_park_label(park_id: str) -> dict[str, Any]:
    """Resolve park_id to park_label, city, country."""
    if not park_id:
        return {"park_label": park_id, "city": None, "country": None}

    if park_id in _cache_park:
        return _cache_park[park_id]

    try:
        with get_db() as conn:
            cur = _cursor(conn)
            cur.execute(
                """
                SELECT park_name, city, country
                FROM ops.v_dim_park_resolved
                WHERE park_id = %(park_id)s
                LIMIT 1
                """,
                {"park_id": park_id},
            )
            row = cur.fetchone()
            result = {
                "park_label": (row["park_name"] or str(park_id)) if row else str(park_id),
                "city": row["city"] if row else None,
                "country": row["country"] if row else None,
            }
            _cache_park[park_id] = result
            return result
    except Exception as e:
        logger.warning("park_resolver failed for %s: %s", park_id, e)
        return {"park_label": str(park_id), "city": None, "country": None}


def resolve_park_batch(park_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Resolve multiple park_ids efficiently."""
    if not park_ids:
        return {}

    uncached = [pid for pid in park_ids if pid not in _cache_park]
    if uncached:
        try:
            with get_db() as conn:
                cur = _cursor(conn)
                cur.execute(
                    """
                    SELECT park_id, park_name, city, country
                    FROM ops.v_dim_park_resolved
                    WHERE park_id = ANY(%(ids)s)
                    """,
                    {"ids": uncached},
                )
                for row in (cur.fetchall() or []):
                    pid = row["park_id"]
                    _cache_park[pid] = {
                        "park_label": (row["park_name"] or str(pid)),
                        "city": row.get("city"),
                        "country": row.get("country"),
                    }
        except Exception as e:
            logger.warning("park_resolver batch failed: %s", e)

    default = {"park_label": None, "city": None, "country": None}
    return {pid: _cache_park.get(pid, {"park_label": str(pid), "city": None, "country": None}) for pid in park_ids}


def enrich_driver_record(driver_record: dict[str, Any]) -> dict[str, Any]:
    """Add display_name, city, country, park_label to a driver record dict."""
    driver_id = driver_record.get("driver_id") or driver_record.get("driver_key", "")
    identity = resolve_driver_identity(str(driver_id)) if driver_id else _empty_identity("")

    park_id = driver_record.get("park_id") or driver_record.get("dominant_park_id", "")
    park_info = resolve_park_label(str(park_id)) if park_id else {"park_label": None, "city": None, "country": None}

    enriched = dict(driver_record)
    enriched["display_name"] = identity.get("display_name", str(driver_id))
    enriched["license"] = identity.get("license")
    enriched["phone"] = identity.get("phone")

    if park_info.get("park_label"):
        enriched["park_label"] = park_info["park_label"]
    if park_info.get("city") and not enriched.get("city"):
        enriched["city"] = park_info["city"]
    if park_info.get("country") and not enriched.get("country"):
        enriched["country"] = park_info["country"]

    return enriched


def enrich_driver_batch(driver_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Batch-enrich a list of driver records with identity fields."""
    if not driver_records:
        return []

    driver_ids = list({str(r.get("driver_id") or r.get("driver_key", "")) for r in driver_records if r.get("driver_id") or r.get("driver_key")})
    park_ids = list({str(r.get("park_id") or r.get("dominant_park_id", "")) for r in driver_records if r.get("park_id") or r.get("dominant_park_id")})

    identities = resolve_driver_batch(driver_ids)
    parks = resolve_park_batch(park_ids)

    result = []
    for r in driver_records:
        did = str(r.get("driver_id") or r.get("driver_key", ""))
        pid = str(r.get("park_id") or r.get("dominant_park_id", ""))
        identity = identities.get(did, _empty_identity(did))
        park_info = parks.get(pid, {"park_label": str(pid) if pid else None, "city": None, "country": None})

        enriched = dict(r)
        enriched["display_name"] = identity.get("display_name", did)
        enriched["license"] = identity.get("license")
        enriched["phone"] = identity.get("phone")
        if park_info.get("park_label"):
            enriched["park_label"] = park_info["park_label"]
        if park_info.get("city") and not enriched.get("city"):
            enriched["city"] = park_info["city"]
        if park_info.get("country") and not enriched.get("country"):
            enriched["country"] = park_info["country"]

        result.append(enriched)

    return result


def _empty_identity(driver_id: str) -> dict[str, Any]:
    return {
        "driver_id": driver_id,
        "display_name": str(driver_id),
        "license": None,
        "phone": None,
        "city": None,
        "country": None,
        "park_label": None,
    }


def clear_cache():
    """Clear identity resolution caches (useful for testing)."""
    _cache.clear()
    _cache_park.clear()
