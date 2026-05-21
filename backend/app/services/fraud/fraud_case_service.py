"""Fase 1F — Case Service.

Crea/actualiza fraud.risk_cases. Evita duplicados.
Un caso abierto por driver_id/park_id/recommended_action/severity.
"""
from datetime import datetime
from app.db.connection import get_db
from psycopg2.extras import Json


def generate_case_code(driver_id):
    """Genera codigo legible: FRAUD-YYYYMMDD-driverid-short."""
    date_str = datetime.now().strftime("%Y%m%d")
    short_id = str(driver_id)[:8].replace("-", "").upper()
    return f"FRAUD-{date_str}-{short_id}"


def find_open_case(driver_id, park_id, severity=None):
    """Busca un caso abierto existente para el driver/park."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if park_id:
                cur.execute("""
                    SELECT id, case_code, severity, status, recommended_action
                    FROM fraud.risk_cases
                    WHERE driver_id = %s AND park_id = %s AND status = 'open'
                    LIMIT 1
                """, (driver_id, park_id))
            else:
                cur.execute("""
                    SELECT id, case_code, severity, status, recommended_action
                    FROM fraud.risk_cases
                    WHERE driver_id = %s AND status = 'open'
                    LIMIT 1
                """, (driver_id,))
            r = cur.fetchone()
            cur.close()
            if r:
                return {
                    "id": r[0], "case_code": r[1], "severity": r[2],
                    "status": r[3], "recommended_action": r[4],
                }
    except Exception:
        pass
    return None


def create_or_update_case(driver_id, park_id, severity, risk_score, triggered_rules, recommended_action,
                         confidence_score=None, confidence_reason=None):
    """Crea o actualiza un caso. Si existe y la severidad sube, actualiza.

    F1F-5C: Admite confidence_score y confidence_reason opcionales.
    Si no se pasan, se calculan desde triggered_rules via fraud_confidence_scoring.
    """
    # Auto-compute confidence if not provided
    if confidence_score is None:
        try:
            from app.services.fraud.fraud_confidence_scoring import compute_case_confidence, build_signal_bundle
            bundle = build_signal_bundle(triggered_rules)
            confidence_score, confidence_reason = compute_case_confidence(bundle)
        except Exception:
            pass

    existing = find_open_case(driver_id, park_id)
    severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}

    with get_db() as conn:
        cur = conn.cursor()

        if existing:
            # Solo actualizar si severidad sube
            current_sev = severity_order.get(existing["severity"], 0)
            new_sev = severity_order.get(severity, 0)
            if new_sev > current_sev:
                cur.execute("""
                    UPDATE fraud.risk_cases
                    SET severity = %s, risk_score = %s, recommended_action = %s,
                        case_reason = %s, case_confidence_score = %s,
                        confidence_reason = %s, updated_at = now()
                    WHERE id = %s
                    RETURNING id, case_code
                """, (severity, risk_score, recommended_action,
                      Json({"triggered_rules": triggered_rules, "updated": True}),
                      confidence_score,
                      Json(confidence_reason) if confidence_reason else None,
                      existing["id"]))
                r = cur.fetchone()
                conn.commit()
                cur.close()
                return {"id": r[0], "case_code": r[1], "updated": True} if r else None

            # Misma severidad: actualizar score y reason
            cur.execute("""
                UPDATE fraud.risk_cases
                SET risk_score = %s, case_reason = %s,
                    case_confidence_score = COALESCE(%s, case_confidence_score),
                    confidence_reason = COALESCE(%s, confidence_reason),
                    updated_at = now()
                WHERE id = %s
            """, (risk_score, Json({"triggered_rules": triggered_rules}),
                  confidence_score,
                  Json(confidence_reason) if confidence_reason else None,
                  existing["id"]))
            conn.commit()
            cur.close()
            return {"id": existing["id"], "case_code": existing["case_code"], "updated": True}

        # Crear nuevo caso
        case_code = generate_case_code(driver_id)
        cur.execute("""
            INSERT INTO fraud.risk_cases
                (case_code, driver_id, park_id, severity, status, risk_score,
                 case_reason, recommended_action, case_confidence_score,
                 confidence_reason, created_at, updated_at)
            VALUES (%s, %s, %s, %s, 'open', %s, %s, %s, %s, %s, now(), now())
            ON CONFLICT (case_code) DO NOTHING
            RETURNING id, case_code
        """, (
            case_code, driver_id, park_id, severity, risk_score,
            Json({"triggered_rules": triggered_rules}),
            recommended_action,
            confidence_score,
            Json(confidence_reason) if confidence_reason else None,
        ))
        r = cur.fetchone()
        if r is None:
            # Ya existia con ese case_code
            cur.execute("SELECT id, case_code FROM fraud.risk_cases WHERE case_code = %s", (case_code,))
            r = cur.fetchone()

        conn.commit()
        cur.close()

    return {"id": r[0], "case_code": r[1], "updated": True} if r else None


def list_cases(status=None, severity=None, park_id=None, driver_id=None,
               recommended_action=None, limit=100, offset=0):
    """Lista casos con filtros."""
    conditions = []
    params = {}

    if status:
        conditions.append("rc.status = %(status)s")
        params["status"] = status
    if severity:
        conditions.append("rc.severity = %(severity)s")
        params["severity"] = severity
    if park_id:
        conditions.append("rc.park_id = %(park_id)s")
        params["park_id"] = park_id
    if driver_id:
        conditions.append("rc.driver_id = %(driver_id)s")
        params["driver_id"] = driver_id
    if recommended_action:
        conditions.append("rc.recommended_action = %(action)s")
        params["action"] = recommended_action

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT id, case_code, driver_id, park_id, severity, status, risk_score,
                   case_reason, recommended_action, created_at, updated_at,
                   case_confidence_score, confidence_reason,
                   calibration_status, calibration_version
            FROM fraud.risk_cases rc
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT {int(limit)} OFFSET {int(offset)}
        """, params)
        rows = cur.fetchall()
        cur.close()

    return [
        {
            "id": r[0], "case_code": r[1], "driver_id": r[2], "park_id": r[3],
            "severity": r[4], "status": r[5], "risk_score": float(r[6] or 0),
            "case_reason": r[7], "recommended_action": r[8],
            "created_at": r[9].isoformat() if r[9] else None,
            "updated_at": r[10].isoformat() if r[10] else None,
            "case_confidence_score": float(r[11]) if r[11] is not None else None,
            "confidence_reason": r[12],
            "calibration_status": r[13],
            "calibration_version": r[14],
        }
        for r in rows
    ]


def review_case(case_id, decision, reviewer, comment=None):
    """Registra una revision de caso."""
    allowed = {"in_review", "approved_action", "rejected", "closed"}
    if decision not in allowed:
        raise ValueError(f"decision invalida: {decision}. Permitidas: {allowed}")

    status_map = {
        "in_review": "in_review",
        "approved_action": "approved_action",
        "rejected": "rejected",
        "closed": "closed",
    }

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE fraud.risk_cases
            SET status = %s, reviewed_by = %s, reviewed_at = now(),
                review_decision = %s, review_comment = %s, updated_at = now()
            WHERE id = %s
            RETURNING id, case_code, status
        """, (status_map[decision], reviewer, decision, comment, case_id))
        r = cur.fetchone()
        conn.commit()
        cur.close()

    if r:
        return {"id": r[0], "case_code": r[1], "status": r[2], "reviewed": True}
    return None
