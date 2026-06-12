"""
LG-RNA-2B — RNA Pilot Measurement Service
Joins RNA priority with contact/outcome data. NO invention of results.
"""
from __future__ import annotations
import logging
from typing import Any, Dict, List
from app.db.connection import get_db

logger = logging.getLogger(__name__)

TABLE_MEASURE = "growth.rna_pilot_measurement_fact"
TABLE_PRIORITY = "growth.rna_priority_fact"
TABLE_RESULT = "growth.yego_lima_loopcontrol_result_sync"
TABLE_IMPACT = "growth.yego_lima_impact_tracking"
TABLE_EXPORT = "growth.yego_lima_export_audit"


def build_pilot_measurement(cohort_date: str = None) -> Dict[str, Any]:
    from datetime import date as dt
    cdate = cohort_date or str(dt.today())

    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(f"""
            INSERT INTO {TABLE_MEASURE} (driver_profile_id, priority_band, rna_score, cohort_date,
                exported_at, contacted_at, contact_status, contact_disposition,
                first_trip_after_contact, trips_after_contact_7d, trips_after_contact_30d,
                activated_after_contact, measured_at, data_quality)
            SELECT
                p.driver_profile_id, p.priority_band, p.rna_score, %(cd)s::date,
                e.generated_at AS exported_at,
                lc.last_call_at AS contacted_at,
                lc.status AS contact_status,
                lc.disposition AS contact_disposition,
                imp.first_trip_after_contact_at,
                COALESCE(imp.post_contact_trips, 0) AS trips_after_contact_7d,
                NULL AS trips_after_contact_30d,
                CASE WHEN imp.first_trip_after_contact_at IS NOT NULL THEN true ELSE false END,
                now(),
                CASE WHEN lc.driver_id IS NOT NULL THEN 'HAS_CONTACT_DATA'
                     WHEN e.export_id IS NOT NULL THEN 'EXPORTED_ONLY'
                     ELSE 'NO_CONTACT_DATA' END
            FROM {TABLE_PRIORITY} p
            LEFT JOIN {TABLE_EXPORT} e ON p.driver_profile_id = e.export_id  -- approximate: export may store driver ref
            LEFT JOIN {TABLE_RESULT} lc ON p.driver_profile_id = lc.driver_id
            LEFT JOIN {TABLE_IMPACT} imp ON p.driver_profile_id = imp.driver_profile_id
                                      AND imp.contact_date = lc.last_call_at::date
            ON CONFLICT (driver_profile_id, cohort_date) DO UPDATE SET
                exported_at = EXCLUDED.exported_at,
                contacted_at = EXCLUDED.contacted_at,
                contact_status = EXCLUDED.contact_status,
                contact_disposition = EXCLUDED.contact_disposition,
                first_trip_after_contact = EXCLUDED.first_trip_after_contact,
                trips_after_contact_7d = EXCLUDED.trips_after_contact_7d,
                activated_after_contact = EXCLUDED.activated_after_contact,
                measured_at = EXCLUDED.measured_at,
                data_quality = EXCLUDED.data_quality
        """, {"cd": cdate})

        cur.execute(f"SELECT COUNT(*) FROM {TABLE_MEASURE} WHERE cohort_date = %(cd)s::date", {"cd": cdate})
        total = (cur.fetchone() or [0])[0]

        cur.execute(f"""
            SELECT priority_band, COUNT(*) as total,
                   COUNT(*) FILTER (WHERE data_quality = 'HAS_CONTACT_DATA') as contacted,
                   COUNT(*) FILTER (WHERE activated_after_contact) as activated
            FROM {TABLE_MEASURE} WHERE cohort_date = %(cd)s::date
            GROUP BY priority_band ORDER BY priority_band
        """, {"cd": cdate})
        bands = []
        for r in cur.fetchall():
            contacted = r[2] or 0
            total_b = r[1] or 1
            bands.append({
                "band": r[0], "total": r[1], "contacted": contacted,
                "activated": r[3] or 0,
                "contact_rate": round(contacted / total_b * 100, 2),
                "activation_rate": round((r[3] or 0) / max(contacted, 1) * 100, 2),
            })

        return {"cohort_date": cdate, "total_measured": total, "bands": bands}


def get_pilot_summary() -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*), COUNT(*) FILTER (WHERE data_quality='HAS_CONTACT_DATA') FROM {TABLE_MEASURE}")
        r = cur.fetchone()
        total, has_contact = r[0] or 0, r[1] or 0

        cur.execute(f"""
            SELECT priority_band, COUNT(*) as total,
                   COUNT(*) FILTER (WHERE data_quality='HAS_CONTACT_DATA') as contacted,
                   COUNT(*) FILTER (WHERE activated_after_contact) as activated
            FROM {TABLE_MEASURE} GROUP BY priority_band ORDER BY priority_band
        """)
        bands = []
        for r in cur.fetchall():
            c = r[2] or 0
            t = r[1] or 1
            bands.append({
                "band": r[0], "total": r[1], "contacted": c, "activated": r[3] or 0,
                "contact_rate": round(c / t * 100, 2),
                "activation_rate": round((r[3] or 0) / max(c, 1) * 100, 2),
            })

        cur.execute(f"SELECT data_quality, COUNT(*) FROM {TABLE_MEASURE} GROUP BY data_quality")
        dq = [{"quality": r[0], "count": r[1]} for r in cur.fetchall()]

        return {
            "total_measured": total, "with_contact_data": has_contact,
            "contact_data_pct": round(has_contact / max(total, 1) * 100, 2),
            "bands": bands, "data_quality": dq,
            "ready": has_contact > 0,
        }


def get_pilot_drivers(band: str = None, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
    with get_db() as conn:
        cur = conn.cursor()
        cond = ""; params = {"lim": limit, "off": offset}
        if band and band in ("HOT", "WARM", "COLD"):
            cond = "WHERE priority_band = %(band)s"; params["band"] = band
        cur.execute(f"SELECT COUNT(*) FROM {TABLE_MEASURE} {cond}", params)
        total = (cur.fetchone() or [0])[0]

        cur.execute(f"""
            SELECT driver_profile_id, priority_band, rna_score, cohort_date,
                   exported_at, contacted_at, contact_status, contact_disposition,
                   first_trip_after_contact, trips_after_contact_7d,
                   activated_after_contact, data_quality
            FROM {TABLE_MEASURE} {cond}
            ORDER BY rna_score DESC LIMIT %(lim)s OFFSET %(off)s
        """, params)

        drivers = []
        for r in cur.fetchall():
            drivers.append({
                "driver_id": r[0], "band": r[1], "score": float(r[2]), "cohort_date": str(r[3]) if r[3] else None,
                "exported_at": str(r[4]) if r[4] else None,
                "contacted_at": str(r[5]) if r[5] else None,
                "contact_status": r[6], "contact_disposition": r[7],
                "first_trip_after": str(r[8]) if r[8] else None,
                "trips_after_7d": r[9], "activated": r[10], "data_quality": r[11],
            })
        return {"total": total, "drivers": drivers}
