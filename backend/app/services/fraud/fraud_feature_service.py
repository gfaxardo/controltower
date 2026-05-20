"""Fase 1F — Feature Service.

Calcula features de confianza y riesgo por driver:
- total_completed_trips, completed_trips_7d/30d
- first_trip_at, last_trip_at
- trust_tier
- pickup_cluster_key
"""
from datetime import datetime, timedelta
from app.db.connection import get_db


def compute_driver_trust(driver_id, park_id=None):
    """Calcula trust tier y stats para un driver."""
    source = "public.trips_2026"
    date_col = "fecha_inicio_viaje"
    driver_col = "conductor_id"
    status_col = "condicion"
    completed_value = "Completado"

    params = {"driver_id": driver_id}
    park_filter = ""
    if park_id:
        park_filter = "AND park_id = %(park_id)s"
        params["park_id"] = park_id

    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(f"""
            SELECT
                COUNT(*) AS total_completed,
                MIN({date_col}) AS first_trip,
                MAX({date_col}) AS last_trip
            FROM {source}
            WHERE {driver_col} = %(driver_id)s
              {park_filter}
              AND {status_col} = %(completed)s
        """, {**params, "completed": completed_value})
        r = cur.fetchone()
        total = r[0] if r and r[0] else 0
        first_trip = r[1] if r else None
        last_trip = r[2] if r else None

        now = datetime.now()
        trips_7d = 0
        trips_30d = 0
        if last_trip:
            d7 = now - timedelta(days=7)
            d30 = now - timedelta(days=30)
            cur.execute(f"""
                SELECT COUNT(*) FROM {source}
                WHERE {driver_col} = %(driver_id)s
                  {park_filter}
                  AND {status_col} = %(completed)s
                  AND {date_col} >= %(d7)s
            """, {**params, "completed": completed_value, "d7": d7})
            trips_7d = cur.fetchone()[0] or 0

            cur.execute(f"""
                SELECT COUNT(*) FROM {source}
                WHERE {driver_col} = %(driver_id)s
                  {park_filter}
                  AND {status_col} = %(completed)s
                  AND {date_col} >= %(d30)s
            """, {**params, "completed": completed_value, "d30": d30})
            trips_30d = cur.fetchone()[0] or 0

        cur.close()

    # Determinar trust_tier
    trust_tier = "unknown"
    trust_reason = {}

    if total == 0:
        trust_tier = "unknown"
        trust_reason = {"reason": "no_completed_trips"}
    else:
        # Verificar si tiene casos abiertos high/critical
        has_restriction = _has_active_restriction(driver_id, park_id)
        if has_restriction:
            trust_tier = "restricted"
            trust_reason = {"reason": "active_high_critical_case"}
        elif total >= 50:
            trust_tier = "trusted"
            trust_reason = {"reason": "sufficient_history", "total_trips": total}
        else:
            trust_tier = "new_or_unproven"
            trust_reason = {"reason": "insufficient_history", "total_trips": total}

    return {
        "driver_id": driver_id,
        "park_id": park_id,
        "total_completed_trips": total,
        "completed_trips_7d": trips_7d,
        "completed_trips_30d": trips_30d,
        "first_completed_trip_at": first_trip.isoformat() if first_trip else None,
        "last_completed_trip_at": last_trip.isoformat() if last_trip else None,
        "trust_tier": trust_tier,
        "trust_reason": trust_reason,
    }


def _has_active_restriction(driver_id, park_id=None):
    """Verifica si el driver tiene casos abiertos high/critical en fraud."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if park_id:
                cur.execute("""
                    SELECT 1 FROM fraud.risk_cases
                    WHERE driver_id = %s AND park_id = %s
                      AND status = 'open' AND severity IN ('high', 'critical')
                    LIMIT 1
                """, (driver_id, park_id))
            else:
                cur.execute("""
                    SELECT 1 FROM fraud.risk_cases
                    WHERE driver_id = %s
                      AND status = 'open' AND severity IN ('high', 'critical')
                    LIMIT 1
                """, (driver_id,))
            r = cur.fetchone()
            cur.close()
            return r is not None
    except Exception:
        return False


def upsert_driver_trust_snapshot(driver_id, park_id, trust_data):
    """Escribe o actualiza el snapshot de confianza en fraud.driver_trust_snapshot."""
    from psycopg2.extras import Json
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO fraud.driver_trust_snapshot
                (driver_id, park_id, total_completed_trips, completed_trips_7d,
                 completed_trips_30d, first_completed_trip_at, last_completed_trip_at,
                 trust_tier, trust_reason, computed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, now())
            ON CONFLICT (driver_id, park_id) DO UPDATE SET
                total_completed_trips = EXCLUDED.total_completed_trips,
                completed_trips_7d = EXCLUDED.completed_trips_7d,
                completed_trips_30d = EXCLUDED.completed_trips_30d,
                first_completed_trip_at = EXCLUDED.first_completed_trip_at,
                last_completed_trip_at = EXCLUDED.last_completed_trip_at,
                trust_tier = EXCLUDED.trust_tier,
                trust_reason = EXCLUDED.trust_reason,
                computed_at = now()
        """, (
            driver_id,
            park_id,
            trust_data["total_completed_trips"],
            trust_data["completed_trips_7d"],
            trust_data["completed_trips_30d"],
            trust_data["first_completed_trip_at"],
            trust_data["last_completed_trip_at"],
            trust_data["trust_tier"],
            Json(trust_data["trust_reason"]),
        ))
        conn.commit()
        cur.close()


# ── Fase 1F-1: Bank Account Normalization & Hashing ──

import hashlib
import re


def normalize_bank_account(bank_name, account_number):
    """Normaliza bank_name y account_number para clustering seguro.
    Retorna (normalized_bank_name, normalized_account_number, cluster_key_hash).
    """
    bn = (bank_name or "").strip().lower()
    an = (account_number or "").strip()
    import re
    bn_clean = re.sub(r'[^a-z0-9]', '', bn)
    an_clean = re.sub(r'[^a-z0-9]', '', an)
    return bn_clean, an_clean


def mask_account_number(account_number):
    """Enmascara numero de cuenta. NUNCA devuelve valor completo.
    len >= 8: 1234****5678
    len < 8: ****78
    null/vacio: None
    """
    if not account_number:
        return None
    s = str(account_number).strip()
    if not s:
        return None
    if len(s) >= 8:
        return s[:4] + "****" + s[-4:]
    return "****" + s[-2:]


def hash_bank_cluster_key(bank_name, account_number):
    """Hash SHA-256 deterministico para cluster key.
    Input: normalized_bank_name + '|' + normalized_account_number.
    Si BANK_CLUSTER_SALT esta configurado, se usa como prefijo.
    NUNCA se imprime el salt.
    """
    bn, an = normalize_bank_account(bank_name, account_number)
    raw = bn + "|" + an
    try:
        from app.settings import settings
        salt = settings.BANK_CLUSTER_SALT
        if salt:
            raw = salt + ":" + raw
    except Exception:
        pass
    return hashlib.sha256(raw.encode()).hexdigest()
