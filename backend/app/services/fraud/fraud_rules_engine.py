"""Fase 1F — Rules Engine.

Aplica reglas deterministicas desde fraud.rule_catalog.
Calcula triggered_rules, risk_score y severity.
"""
from datetime import datetime, timedelta
from app.db.connection import get_db
from psycopg2.extras import Json


# Thresholds configurables (documentados)
CARD_HIGH_AMOUNT_THRESHOLD = 50000
LONG_TRIP_AMOUNT_THRESHOLD = 80000
LONG_TRIP_DISTANCE_THRESHOLD = 15  # km
SHORT_TRIP_AMOUNT_MAX = 8000
SHORT_TRIP_DISTANCE_MAX = 3  # km
SHORT_TRIP_WINDOW_DAYS = 7
SHORT_TRIP_MIN_COUNT = 5
PICKUP_CLUSTER_WINDOW_DAYS = 7
PICKUP_CLUSTER_MIN_COUNT = 3
BURST_24H_THRESHOLD = 20
BURST_48H_THRESHOLD = 30
BURST_7D_THRESHOLD = 70
PARK_CONCENTRATION_MIN_SUSPICIOUS = 3


def load_enabled_rules():
    """Carga reglas habilitadas desde fraud.rule_catalog."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT rule_code, rule_name, severity_default, weight, description
                FROM fraud.rule_catalog WHERE enabled = true ORDER BY weight DESC
            """)
            rows = cur.fetchall()
            cur.close()
        return [
            {"rule_code": r[0], "rule_name": r[1], "severity_default": r[2],
             "weight": float(r[3]), "description": r[4]}
            for r in rows
        ]
    except Exception:
        return []


def severity_from_score(score):
    if score >= 80:
        return "critical"
    elif score >= 60:
        return "high"
    elif score >= 30:
        return "medium"
    return "low"


def recommended_action(triggered_rules, severity):
    """Determina la accion recomendada basada en reglas y severidad."""
    rule_codes = [r["rule_code"] for r in triggered_rules] if triggered_rules else []

    if severity == "critical":
        if "POST_NEGATIVE_BALANCE_SIGNAL" in rule_codes:
            return "disable_autocobro"
        if "BANK_ACCOUNT_CLUSTER" in rule_codes:
            return "restrict_driver_review"
        return "review"

    if severity == "high":
        if "REFERRAL_BONUS_ABUSE_SIGNAL" in rule_codes or "SHORT_TRIP_BONUS_PATTERN" in rule_codes:
            return "hold_bonus_review"
        if "HIGH_CARD_AMOUNT_NEW_DRIVER" in rule_codes or "LONG_TRIP_OUTLIER" in rule_codes:
            return "restrict_driver_review"
        return "review"

    if severity == "medium":
        if "REPEATED_PICKUP_CLUSTER" in rule_codes:
            return "monitor"
        return "monitor"

    return "no_action"


