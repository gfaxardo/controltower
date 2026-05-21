"""Fase 1F — Fraud Risk Control Router.

Endpoints antifraude bajo prefijo /fraud.
NO toca Omniview, Plan vs Real, ni Fase 2.
"""
from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import datetime
from app.services.fraud.fraud_source_discovery_service import get_canonical_trip_source, get_capabilities
from app.services.fraud.fraud_routine_service import run_routines
from app.services.fraud.fraud_case_service import list_cases, review_case
from app.services.fraud.fraud_action_service import preview_action, manual_log_action
from app.db.connection import get_db

router = APIRouter(prefix="/fraud", tags=["fraud"])


# ── F1F-7: Daily operational status helper ──
def _compute_daily_operational_status(open_cases_count: int, trust_count: int) -> str:
    """Determina si el modulo esta listo para operacion recurrente diaria."""
    if trust_count < 100:
        return "not_ready"
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM fraud.routine_run_log WHERE frequency = 'daily' AND status = 'completed'")
            daily_runs = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fraud.driver_risk_snapshot WHERE behavioral_profile_class IS NOT NULL")
            profiles = cur.fetchone()[0]
            cur.close()
    except Exception:
        daily_runs = 0
        profiles = 0

    if profiles >= 500:
        return "ready"
    elif daily_runs >= 1:
        return "conditional"
    return "not_ready"


@router.get("/health")
async def health():
    """Estado general del modulo antifraude."""
    canonical = get_canonical_trip_source()
    caps = get_capabilities()

    enabled_count = 0
    open_cases_count = 0
    trust_count = 0
    salt_configured = False
    try:
        from app.settings import settings
        salt_configured = bool(settings.BANK_CLUSTER_SALT)
    except Exception:
        pass

    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM fraud.rule_catalog WHERE enabled = true")
            enabled_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fraud.risk_cases WHERE status = 'open'")
            open_cases_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM fraud.driver_trust_snapshot")
            trust_count = cur.fetchone()[0]
            cur.close()
    except Exception:
        pass

    readiness = "not_ready"
    if enabled_count >= 7 and trust_count >= 100:
        readiness = "ready" if salt_configured else "conditional"
    if open_cases_count > 0:
        readiness = "operational" if readiness == "ready" else readiness

    return {
        "status": "operational" if enabled_count >= 7 else "degraded",
        "production_readiness_status": readiness,
        "canonical_trip_source": canonical["source_table"],
        "capabilities": caps,
        "enabled_rules_count": enabled_count,
        "open_cases_count": open_cases_count,
        "drivers_classified": trust_count,
        "salt_configured": salt_configured,
        # ── F1F-7: Daily operational readiness ──
        "fraud_daily_operational_status": _compute_daily_operational_status(open_cases_count, trust_count),
    }


@router.get("/source-discovery")
async def source_discovery():
    """Metadatos de fuentes disponibles."""
    caps = get_capabilities()
    canonical = get_canonical_trip_source()

    # Row counts dinámicos
    pd_rows = 0
    fis_rows = 0
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM public.payment_details WHERE driver_id IS NOT NULL AND TRIM(driver_id) <> '' AND account_number IS NOT NULL AND TRIM(account_number) <> ''")
            pd_rows = cur.fetchone()[0]
            try:
                cur.execute("SELECT COUNT(*) FROM fraud.payment_identity_source WHERE is_active = true")
                fis_rows = cur.fetchone()[0]
            except Exception:
                pass
            cur.close()
    except Exception:
        pass

    return {
        "canonical_source": canonical,
        "capabilities": caps,
        "public_payment_details_rows": pd_rows,
        "fraud_payment_identity_source_rows": fis_rows,
        "bank_identity_source_recommended": "fraud.payment_identity_source" if pd_rows == 0 else "public.payment_details",
        "bank_cluster_ready_for_real_detection": (pd_rows > 0 or fis_rows > 0),
        "missing_sources": [
            "balance_source — sin tabla de saldo/PLAC",
            "bonus_source — sin tabla de bonos con driver_id",
            "pickup_latlng — sin columnas GPS en trips_2026",
            "duration — sin columna de duracion en trips_2026",
        ],
    }


