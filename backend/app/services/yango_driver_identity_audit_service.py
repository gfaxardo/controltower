"""
CF-H2C — Yango Driver Identity Audit Service

Cross-matches driver identities between:
- public.drivers (CT bridge)
- raw_yango.driver_profiles_raw (Yango API)
- public.trips_2026 (driver activity from CT)
- raw_yango.orders_raw (driver activity from Yango)

Detects potential mapping candidates using: full_name, phone, license, driver_id.
Does NOT create a canonical mapping table yet — audit only.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from psycopg2.extras import RealDictCursor

from app.db.connection import get_db

logger = logging.getLogger(__name__)

LIMA_PARK_ID = "08e20910d81d42658d4334d3f6d10ac0"


def _normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return " ".join(name.lower().strip().split())


def audit_driver_identity(park_id: str, audit_date: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "audit_date": audit_date,
        "park_id": park_id,
        "ct_drivers_total": 0,
        "ct_drivers_with_phone": 0,
        "ct_drivers_with_license": 0,
        "ct_drivers_active_today": 0,
        "yango_drivers_total": 0,
        "yango_drivers_working": 0,
        "yango_drivers_with_orders": 0,
        "matched_by_name": 0,
        "matched_by_name_partial": 0,
        "matched_by_phone": 0,
        "matched_by_license": 0,
        "matched_by_both_name_phone": 0,
        "matched_by_all": 0,
        "ct_drivers_unmatched": 0,
        "yango_drivers_unmatched": 0,
        "mapping_candidates_high": 0,
        "mapping_candidates_medium": 0,
        "mapping_candidates_low": 0,
        "overall_match_pct": None,
        "identity_audit_status": "PENDING",
    }

    with get_db() as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            # --- CT drivers: total in public.drivers ---
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM public.drivers
                WHERE active = true
                """
            )
            ct_tot = cur.fetchone()
            if ct_tot:
                result["ct_drivers_total"] = int(ct_tot["total"] or 0)

            # --- CT drivers with phone ---
            cur.execute(
                """
                SELECT COUNT(*) AS with_phone
                FROM public.drivers
                WHERE active = true AND phone IS NOT NULL AND phone != ''
                """
            )
            ct_ph = cur.fetchone()
            if ct_ph:
                result["ct_drivers_with_phone"] = int(ct_ph["with_phone"] or 0)

            # --- CT drivers with license ---
            cur.execute(
                """
                SELECT COUNT(*) AS with_license
                FROM public.drivers
                WHERE active = true AND license_number IS NOT NULL AND license_number != ''
                """
            )
            ct_lic = cur.fetchone()
            if ct_lic:
                result["ct_drivers_with_license"] = int(ct_lic["with_license"] or 0)

            # --- CT drivers active today (had trips) ---
            cur.execute(
                """
                SELECT COUNT(DISTINCT conductor_id) AS active
                FROM public.trips_2026
                WHERE park_id = %(park_id)s
                  AND fecha_finalizacion::date = %(source_date)s
                  AND condicion = 'Completado'
                """,
                {"park_id": park_id, "source_date": audit_date},
            )
            ct_act = cur.fetchone()
            if ct_act:
                result["ct_drivers_active_today"] = int(ct_act["active"] or 0)

            # --- Yango drivers: total profiles ---
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM raw_yango.driver_profiles_raw
                WHERE park_id = %(park_id)s
                """,
                {"park_id": park_id},
            )
            ya_tot = cur.fetchone()
            if ya_tot:
                result["yango_drivers_total"] = int(ya_tot["total"] or 0)

            # --- Yango drivers: working ---
            cur.execute(
                """
                SELECT COUNT(*) AS working
                FROM raw_yango.driver_profiles_raw
                WHERE park_id = %(park_id)s
                  AND work_status = 'working'
                """,
                {"park_id": park_id},
            )
            ya_wrk = cur.fetchone()
            if ya_wrk:
                result["yango_drivers_working"] = int(ya_wrk["working"] or 0)

            # --- Yango drivers with orders today ---
            cur.execute(
                """
                SELECT COUNT(DISTINCT driver_profile_id) AS with_orders
                FROM raw_yango.orders_raw
                WHERE park_id = %(park_id)s
                  AND order_ended_at::date = %(source_date)s
                  AND order_status = 'complete'
                """
            )
            ya_ord = cur.fetchone()
            if ya_ord:
                result["yango_drivers_with_orders"] = int(ya_ord["with_orders"] or 0)

            # --- Cross-match: CT driver_id = Yango driver_profile_id (exact UUID match) ---
            cur.execute(
                """
                SELECT COUNT(*) AS matched
                FROM public.drivers d
                INNER JOIN raw_yango.driver_profiles_raw y
                    ON d.driver_id = y.driver_profile_id
                WHERE d.active = true
                  AND y.park_id = %(park_id)s
                """,
                {"park_id": park_id},
            )
            id_match = cur.fetchone()
            if id_match:
                result["matched_by_all"] = int(id_match["matched"] or 0)

            # --- Cross-match: CT full_name vs Yango raw_payload names ---
            cur.execute(
                """
                SELECT COUNT(*) AS matched
                FROM public.drivers d
                INNER JOIN raw_yango.driver_profiles_raw y
                    ON LOWER(TRIM(d.full_name)) = LOWER(TRIM(
                        COALESCE(y.raw_payload->'driver_profile'->>'first_name', '') || ' ' ||
                        COALESCE(y.raw_payload->'driver_profile'->>'last_name', '')
                    ))
                WHERE d.active = true
                  AND y.park_id = %(park_id)s
                """,
                {"park_id": park_id},
            )
            name_full = cur.fetchone()
            if name_full:
                result["matched_by_name"] = int(name_full["matched"] or 0)

            # --- Cross-match: CT last_name vs Yango raw_payload last_name ---
            cur.execute(
                """
                SELECT COUNT(*) AS matched
                FROM public.drivers d
                INNER JOIN raw_yango.driver_profiles_raw y
                    ON LOWER(TRIM(d.last_name)) = LOWER(TRIM(y.raw_payload->'driver_profile'->>'last_name'))
                WHERE d.active = true
                  AND y.park_id = %(park_id)s
                """,
                {"park_id": park_id},
            )
            name_part = cur.fetchone()
            if name_part:
                result["matched_by_name_partial"] = int(name_part["matched"] or 0)

            # --- Cross-match: CT phone vs Yango raw_payload phone ---
            cur.execute(
                """
                SELECT COUNT(*) AS matched
                FROM public.drivers d
                INNER JOIN raw_yango.driver_profiles_raw y
                    ON d.phone IS NOT NULL AND d.phone != ''
                    AND y.raw_payload->'driver_profile'->>'phone' IS NOT NULL
                    AND REPLACE(REPLACE(REPLACE(d.phone, ' ', ''), '-', ''), '+', '')
                        = REPLACE(REPLACE(REPLACE(y.raw_payload->'driver_profile'->>'phone', ' ', ''), '-', ''), '+', '')
                WHERE d.active = true
                  AND y.park_id = %(park_id)s
                """,
                {"park_id": park_id},
            )
            phone_match = cur.fetchone()
            if phone_match:
                result["matched_by_phone"] = int(phone_match["matched"] or 0)

            # --- Cross-match: CT license vs Yango raw_payload (document_number if available) ---
            cur.execute(
                """
                SELECT COUNT(*) AS matched
                FROM public.drivers d
                INNER JOIN raw_yango.driver_profiles_raw y
                    ON d.license_number IS NOT NULL AND d.license_number != ''
                    AND (
                        y.raw_payload->'driver_profile'->>'license_number' = d.license_number
                        OR y.raw_payload->>'license_number' = d.license_number
                    )
                WHERE d.active = true
                  AND y.park_id = %(park_id)s
                """,
                {"park_id": park_id},
            )
            lic_match = cur.fetchone()
            if lic_match:
                result["matched_by_license"] = int(lic_match["matched"] or 0)

            # --- Cross-match: Both name AND phone ---
            cur.execute(
                """
                SELECT COUNT(*) AS matched
                FROM public.drivers d
                INNER JOIN raw_yango.driver_profiles_raw y
                    ON LOWER(TRIM(d.full_name)) = LOWER(TRIM(
                        COALESCE(y.raw_payload->'driver_profile'->>'first_name', '') || ' ' ||
                        COALESCE(y.raw_payload->'driver_profile'->>'last_name', '')
                    ))
                    AND d.phone IS NOT NULL AND d.phone != ''
                    AND y.raw_payload->'driver_profile'->>'phone' IS NOT NULL
                    AND REPLACE(REPLACE(REPLACE(d.phone, ' ', ''), '-', ''), '+', '')
                        = REPLACE(REPLACE(REPLACE(y.raw_payload->'driver_profile'->>'phone', ' ', ''), '-', ''), '+', '')
                WHERE d.active = true
                  AND y.park_id = %(park_id)s
                """,
                {"park_id": park_id},
            )
            both_match = cur.fetchone()
            if both_match:
                result["matched_by_both_name_phone"] = int(both_match["matched"] or 0)

            # --- Unmatched counts ---
            ct_total = result["ct_drivers_total"]
            ya_total = result["yango_drivers_total"]
            best_match = max(
                result["matched_by_all"],
                result["matched_by_both_name_phone"],
                result["matched_by_name"],
                result["matched_by_phone"],
                0,
            )
            result["ct_drivers_unmatched"] = max(0, ct_total - best_match)
            result["yango_drivers_unmatched"] = max(0, ya_total - best_match)

            # --- Mapping candidates ---
            result["mapping_candidates_high"] = result["matched_by_all"] + result["matched_by_both_name_phone"]
            result["mapping_candidates_medium"] = result["matched_by_name"] + result["matched_by_phone"]
            result["mapping_candidates_low"] = result["matched_by_name_partial"] + result["matched_by_license"]

            # --- Overall match percentage ---
            total_possible = max(ct_total, ya_total, 1)
            result["overall_match_pct"] = round(best_match / total_possible * 100, 4)

            if result["overall_match_pct"] >= 95:
                result["identity_audit_status"] = "HIGH_MATCH"
            elif result["overall_match_pct"] >= 70:
                result["identity_audit_status"] = "MEDIUM_MATCH"
            elif result["overall_match_pct"] >= 30:
                result["identity_audit_status"] = "LOW_MATCH"
            else:
                result["identity_audit_status"] = "POOR_MATCH"

        finally:
            cur.close()

    return result


def upsert_identity_audit(rec: Dict[str, Any]) -> bool:
    with get_db() as conn:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO ops.yango_driver_identity_audit_day (
                    audit_date, park_id,
                    ct_drivers_total, ct_drivers_with_phone, ct_drivers_with_license,
                    ct_drivers_active_today,
                    yango_drivers_total, yango_drivers_working, yango_drivers_with_orders,
                    matched_by_name, matched_by_name_partial,
                    matched_by_phone, matched_by_license,
                    matched_by_both_name_phone, matched_by_all,
                    ct_drivers_unmatched, yango_drivers_unmatched,
                    mapping_candidates_high, mapping_candidates_medium, mapping_candidates_low,
                    overall_match_pct, identity_audit_status
                ) VALUES (
                    %(audit_date)s, %(park_id)s,
                    %(ct_drivers_total)s, %(ct_drivers_with_phone)s, %(ct_drivers_with_license)s,
                    %(ct_drivers_active_today)s,
                    %(yango_drivers_total)s, %(yango_drivers_working)s, %(yango_drivers_with_orders)s,
                    %(matched_by_name)s, %(matched_by_name_partial)s,
                    %(matched_by_phone)s, %(matched_by_license)s,
                    %(matched_by_both_name_phone)s, %(matched_by_all)s,
                    %(ct_drivers_unmatched)s, %(yango_drivers_unmatched)s,
                    %(mapping_candidates_high)s, %(mapping_candidates_medium)s, %(mapping_candidates_low)s,
                    %(overall_match_pct)s, %(identity_audit_status)s
                )
                ON CONFLICT (audit_date, park_id) DO UPDATE SET
                    ct_drivers_total = EXCLUDED.ct_drivers_total,
                    ct_drivers_with_phone = EXCLUDED.ct_drivers_with_phone,
                    ct_drivers_with_license = EXCLUDED.ct_drivers_with_license,
                    ct_drivers_active_today = EXCLUDED.ct_drivers_active_today,
                    yango_drivers_total = EXCLUDED.yango_drivers_total,
                    yango_drivers_working = EXCLUDED.yango_drivers_working,
                    yango_drivers_with_orders = EXCLUDED.yango_drivers_with_orders,
                    matched_by_name = EXCLUDED.matched_by_name,
                    matched_by_name_partial = EXCLUDED.matched_by_name_partial,
                    matched_by_phone = EXCLUDED.matched_by_phone,
                    matched_by_license = EXCLUDED.matched_by_license,
                    matched_by_both_name_phone = EXCLUDED.matched_by_both_name_phone,
                    matched_by_all = EXCLUDED.matched_by_all,
                    ct_drivers_unmatched = EXCLUDED.ct_drivers_unmatched,
                    yango_drivers_unmatched = EXCLUDED.yango_drivers_unmatched,
                    mapping_candidates_high = EXCLUDED.mapping_candidates_high,
                    mapping_candidates_medium = EXCLUDED.mapping_candidates_medium,
                    mapping_candidates_low = EXCLUDED.mapping_candidates_low,
                    overall_match_pct = EXCLUDED.overall_match_pct,
                    identity_audit_status = EXCLUDED.identity_audit_status,
                    computed_at = now()
                """,
                rec,
            )
            logger.info(
                "Identity audit upserted: date=%s park=%s match=%.1f%% status=%s "
                "ct=%s ya=%s high_candidates=%s",
                rec["audit_date"], rec["park_id"][:8] + "***",
                rec["overall_match_pct"] or 0.0,
                rec["identity_audit_status"],
                rec["ct_drivers_total"], rec["yango_drivers_total"],
                rec["mapping_candidates_high"],
            )
            return True
        except Exception as e:
            logger.error("Failed to upsert identity audit: %s", e)
            return False
        finally:
            cur.close()
