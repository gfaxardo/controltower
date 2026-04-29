from __future__ import annotations

import threading
import time
from typing import Any, Iterable, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

CANONICAL_MAPPING_TABLE = "dim.dim_business_slice_mapping"
_CACHE_TTL_SEC = 300.0
_cache_lock = threading.Lock()
_cache_payload: dict[str, Any] = {
    "ts": 0.0,
    "by_raw": {},
    "by_canonical": {},
    "display_by_canonical": {},
}


def normalize_business_slice_key(value: Any) -> str:
    from app.contracts.data_contract import remove_accents

    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    normalized = remove_accents(raw).replace("_", " ")
    return " ".join(normalized.split())


def _load_mapping_payload() -> dict[str, Any]:
    by_raw: dict[str, str] = {}
    by_canonical: dict[str, set[str]] = {}
    display_by_canonical: dict[str, str] = {}
    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            f"""
            SELECT raw_value, canonical_value
            FROM {CANONICAL_MAPPING_TABLE}
            WHERE raw_value IS NOT NULL
              AND canonical_value IS NOT NULL
            ORDER BY canonical_value, raw_value
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
    for row in rows:
        raw_value = str(row.get("raw_value") or "").strip()
        canonical_value = str(row.get("canonical_value") or "").strip()
        raw_norm = normalize_business_slice_key(raw_value)
        canonical_norm = normalize_business_slice_key(canonical_value)
        if not raw_norm or not canonical_norm:
            continue
        by_raw[raw_norm] = canonical_value
        by_canonical.setdefault(canonical_norm, set()).add(raw_value)
        by_canonical.setdefault(canonical_norm, set()).add(canonical_value)
        display_by_canonical.setdefault(canonical_norm, canonical_value)
    # Todo canonical_value se resuelve a sí mismo aunque no exista fila explícita raw->same.
    for canonical_norm, display in list(display_by_canonical.items()):
        by_raw.setdefault(canonical_norm, display)
        by_canonical.setdefault(canonical_norm, set()).add(display)
    return {
        "ts": time.monotonic(),
        "by_raw": by_raw,
        "by_canonical": {k: sorted(v) for k, v in by_canonical.items()},
        "display_by_canonical": display_by_canonical,
    }


def _get_mapping_payload() -> dict[str, Any]:
    now = time.monotonic()
    with _cache_lock:
        if now - float(_cache_payload.get("ts") or 0.0) < _CACHE_TTL_SEC:
            return _cache_payload
    payload = _load_mapping_payload()
    with _cache_lock:
        _cache_payload.update(payload)
        return _cache_payload


def canonicalize_business_slice_name(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    payload = _get_mapping_payload()
    mapped = payload["by_raw"].get(normalize_business_slice_key(raw))
    return str(mapped or raw).strip()


def business_slice_filter_variants(value: Any) -> list[str]:
    raw = str(value or "").strip()
    if not raw:
        return []
    canonical_value = canonicalize_business_slice_name(raw)
    canonical_norm = normalize_business_slice_key(canonical_value)
    payload = _get_mapping_payload()
    variants = set(payload["by_canonical"].get(canonical_norm, []))
    variants.add(canonical_value)
    variants.add(raw)
    return sorted(v for v in variants if str(v).strip())


def canonicalize_business_slice_rows(
    rows: Iterable[dict[str, Any]],
    field_name: str = "business_slice_name",
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item[field_name] = canonicalize_business_slice_name(item.get(field_name))
        out.append(item)
    return out


def aggregate_business_slice_rows(
    rows: Iterable[dict[str, Any]],
    *,
    field_name: str = "business_slice_name",
    extra_key_fields: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    key_fields = list(extra_key_fields or [])
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    weighted_by_trips_fields = (
        "avg_ticket",
        "commission_pct",
        "precio_km",
        "tiempo_km",
        "completados_por_hora",
        "cancelados_por_hora",
    )
    sum_fields = (
        "trips_completed",
        "trips_cancelled",
        "active_drivers",
        "revenue_yego_net",
        "revenue_yego_final",
        "revenue_proxy_trips",
        "revenue_real_trips",
        "ticket_sum_completed",
        "ticket_count_completed",
        "total_fare_completed_positive_sum",
    )

    def _as_float(v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _as_int(v: Any) -> int:
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0

    for raw_row in rows:
        row = dict(raw_row)
        row[field_name] = canonicalize_business_slice_name(row.get(field_name))
        key = tuple(row.get(field) for field in key_fields + [field_name])
        if key not in grouped:
            seed = dict(row)
            seed["_agg_weighted"] = {
                field: (_as_float(row.get(field)) or 0.0) * max(_as_int(row.get("trips_completed")), 0)
                for field in weighted_by_trips_fields
            }
            seed["_agg_weighted_seen"] = {
                field: row.get(field) is not None
                for field in weighted_by_trips_fields
            }
            grouped[key] = seed
            continue

        target = grouped[key]
        for field in sum_fields:
            left = target.get(field)
            right = row.get(field)
            if left is None and right is None:
                continue
            target[field] = (left or 0) + (right or 0)

        for field in ("refreshed_at", "loaded_at"):
            target[field] = max(str(target.get(field) or ""), str(row.get(field) or "")) or None

        weighted = target["_agg_weighted"]
        weighted_seen = target["_agg_weighted_seen"]
        row_weight = max(_as_int(row.get("trips_completed")), 0)
        for field in weighted_by_trips_fields:
            weighted[field] += (_as_float(row.get(field)) or 0.0) * row_weight
            weighted_seen[field] = weighted_seen[field] or (row.get(field) is not None)

    out: list[dict[str, Any]] = []
    for row in grouped.values():
        weighted = row.pop("_agg_weighted", {})
        weighted_seen = row.pop("_agg_weighted_seen", {})
        trips_completed = max(_as_int(row.get("trips_completed")), 0)
        trips_cancelled = max(_as_int(row.get("trips_cancelled")), 0)
        active_drivers = max(_as_int(row.get("active_drivers")), 0)
        for field in weighted_by_trips_fields:
            if trips_completed > 0 and weighted_seen.get(field):
                row[field] = weighted[field] / trips_completed
            else:
                row[field] = None if not weighted_seen.get(field) else row.get(field)
        ticket_sum = _as_float(row.get("ticket_sum_completed"))
        ticket_count = _as_float(row.get("ticket_count_completed"))
        if ticket_sum is not None and ticket_count and ticket_count > 0:
            row["avg_ticket"] = ticket_sum / ticket_count
        revenue = _as_float(row.get("revenue_yego_net"))
        total_fare = _as_float(row.get("total_fare_completed_positive_sum"))
        if revenue is not None and total_fare and total_fare > 0:
            row["commission_pct"] = revenue / total_fare
        row["trips_per_driver"] = (trips_completed / active_drivers) if active_drivers > 0 else None
        den = trips_completed + trips_cancelled
        row["cancel_rate_pct"] = (100.0 * trips_cancelled / den) if den > 0 else None
        out.append(row)
    return out