@router.get("/rules")
async def list_rules():
    """Lista todas las reglas."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT id, rule_code, rule_name, description, severity_default,
                       weight, enabled, requires_source, created_at, updated_at
                FROM fraud.rule_catalog ORDER BY weight DESC
            """)
            rows = cur.fetchall()
            cur.close()
        return [
            {
                "id": r[0], "rule_code": r[1], "rule_name": r[2], "description": r[3],
                "severity_default": r[4], "weight": float(r[5]), "enabled": r[6],
                "requires_source": r[7],
                "created_at": r[8].isoformat() if r[8] else None,
                "updated_at": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/rules/{rule_code}")
async def update_rule(rule_code: str, enabled: Optional[bool] = None,
                      weight: Optional[float] = None, severity_default: Optional[str] = None):
    """Habilita/deshabilita o modifica una regla."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            sets = []
            params = {"rc": rule_code}
            if enabled is not None:
                sets.append("enabled = %(enabled)s")
                params["enabled"] = enabled
            if weight is not None:
                sets.append("weight = %(weight)s")
                params["weight"] = weight
            if severity_default is not None:
                sets.append("severity_default = %(severity)s")
                params["severity"] = severity_default
            if not sets:
                raise HTTPException(status_code=400, detail="No hay campos para actualizar")
            sets.append("updated_at = now()")
            cur.execute(
                f"UPDATE fraud.rule_catalog SET {', '.join(sets)} WHERE rule_code = %(rc)s RETURNING rule_code",
                params,
            )
            r = cur.fetchone()
            conn.commit()
            cur.close()
            if r is None:
                raise HTTPException(status_code=404, detail=f"Regla no encontrada: {rule_code}")
        return {"rule_code": rule_code, "updated": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recompute")
async def recompute(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    driver_id: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    limit: int = Query(5000, le=50000),
    dry_run: bool = Query(True),
    routines: Optional[str] = Query(None, description="Comma-separated: driver_trust,trip_anomalies,referral_abuse,pickup_clusters,park_concentration,trip_behavior_all,repeated_origin_pattern,repeated_route_signature,low_avg_distance_pattern,low_avg_duration_pattern,extreme_short_trip_ratio,low_variance_pattern,short_trip_farming,route_loop_pattern,coordinated_origin_pattern,all"),
):
    """Ejecuta recomputo antifraude. dry_run=True no escribe."""
    routine_list = [r.strip() for r in routines.split(",")] if routines else None
    result = run_routines(
        date_from=date_from, date_to=date_to, driver_id=driver_id,
        park_id=park_id, limit=limit, dry_run=dry_run, routines=routine_list,
    )
    return result


@router.get("/drivers/risk")
async def list_driver_risks(
    severity: Optional[str] = Query(None),
    trust_tier: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    driver_id: Optional[str] = Query(None),
    recommended_action: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
):
    """Lista drivers con su perfil de riesgo."""
    try:
        with get_db() as conn:
            cur = conn.cursor()

            conditions = []
            params = {}
            if severity:
                conditions.append("drs.severity = %(severity)s")
                params["severity"] = severity
            if trust_tier:
                conditions.append("dts.trust_tier = %(trust_tier)s")
                params["trust_tier"] = trust_tier
            if park_id:
                conditions.append("drs.park_id = %(park_id)s")
                params["park_id"] = park_id
            if driver_id:
                conditions.append("drs.driver_id = %(driver_id)s")
                params["driver_id"] = driver_id
            if recommended_action:
                conditions.append("drs.recommended_action = %(action)s")
                params["action"] = recommended_action

            where_clause = " AND ".join(conditions) if conditions else "1=1"
            params["limit"] = limit
            params["offset"] = offset

            cur.execute(f"""
                SELECT
                    drs.driver_id, drs.park_id, dts.trust_tier,
                    dts.total_completed_trips, drs.risk_score, drs.severity,
                    drs.suspicious_trip_count, drs.recommended_action,
                    drs.triggered_rules, drs.computed_at
                FROM fraud.driver_risk_snapshot drs
                LEFT JOIN fraud.driver_trust_snapshot dts
                    ON drs.driver_id = dts.driver_id AND COALESCE(drs.park_id, '') = COALESCE(dts.park_id, '')
                WHERE {where_clause}
                ORDER BY drs.risk_score DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, params)
            rows = cur.fetchall()
            cur.close()

        return [
            {
                "driver_id": r[0], "park_id": r[1], "trust_tier": r[2],
                "total_completed_trips": r[3], "risk_score": float(r[4] or 0),
                "severity": r[5], "suspicious_trip_count": r[6],
                "recommended_action": r[7], "triggered_rules": r[8],
                "computed_at": r[9].isoformat() if r[9] else None,
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drivers/{driver_id_param}/risk")
async def get_driver_risk(driver_id_param: str):
    """Perfil completo de riesgo para un driver."""
    try:
        with get_db() as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT * FROM fraud.driver_trust_snapshot WHERE driver_id = %s
            """, (driver_id_param,))
            trust_row = cur.fetchone()
            trust_cols = [desc[0] for desc in cur.description] if trust_row else []

            cur.execute("""
                SELECT * FROM fraud.driver_risk_snapshot WHERE driver_id = %s
            """, (driver_id_param,))
            risk_row = cur.fetchone()
            risk_cols = [desc[0] for desc in cur.description] if risk_row else []

            cur.execute("""
                SELECT * FROM fraud.trip_risk_features
                WHERE driver_id = %s ORDER BY computed_at DESC LIMIT 20
            """, (driver_id_param,))
            trip_rows = cur.fetchall()
            trip_cols = [desc[0] for desc in cur.description] if trip_rows else []

            cur.execute("""
                SELECT * FROM fraud.risk_cases
                WHERE driver_id = %s AND status = 'open'
            """, (driver_id_param,))
            case_rows = cur.fetchall()
            case_cols = [desc[0] for desc in cur.description] if case_rows else []

            # Identity clusters
            cur.execute("""
                SELECT id, cluster_type, cluster_key_hash, severity,
                       drivers, evidence, computed_at
                FROM fraud.external_identity_clusters
                WHERE drivers::jsonb @> %s::jsonb
                ORDER BY computed_at DESC
            """, (f'[{{"driver_id": "{driver_id_param}"}}]',))
            cluster_rows = cur.fetchall()

            cur.close()

        def row_to_dict(row, cols):
            if not row:
                return None
            d = dict(zip(cols, row))
            for k, v in d.items():
                if isinstance(v, datetime):
                    d[k] = v.isoformat()
            return d

        def cluster_to_dict(row):
            if not row:
                return None
            evidence = row[5] or {}
            drivers_data = row[4] or []
            dc = len(drivers_data) if isinstance(drivers_data, list) else 0
            return {
                "cluster_id": row[0],
                "cluster_type": row[1],
                "severity": row[3],
                "masked_account_number": evidence.get("masked_account_number"),
                "bank_name_norm": evidence.get("bank_name_norm"),
                "driver_count": dc,
                "related_drivers": [
                    {"driver_id": d.get("driver_id"), "trust_tier": d.get("trust_tier")}
                    for d in (drivers_data if isinstance(drivers_data, list) else [])
                    if d.get("driver_id") != driver_id_param
                ][:5],
                "computed_at": row[6].isoformat() if row[6] else None,
            }

        # ── Trip behavior signals (Fase 1F-5C) ──
        trip_behavior_signals = None
        try:
            with get_db() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT triggered_rules, risk_score, severity,
                           behavioral_profile_class, behavioral_confidence_score,
                           behavioral_profile_reason
                    FROM fraud.driver_risk_snapshot
                    WHERE driver_id = %s AND action_reason IS NOT NULL
                """, (driver_id_param,))
                beh_row = cur.fetchone()
                if beh_row:
                    triggered = beh_row[0] or []
                    trigger_codes = [t.get("rule_code") if isinstance(t, dict) else None for t in triggered] if isinstance(triggered, list) else []
                    behavioral_codes = [
                        "REPEATED_ORIGIN_PATTERN", "REPEATED_ROUTE_SIGNATURE",
                        "SHORT_TRIP_FARMING_PATTERN", "ROUTE_LOOP_PATTERN",
                        "COORDINATED_ORIGIN_PATTERN", "LOW_AVG_DISTANCE_PATTERN",
                        "LOW_AVG_DURATION_PATTERN", "EXTREME_SHORT_TRIP_RATIO",
                        "LOW_VARIANCE_PATTERN", "BEHAVIORAL_DRIVER_PROFILE",
                    ]
                    has_behavioral = any(c in behavioral_codes for c in trigger_codes if c)
                    trip_behavior_signals = {
                        "has_behavioral_flags": has_behavioral,
                        "behavioral_risk_score": float(beh_row[1] or 0),
                        "behavioral_severity": beh_row[2],
                        "triggered_behavioral_rules": [c for c in trigger_codes if c in behavioral_codes],
                        "behavioral_profile_class": beh_row[3],
                        "behavioral_confidence_score": float(beh_row[4]) if beh_row[4] is not None else None,
                        "behavioral_profile_reason": beh_row[5],
                    }
                cur.close()
        except Exception:
            pass

        return {
            "driver_id": driver_id_param,
            "trust_snapshot": row_to_dict(trust_row, trust_cols),
            "risk_snapshot": row_to_dict(risk_row, risk_cols),
            "suspicious_trips": [row_to_dict(r, trip_cols) for r in trip_rows],
            "open_cases": [row_to_dict(r, case_cols) for r in case_rows],
            "identity_clusters": [cluster_to_dict(r) for r in cluster_rows],
            "trip_behavior_signals": trip_behavior_signals,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cases")
async def get_cases(
    status: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    park_id: Optional[str] = Query(None),
    driver_id: Optional[str] = Query(None),
    recommended_action: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
):
    """Lista casos antifraude."""
    try:
        return list_cases(status, severity, park_id, driver_id, recommended_action, limit, offset)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cases/{case_id}/review")
async def post_case_review(
    case_id: int,
    decision: str = Query(...),
    reviewer: str = Query(...),
    comment: Optional[str] = Query(None),
):
    """Registra una revision de caso."""
    try:
        result = review_case(case_id, decision, reviewer, comment)
        if result is None:
            raise HTTPException(status_code=404, detail="Caso no encontrado")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/preview")
async def post_action_preview(
    driver_id: str = Query(...),
    park_id: Optional[str] = Query(None),
    case_id: Optional[int] = Query(None),
    action_type: str = Query(...),
    reason: Optional[str] = Query(None),
    actor: Optional[str] = Query("system"),
):
    """Genera preview de accion. NO ejecuta accion externa."""
    import json
    reason_dict = json.loads(reason) if reason else {}
    try:
        return preview_action(driver_id, park_id, case_id, action_type, reason_dict, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actions/manual-log")
async def post_action_manual_log(
    driver_id: str = Query(...),
    park_id: Optional[str] = Query(None),
    case_id: Optional[int] = Query(None),
    action_type: str = Query(...),
    result: Optional[str] = Query(None),
    comment: Optional[str] = Query(None),
    actor: Optional[str] = Query("system"),
):
    """Registra accion manual ya ejecutada fuera del sistema."""
    try:
        return manual_log_action(driver_id, park_id, case_id, action_type, result, comment, actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/routines/status")
async def routines_status():
    """Estado de las rutinas antifraude, con frecuencia y readiness.

    F1F-7: Incluye frequency, daily_ready, weekly_ready, last_error.
    """
    status_map = {
        "driver_trust": "ready", "trip_anomalies": "ready",
        "referral_abuse": "ready", "pickup_clusters": "ready",
        "park_concentration": "ready", "bank_account_cluster": "wired",
        "identity_clusters": "ready",
        "balance_negative": "disabled — no balance source",
        "driver_trust_full_universe": "ready",
    }

    # ── F1F-7: Behavioral routines with performance thresholds ──
    behavioral_daily_ready = {
        "repeated_origin_pattern": 30, "low_avg_distance_pattern": 15,
        "low_avg_duration_pattern": 15, "extreme_short_trip_ratio": 15,
        "low_variance_pattern": 15, "short_trip_farming": 15,
        "park_behavior_concentration": 15,
    }
    behavioral_weekly_ready = {
        "repeated_route_signature": 120, "route_loop_pattern": 30,
        "coordinated_origin_pattern": 600, "long_trip_outlier_v2": 120,
    }
    behavioral_monthly_ready = {
        "behavioral_driver_profile": 600,
    }

    routines = []
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT DISTINCT ON (routine_name)
                       routine_name, mode, status, dry_run,
                       duration_seconds, started_at, finished_at, result_summary,
                       frequency
                FROM fraud.routine_run_log
                ORDER BY routine_name, started_at DESC
            """)
            for r in cur.fetchall():
                routines.append({
                    "name": r[0], "mode": r[1], "last_status": r[2],
                    "last_dry_run": r[3], "last_duration_seconds": float(r[4]) if r[4] else None,
                    "last_started_at": r[5].isoformat() if r[5] else None,
                    "last_finished_at": r[6].isoformat() if r[6] else None,
                    "last_result_summary": r[7],
                    "frequency": r[8],
                    "daily_ready": r[0] in behavioral_daily_ready,
                    "weekly_ready": r[0] in behavioral_weekly_ready or r[0] in behavioral_daily_ready,
                })
            cur.close()
    except Exception:
        pass

    # Fill in routines not yet logged
    logged_names = {r["name"] for r in routines}
    for name, default_status in status_map.items():
        if name not in logged_names:
            routines.append({
                "name": name, "mode": None, "last_status": default_status,
                "last_dry_run": None, "last_duration_seconds": None,
                "last_started_at": None, "last_finished_at": None,
                "last_result_summary": None,
                "frequency": None,
                "daily_ready": name in behavioral_daily_ready,
                "weekly_ready": name in behavioral_weekly_ready or name in behavioral_daily_ready,
            })

    return {"routines": routines}


@router.get("/identity-clusters")
async def get_identity_clusters(
    cluster_type: Optional[str] = Query("bank_account"),
    severity: Optional[str] = Query(None),
    min_driver_count: int = Query(2, ge=2),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
):
    """Lista clusters de identidad. NO expone account_number completo."""
    try:
        with get_db() as conn:
            cur = conn.cursor()

            conditions = ["cluster_type = %(ctype)s"]
            params = {"ctype": cluster_type}

            if severity:
                conditions.append("severity = %(severity)s")
                params["severity"] = severity

            where_clause = " AND ".join(conditions)
            params["limit"] = limit
            params["offset"] = offset
            params["min_dc"] = min_driver_count

            cur.execute(f"""
                SELECT id, cluster_type, cluster_key_hash, severity,
                       drivers, evidence, computed_at
                FROM fraud.external_identity_clusters
                WHERE {where_clause}
                  AND jsonb_array_length(drivers) >= %(min_dc)s
                ORDER BY jsonb_array_length(drivers) DESC, computed_at DESC
                LIMIT %(limit)s OFFSET %(offset)s
            """, params)
            rows = cur.fetchall()
            cur.close()

        results = []
        for r in rows:
            drivers_data = r[4] or []
            evidence_data = r[5] or {}
            dc = len(drivers_data) if isinstance(drivers_data, list) else 0

            new_count = evidence_data.get("new_or_unproven_count", 0)
            rest_count = evidence_data.get("restricted_count", 0)
            high_count = evidence_data.get("high_or_critical_count", 0)

            result = {
                "cluster_id": r[0],
                "cluster_type": r[1],
                "cluster_key_hash": r[2],
                "severity": r[3],
                "masked_account_number": evidence_data.get("masked_account_number"),
                "bank_name_norm": evidence_data.get("bank_name_norm"),
                "driver_count": dc,
                "new_or_unproven_count": new_count,
                "restricted_count": rest_count,
                "high_or_critical_count": high_count,
                "drivers": drivers_data,
                "computed_at": r[6].isoformat() if r[6] else None,
            }
            results.append(result)

        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/payment-identity/summary")
async def payment_identity_summary():
    """Resumen de identidades bancarias onboarded. NO expone cuentas completas."""
    try:
        from app.settings import settings

        with get_db() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) FROM public.payment_details WHERE driver_id IS NOT NULL AND TRIM(driver_id) <> '' AND account_number IS NOT NULL AND TRIM(account_number) <> ''")
            pd_rows = cur.fetchone()[0]

            fis_rows = 0
            unique_hashes = 0
            drivers_with_identity = 0
            potential_clusters = 0
            last_batch = None
            try:
                cur.execute("SELECT COUNT(*) FROM fraud.payment_identity_source WHERE is_active = true")
                fis_rows = cur.fetchone()[0]
                cur.execute("SELECT COUNT(DISTINCT account_hash) FROM fraud.payment_identity_source WHERE is_active = true")
                unique_hashes = cur.fetchone()[0]
                cur.execute("SELECT COUNT(DISTINCT driver_id) FROM fraud.payment_identity_source WHERE is_active = true")
                drivers_with_identity = cur.fetchone()[0]
                cur.execute("""
                    SELECT COUNT(*) FROM (
                        SELECT account_hash FROM fraud.payment_identity_source
                        WHERE is_active = true GROUP BY account_hash HAVING COUNT(DISTINCT driver_id) >= 2
                    ) sub
                """)
                potential_clusters = cur.fetchone()[0]
                cur.execute("""
                    SELECT batch_id, source_name, total_rows, inserted_rows, finished_at
                    FROM fraud.payment_identity_import_log
                    WHERE status = 'completed'
                    ORDER BY finished_at DESC LIMIT 1
                """)
                r = cur.fetchone()
                if r:
                    last_batch = {"batch_id": r[0], "source_name": r[1], "total_rows": r[2],
                                  "inserted_rows": r[3], "finished_at": r[4].isoformat() if r[4] else None}
            except Exception:
                pass

            cur.close()

        salt_configured = bool(settings.BANK_CLUSTER_SALT)

        # Check for test data
        test_data_active = False
        try:
            cur.execute("SELECT COUNT(*) FROM fraud.payment_identity_source WHERE source_name = 'test_data' AND is_active = true")
            test_data_active = cur.fetchone()[0] > 0
        except Exception:
            pass

        recompute_needed = (fis_rows > 0 or pd_rows > 0) and potential_clusters > 0

        return {
            "public_payment_details_rows": pd_rows,
            "fraud_payment_identity_source_rows": fis_rows,
            "drivers_with_payment_identity": drivers_with_identity,
            "unique_account_hashes": unique_hashes,
            "potential_clusters_2_plus": potential_clusters,
            "last_import_batch": last_batch,
            "salt_configured": salt_configured,
            "test_data_active": test_data_active,
            "production_ready": salt_configured and not test_data_active,
            "bank_cluster_ready": recompute_needed,
            "recompute_suggested": recompute_needed and not test_data_active,
            "recommended_source": "fraud.payment_identity_source" if pd_rows == 0 else "public.payment_details",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# Fase 1F-5: Trip Behavior Endpoints
# ═══════════════════════════════════════════════════════════════════

@router.get("/trip-behavior/summary")
async def trip_behavior_summary():
    """Resumen del motor de fraude conductual. Agregado desde fraud.risk_cases y fraud.driver_risk_snapshot.

    F1F-5C: Incluye config_version, confidence_distribution, behavioral_profile_distribution, suppressed_cases_count.
    """
    try:
        from app.services.fraud.fraud_behavioral_routines import CONFIG_VERSION

        with get_db() as conn:
            cur = conn.cursor()

            # Trip counts
            cur.execute("SELECT COUNT(*) FROM public.trips_2026 WHERE condicion = 'Completado'")
            trips_total = cur.fetchone()[0]

            # Drivers flagged by behavioral rules
            cur.execute(f"""
                SELECT COUNT(DISTINCT driver_id) FROM fraud.risk_cases
                WHERE status = 'open'
                  AND case_reason IS NOT NULL
            """)
            drivers_flagged = cur.fetchone()[0] or 0

            # Count by rule type
            behavioral_codes = [
                "REPEATED_ORIGIN_PATTERN", "REPEATED_ROUTE_SIGNATURE",
                "SHORT_TRIP_FARMING_PATTERN", "ROUTE_LOOP_PATTERN",
                "COORDINATED_ORIGIN_PATTERN", "LOW_AVG_DISTANCE_PATTERN",
                "LOW_AVG_DURATION_PATTERN", "EXTREME_SHORT_TRIP_RATIO",
                "LOW_VARIANCE_PATTERN", "BEHAVIORAL_DRIVER_PROFILE",
            ]
            rule_counts = {}
            for code in behavioral_codes:
                try:
                    cur.execute("""
                        SELECT COUNT(DISTINCT driver_id) FROM fraud.risk_cases
                        WHERE status = 'open'
                          AND case_reason::text LIKE %s
                    """, (f"%{code}%",))
                    rule_counts[code] = cur.fetchone()[0] or 0
                except Exception:
                    rule_counts[code] = 0

            # ── F1F-5C: Confidence distribution ──
            confidence_distribution = {"low_confidence": 0, "medium_confidence": 0, "high_confidence": 0, "very_high_confidence": 0}
            try:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE case_confidence_score BETWEEN 0 AND 39) AS low,
                        COUNT(*) FILTER (WHERE case_confidence_score BETWEEN 40 AND 59) AS medium,
                        COUNT(*) FILTER (WHERE case_confidence_score BETWEEN 60 AND 79) AS high,
                        COUNT(*) FILTER (WHERE case_confidence_score >= 80) AS very_high
                    FROM fraud.risk_cases
                    WHERE status = 'open' AND case_confidence_score IS NOT NULL
                """)
                r = cur.fetchone()
                if r:
                    confidence_distribution = {
                        "low_confidence": r[0] or 0,
                        "medium_confidence": r[1] or 0,
                        "high_confidence": r[2] or 0,
                        "very_high_confidence": r[3] or 0,
                    }
            except Exception:
                pass

            # ── F1F-5C: Behavioral profile distribution ──
            profile_distribution = {"normal": 0, "watchlist": 0, "suspicious": 0, "high_risk": 0, "critical_pattern": 0}
            try:
                cur.execute("""
                    SELECT behavioral_profile_class, COUNT(*)
                    FROM fraud.driver_risk_snapshot
                    WHERE behavioral_profile_class IS NOT NULL
                    GROUP BY behavioral_profile_class
                """)
                for row in cur.fetchall():
                    if row[0] in profile_distribution:
                        profile_distribution[row[0]] = row[1] or 0
            except Exception:
                pass

            # ── F1F-5C: Suppressed cases count (from routine_run_log) ──
            suppressed_cases = 0
            try:
                cur.execute("""
                    SELECT COALESCE(SUM((result_summary->>'suppressed')::int), 0)
                    FROM fraud.routine_run_log
                    WHERE routine_name IN (
                        'repeated_origin_pattern', 'repeated_route_signature',
                        'short_trip_farming', 'route_loop_pattern',
                        'coordinated_origin_pattern', 'low_avg_distance_pattern',
                        'low_avg_duration_pattern', 'extreme_short_trip_ratio',
                        'low_variance_pattern', 'behavioral_driver_profile'
                    )
                """)
                suppressed_cases = cur.fetchone()[0] or 0
            except Exception:
                pass

            # Top behavioral risk drivers
            cur.execute("""
                SELECT driver_id, park_id, risk_score, severity, action_reason,
                       behavioral_profile_class, behavioral_confidence_score
                FROM fraud.driver_risk_snapshot
                WHERE action_reason IS NOT NULL
                ORDER BY risk_score DESC
                LIMIT 10
            """)
            top_drivers = []
            for r in cur.fetchall():
                action_reason = r[4] or {}
                top_drivers.append({
                    "driver_id": r[0],
                    "park_id": r[1],
                    "risk_score": float(r[2] or 0),
                    "severity": r[3],
                    "behavioral_risk_score": action_reason.get("behavioral_risk_score") if isinstance(action_reason, dict) else None,
                    "behavioral_profile_class": r[5],
                    "behavioral_confidence_score": float(r[6]) if r[6] is not None else None,
                })

            # Top origin clusters from cases
            top_origins = []
            try:
                cur.execute("""
                    SELECT case_reason->'evidence'->>'origin_cluster_key' AS origin_key,
                           COUNT(*) AS case_count
                    FROM fraud.risk_cases
                    WHERE status = 'open'
                      AND case_reason->'evidence'->>'origin_cluster_key' IS NOT NULL
                    GROUP BY case_reason->'evidence'->>'origin_cluster_key'
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                """)
                top_origins = [{"origin_key": r[0][:80] if r[0] else None, "case_count": r[1]} for r in cur.fetchall()]
            except Exception:
                pass

            # Top route signatures
            top_routes = []
            try:
                cur.execute("""
                    SELECT case_reason->'evidence'->>'route_signature' AS route_sig,
                           COUNT(*) AS case_count
                    FROM fraud.risk_cases
                    WHERE status = 'open'
                      AND case_reason->'evidence'->>'route_signature' IS NOT NULL
                    GROUP BY case_reason->'evidence'->>'route_signature'
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                """)
                top_routes = [{"route_signature": r[0][:80] if r[0] else None, "case_count": r[1]} for r in cur.fetchall()]
            except Exception:
                pass

            # Cases created
            cur.execute("SELECT COUNT(*) FROM fraud.risk_cases WHERE status = 'open'")
            open_cases = cur.fetchone()[0]

            cur.close()

        return {
            "config_version": CONFIG_VERSION,
            "trips_analyzed": trips_total,
            "drivers_flagged": drivers_flagged,
            "candidates_count": confidence_distribution.get("low_confidence", 0) + confidence_distribution.get("medium_confidence", 0),
            "cases_count": open_cases,
            "suppressed_cases_count": suppressed_cases,
            "repeated_origin_count": rule_counts.get("REPEATED_ORIGIN_PATTERN", 0),
            "repeated_route_count": rule_counts.get("REPEATED_ROUTE_SIGNATURE", 0),
            "short_trip_farming_count": rule_counts.get("SHORT_TRIP_FARMING_PATTERN", 0),
            "route_loop_count": rule_counts.get("ROUTE_LOOP_PATTERN", 0),
            "coordinated_origin_count": rule_counts.get("COORDINATED_ORIGIN_PATTERN", 0),
            "low_avg_distance_count": rule_counts.get("LOW_AVG_DISTANCE_PATTERN", 0),
            "low_avg_duration_count": rule_counts.get("LOW_AVG_DURATION_PATTERN", 0),
            "extreme_short_trip_ratio_count": rule_counts.get("EXTREME_SHORT_TRIP_RATIO", 0),
            "low_variance_count": rule_counts.get("LOW_VARIANCE_PATTERN", 0),
            "confidence_distribution": confidence_distribution,
            "behavioral_profile_distribution": profile_distribution,
            "top_origin_clusters": top_origins,
            "top_route_signatures": top_routes,
            "top_behavioral_risk_drivers": top_drivers,
            "recommended_actions_summary": {
                "review": drivers_flagged,
                "monitor": max(0, drivers_flagged - rule_counts.get("SHORT_TRIP_FARMING_PATTERN", 0)),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# F1F-8: AUTOCOBRO ELIGIBILITY PREVIEW ENDPOINTS
# ═══════════════════════════════════════════════════════════════════

@router.get("/autocobro/eligibility/summary")
async def autocobro_eligibility_summary(
    policy_version: str = Query("autocobro_v1_preview"),
):
    """Resumen de distribucion de elegibilidad de autocobro (preview-only)."""
    try:
        from app.services.fraud.fraud_autocobro_eligibility_service import get_autocobro_eligibility_summary
        result = get_autocobro_eligibility_summary(policy_version)
        result["mode"] = "preview_only"
        result["actions_executed"] = 0
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/autocobro/eligibility")
async def autocobro_eligibility_list(
    policy_version: str = Query("autocobro_v1_preview"),
    status: Optional[str] = Query(None, description="eligible|review_required|restricted|unknown"),
    park_id: Optional[str] = Query(None),
    driver_id: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
):
    """Lista de elegibilidad de autocobro con filtros (preview-only)."""
    try:
        from app.services.fraud.fraud_autocobro_eligibility_service import get_autocobro_eligibility_list
        result = get_autocobro_eligibility_list(
            policy_version=policy_version,
            status=status,
            park_id=park_id,
            driver_id=driver_id,
            limit=limit,
            offset=offset,
        )
        return {
            "policy_version": policy_version,
            "mode": "preview_only",
            "count": len(result),
            "results": result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/autocobro/eligibility/{driver_id}")
async def autocobro_eligibility_detail(
    driver_id: str,
    policy_version: str = Query("autocobro_v1_preview"),
):
    """Detalle de elegibilidad de autocobro para un driver (preview-only)."""
    try:
        from app.services.fraud.fraud_autocobro_eligibility_service import (
            compute_driver_autocobro_eligibility,
        )
        from app.services.fraud.fraud_case_service import list_cases

        trace = compute_driver_autocobro_eligibility(driver_id, park_id=None, policy_version=policy_version)

        open_cases = list_cases(
            status="open",
            driver_id=driver_id,
            limit=20,
            offset=0,
        )

        return {
            "eligibility": trace,
            "open_cases": open_cases,
            "mode": "preview_only",
            "warning": "Esta evaluacion es preview. NO ejecuta accion real de autocobro.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/autocobro/eligibility/recompute")
async def autocobro_eligibility_recompute(
    policy_version: str = Query("autocobro_v1_preview"),
    dry_run: bool = Query(True),
    limit: Optional[int] = Query(None, le=50000),
    park_id: Optional[str] = Query(None),
):
    """Re-computa elegibilidad de autocobro para universo de drivers (preview-only).

    Si dry_run=false, escribe snapshot en fraud.autocobro_eligibility_snapshot.
    NUNCA ejecuta accion real de autocobro.
    """
    try:
        from app.services.fraud.fraud_autocobro_eligibility_service import recompute_autocobro_eligibility
        result = recompute_autocobro_eligibility(
            policy_version=policy_version,
            dry_run=dry_run,
            limit=limit,
            park_id=park_id,
        )
        result["mode"] = "preview_only"
        result["warning"] = "Ninguna accion real de autocobro fue ejecutada. Preview unicamente."
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