def evaluate_trip(trip, driver_trust):
    """Evalua un viaje normalizado contra todas las reglas enabled.
    Retorna (triggered_rules, risk_score, severity).
    """
    enabled_rules = load_enabled_rules()
    triggered = []
    total_score = 0

    driver_id = trip.get("driver_id")
    trust_tier = driver_trust.get("trust_tier", "unknown") if driver_trust else "unknown"
    total_trips = driver_trust.get("total_completed_trips", 0) if driver_trust else 0

    for rule in enabled_rules:
        rc = rule["rule_code"]
        hit = False
        evidence = {}

        if rc == "NEW_DRIVER_UNDER_50_TRIPS":
            if total_trips < 50:
                hit = True
                evidence = {"total_completed_trips": total_trips}

        elif rc == "HIGH_CARD_AMOUNT_NEW_DRIVER":
            payment = trip.get("payment_method", "")
            amount = trip.get("amount") or 0
            if trust_tier in ("new_or_unproven", "restricted") and "card" in str(payment).lower() and amount >= CARD_HIGH_AMOUNT_THRESHOLD:
                hit = True
                evidence = {"amount": amount, "payment_method": payment, "threshold": CARD_HIGH_AMOUNT_THRESHOLD}

        elif rc == "REPEATED_PICKUP_CLUSTER":
            cluster = trip.get("pickup_cluster_key")
            if cluster:
                same_cluster_count = _count_trips_same_cluster(driver_id, cluster, PICKUP_CLUSTER_WINDOW_DAYS)
                if same_cluster_count >= PICKUP_CLUSTER_MIN_COUNT:
                    hit = True
                    evidence = {"cluster_key": cluster, "same_cluster_count": same_cluster_count}

        elif rc == "LONG_TRIP_OUTLIER":
            amount = trip.get("amount") or 0
            distance = trip.get("distance") or 0
            if amount >= LONG_TRIP_AMOUNT_THRESHOLD or distance >= LONG_TRIP_DISTANCE_THRESHOLD:
                hit = True
                evidence = {"amount": amount, "distance": distance,
                            "amount_threshold": LONG_TRIP_AMOUNT_THRESHOLD,
                            "distance_threshold": LONG_TRIP_DISTANCE_THRESHOLD}

        elif rc == "SHORT_TRIP_BONUS_PATTERN":
            amount = trip.get("amount") or 0
            distance = trip.get("distance") or 0
            if trust_tier in ("new_or_unproven", "restricted") and amount <= SHORT_TRIP_AMOUNT_MAX:
                recent_short = _count_recent_short_trips(driver_id, SHORT_TRIP_WINDOW_DAYS, SHORT_TRIP_AMOUNT_MAX, SHORT_TRIP_DISTANCE_MAX)
                if recent_short >= SHORT_TRIP_MIN_COUNT:
                    hit = True
                    evidence = {"recent_short_trips": recent_short, "pattern_only": True,
                                "amount": amount, "distance": distance}

        elif rc == "BURST_ACTIVITY_NEW_DRIVER":
            if trust_tier in ("new_or_unproven", "restricted"):
                trips_24h = _count_trips_window(driver_id, 1)
                trips_48h = _count_trips_window(driver_id, 2)
                trips_7d = _count_trips_window(driver_id, 7)
                if trips_24h >= BURST_24H_THRESHOLD or trips_48h >= BURST_48H_THRESHOLD or trips_7d >= BURST_7D_THRESHOLD:
                    hit = True
                    evidence = {"trips_24h": trips_24h, "trips_48h": trips_48h, "trips_7d": trips_7d}

        elif rc == "PARK_CONCENTRATION_RISK":
            park_id = trip.get("park_id")
            if park_id:
                suspicious_count = _count_suspicious_in_park(park_id)
                if suspicious_count >= PARK_CONCENTRATION_MIN_SUSPICIOUS:
                    hit = True
                    evidence = {"park_id": park_id, "suspicious_drivers_in_park": suspicious_count}

        if hit:
            triggered.append({
                "rule_code": rc,
                "rule_name": rule["rule_name"],
                "severity": rule["severity_default"],
                "weight": rule["weight"],
                "evidence": evidence,
            })
            total_score += rule["weight"]

    severity = severity_from_score(total_score)
    return triggered, total_score, severity


def _count_trips_same_cluster(driver_id, cluster_key, window_days):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM fraud.trip_risk_features
                WHERE driver_id = %s AND pickup_cluster_key = %s
                  AND computed_at >= %s
            """, (driver_id, cluster_key, datetime.now() - timedelta(days=window_days)))
            r = cur.fetchone()
            cur.close()
            return r[0] if r else 0
    except Exception:
        return 0


def _count_recent_short_trips(driver_id, window_days, max_amount, max_distance):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cutoff = datetime.now() - timedelta(days=window_days)
            cur.execute("""
                SELECT COUNT(*) FROM public.trips_2026
                WHERE conductor_id = %s AND condicion = 'Completado'
                  AND fecha_inicio_viaje >= %s
                  AND COALESCE(precio_yango_pro, 0) <= %s
                  AND COALESCE(distancia_km, 0) <= %s
            """, (driver_id, cutoff, max_amount, max_distance))
            r = cur.fetchone()
            cur.close()
            return r[0] if r else 0
    except Exception:
        return 0


def _count_trips_window(driver_id, days):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cutoff = datetime.now() - timedelta(days=days)
            cur.execute("""
                SELECT COUNT(*) FROM public.trips_2026
                WHERE conductor_id = %s AND condicion = 'Completado'
                  AND fecha_inicio_viaje >= %s
            """, (driver_id, cutoff))
            r = cur.fetchone()
            cur.close()
            return r[0] if r else 0
    except Exception:
        return 0


def _count_suspicious_in_park(park_id):
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(DISTINCT driver_id) FROM fraud.driver_risk_snapshot
                WHERE park_id = %s AND severity IN ('high', 'critical')
            """, (park_id,))
            r = cur.fetchone()
            cur.close()
            return r[0] if r else 0
    except Exception:
        return 0
