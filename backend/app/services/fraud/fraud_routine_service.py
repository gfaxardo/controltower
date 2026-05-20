"""Fase 1F — Routine Service.

Orquesta las rutinas antifraude:
- driver_trust
- trip_anomalies (card_high_amount + long_trip_outlier + burst_activity)
- referral_abuse (short_trip_bonus_pattern)
- pickup_clusters
- park_concentration
- identity_clusters (si hay fuente)
- balance_negative (si hay fuente)

Soporta dry_run. Escribe snapshots/cases solo si dry_run=False.
"""
from datetime import datetime, timedelta
from app.db.connection import get_db
from psycopg2.extras import Json
from app.services.fraud.fraud_source_adapter import fetch_normalized_trips, get_bank_identity_rows
from app.services.fraud.fraud_feature_service import upsert_driver_trust_snapshot, normalize_bank_account, mask_account_number, hash_bank_cluster_key
from app.services.fraud.fraud_rules_engine import evaluate_trip, severity_from_score, recommended_action, load_enabled_rules
from app.services.fraud.fraud_case_service import create_or_update_case


def run_routines(date_from=None, date_to=None, driver_id=None, park_id=None,
                 limit=5000, dry_run=True, routines=None, full_universe=False):
    """Ejecuta las rutinas especificadas. full_universe=True usa full_universe para driver_trust."""
    if routines is None:
        routines = ["all"]

    all_summary = {
        "dry_run": dry_run,
        "date_from": date_from,
        "date_to": date_to,
        "limit": limit,
        "routines_requested": routines,
        "results": {},
        "total_trips_analyzed": 0,
        "total_flags": 0,
        "total_cases_created": 0,
        "errors": [],
    }

    for routine in routines:
        try:
            if routine in ("driver_trust", "all"):
                if full_universe:
                    result = routine_driver_trust_full_universe(date_from, date_to, dry_run=dry_run)
                else:
                    result = routine_driver_trust(date_from, date_to, dry_run=dry_run, max_drivers=int(limit))
                all_summary["results"]["driver_trust"] = result

            if routine in ("trip_anomalies", "all"):
                result = routine_trip_anomalies(date_from, date_to, driver_id, park_id, limit, dry_run)
                all_summary["results"]["trip_anomalies"] = result
                all_summary["total_trips_analyzed"] += result.get("trips_analyzed", 0)
                all_summary["total_flags"] += result.get("flags_raised", 0)
                all_summary["total_cases_created"] += result.get("cases_created", 0)

            if routine in ("referral_abuse", "all"):
                result = routine_referral_abuse(date_from, date_to, driver_id, park_id, limit, dry_run)
                all_summary["results"]["referral_abuse"] = result
                all_summary["total_flags"] += result.get("flags_raised", 0)

            if routine in ("pickup_clusters", "all"):
                result = routine_pickup_clusters(date_from, date_to, driver_id, park_id, dry_run)
                all_summary["results"]["pickup_clusters"] = result
                all_summary["total_flags"] += result.get("flags_raised", 0)

            if routine in ("park_concentration", "all"):
                result = routine_park_concentration(dry_run)
                all_summary["results"]["park_concentration"] = result

            if routine in ("identity_clusters", "bank_account_cluster", "all"):
                result = routine_bank_account_cluster(dry_run=dry_run)
                all_summary["results"]["bank_account_cluster"] = result
                all_summary["total_cases_created"] += result.get("cases_created", 0)

            if routine in ("balance_negative", "all"):
                result = routine_balance_negative(dry_run)
                all_summary["results"]["balance_negative"] = result

            # ── Fase 1F-5: Trip Behavior Routines ──
            if routine in ("trip_behavior_all",):
                from app.services.fraud.fraud_behavioral_routines import run_trip_behavior_routines
                result = run_trip_behavior_routines(
                    date_from=date_from, date_to=date_to, park_id=park_id,
                    driver_id=driver_id, window_days=7, dry_run=dry_run,
                    limit=int(limit), routines=None,
                )
                all_summary["results"]["trip_behavior"] = result
                all_summary["total_flags"] += result.get("total_drivers_flagged", 0)
                all_summary["total_cases_created"] += result.get("total_cases_created", 0)
            else:
                # Permitir rutinas conductuales individuales
                behavioral_routines = {
                    "repeated_origin_pattern", "repeated_route_signature",
                    "low_avg_distance_pattern", "low_avg_duration_pattern",
                    "extreme_short_trip_ratio", "low_variance_pattern",
                    "short_trip_farming", "route_loop_pattern",
                    "coordinated_origin_pattern", "trip_behavior_all",
                }
                if routine in behavioral_routines and routine != "trip_behavior_all":
                    from app.services.fraud.fraud_behavioral_routines import run_trip_behavior_routines
                    result = run_trip_behavior_routines(
                        date_from=date_from, date_to=date_to, park_id=park_id,
                        driver_id=driver_id, window_days=7, dry_run=dry_run,
                        limit=int(limit), routines=[routine],
                    )
                    all_summary["results"][routine] = result
                    all_summary["total_flags"] += result.get("total_drivers_flagged", 0)
                    all_summary["total_cases_created"] += result.get("total_cases_created", 0)

        except Exception as e:
            all_summary["errors"].append({"routine": routine, "error": str(e)})

    return all_summary


def routine_driver_trust(date_from=None, date_to=None, dry_run=True, max_drivers=100):
    """Clasifica drivers por confianza. max_drivers limita cuantos procesar en esta corrida."""
    source = "public.trips_2026"

    conditions = ["condicion = 'Completado'"]
    params = {}
    if date_from:
        conditions.append("fecha_inicio_viaje >= %(date_from)s")
        params["date_from"] = date_from
    if date_to:
        conditions.append("fecha_inicio_viaje < %(date_to)s::date + interval '1 day'")
        params["date_to"] = date_to

    where_clause = " AND ".join(conditions)

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT conductor_id AS driver_id, park_id,
                   COUNT(*) AS total_completed,
                   MIN(fecha_inicio_viaje) AS first_trip,
                   MAX(fecha_inicio_viaje) AS last_trip
            FROM {source}
            WHERE {where_clause}
            GROUP BY conductor_id, park_id
            ORDER BY MAX(fecha_inicio_viaje) DESC
            LIMIT {int(max_drivers)}
        """, params)
        drivers = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.close()

    results = {"drivers_analyzed": len(drivers), "trusted": 0, "new_or_unproven": 0,
               "restricted": 0, "unknown": 0, "dry_run": dry_run}

    for d in drivers:
        driver_id_val = d["driver_id"]
        park_id_val = d["park_id"]
        total = d["total_completed"]
        first_trip = d["first_trip"]
        last_trip = d["last_trip"]

        has_restriction = _check_restriction(driver_id_val, park_id_val)

        trust_tier = "new_or_unproven" if total < 50 else "trusted"
        trust_reason = {"reason": "batch_computed", "total_trips": total}
        if has_restriction:
            trust_tier = "restricted"
            trust_reason["reason"] = "active_high_critical_case"
        elif total == 0:
            trust_tier = "unknown"
            trust_reason["reason"] = "no_completed_trips"

        results[trust_tier] = results.get(trust_tier, 0) + 1

        if not dry_run:
            trust_data = {
                "driver_id": driver_id_val,
                "park_id": park_id_val,
                "total_completed_trips": total,
                "completed_trips_7d": 0,
                "completed_trips_30d": 0,
                "first_completed_trip_at": first_trip.isoformat() if first_trip else None,
                "last_completed_trip_at": last_trip.isoformat() if last_trip else None,
                "trust_tier": trust_tier,
                "trust_reason": trust_reason,
            }
            upsert_driver_trust_snapshot(driver_id_val, park_id_val, trust_data)

    return results


def routine_driver_trust_full_universe(date_from=None, date_to=None, dry_run=True, max_drivers=100000):
    """Clasifica TODOS los drivers usando agregacion SQL y batch INSERT.

    Usa una sola query SQL GROUP BY + FILTER para metricas, luego
    un batch INSERT...ON CONFLICT en chunks de 500 filas por round-trip.
    """
    import time, uuid
    from psycopg2.extras import Json, execute_values

    run_code = f"DRIVER_TRUST_FULL-{uuid.uuid4().hex[:8]}"
    t0 = time.time()
    source = "public.trips_2026"
    _log_routine_start(run_code, "driver_trust_full_universe", "full", dry_run, date_from, date_to)

    date_filter = ""
    date_params = {}
    if date_from:
        date_filter = "AND fecha_inicio_viaje >= %(date_from)s"
        date_params["date_from"] = date_from
    if date_to:
        date_filter += " AND fecha_inicio_viaje < %(date_to)s::date + interval '1 day'"
        date_params["date_to"] = date_to

    query = f"""
        SELECT conductor_id AS driver_id, park_id,
               COUNT(*) FILTER (WHERE condicion = 'Completado') AS total_completed,
               COUNT(*) FILTER (WHERE condicion = 'Completado' AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '7 days') AS completed_7d,
               COUNT(*) FILTER (WHERE condicion = 'Completado' AND fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '30 days') AS completed_30d,
               MIN(fecha_inicio_viaje) FILTER (WHERE condicion = 'Completado') AS first_trip,
               MAX(fecha_inicio_viaje) FILTER (WHERE condicion = 'Completado') AS last_trip
        FROM {source}
        WHERE condicion = 'Completado'
          {date_filter}
        GROUP BY conductor_id, park_id
        ORDER BY MAX(fecha_inicio_viaje) DESC
        LIMIT {int(max_drivers)}
    """

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(query, date_params)
        all_drivers = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
        cur.close()

    total_scanned = len(all_drivers)
    results = {"drivers_analyzed": total_scanned, "trusted": 0, "new_or_unproven": 0,
               "restricted": 0, "unknown": 0, "dry_run": dry_run, "written": 0}

    if not dry_run:
        # Batch INSERT en chunks para minimizar round-trips
        chunk = 500
        for i in range(0, len(all_drivers), chunk):
            batch = all_drivers[i:i + chunk]
            rows = []
            for d in batch:
                driver_id_val = d["driver_id"]
                park_id_val = d["park_id"] or ""
                total = d["total_completed"] or 0
                trips_7d = d["completed_7d"] or 0
                trips_30d = d["completed_30d"] or 0
                first_trip = d["first_trip"]
                last_trip = d["last_trip"]

                if total == 0:
                    tier = "unknown"
                    reason = '{"reason":"no_completed_trips"}'
                elif total >= 50:
                    tier = "trusted"
                    reason = '{"reason":"sufficient_history","total_trips":' + str(total) + '}'
                else:
                    tier = "new_or_unproven"
                    reason = '{"reason":"insufficient_history","total_trips":' + str(total) + '}'

                results[tier] = results.get(tier, 0) + 1
                results["written"] += 1

                rows.append((
                    driver_id_val,
                    park_id_val if park_id_val else None,
                    total, trips_7d, trips_30d,
                    first_trip.isoformat() if first_trip else None,
                    last_trip.isoformat() if last_trip else None,
                    tier,
                    reason,
                ))

            with get_db() as wconn:
                wcur = wconn.cursor()
                execute_values(wcur, """
                    INSERT INTO fraud.driver_trust_snapshot
                        (driver_id, park_id, total_completed_trips, completed_trips_7d,
                         completed_trips_30d, first_completed_trip_at, last_completed_trip_at,
                         trust_tier, trust_reason)
                    VALUES %s
                    ON CONFLICT (driver_id, park_id) DO UPDATE SET
                        total_completed_trips = EXCLUDED.total_completed_trips,
                        completed_trips_7d = EXCLUDED.completed_trips_7d,
                        completed_trips_30d = EXCLUDED.completed_trips_30d,
                        first_completed_trip_at = EXCLUDED.first_completed_trip_at,
                        last_completed_trip_at = EXCLUDED.last_completed_trip_at,
                        trust_tier = EXCLUDED.trust_tier,
                        trust_reason = EXCLUDED.trust_reason::jsonb,
                        computed_at = now()
                """, rows, template="(%s,%s,%s,%s,%s,%s,%s,%s,%s)")
                wconn.commit()
                wcur.close()
    else:
        for d in all_drivers:
            total = d["total_completed"] or 0
            if total == 0:
                results["unknown"] = results.get("unknown", 0) + 1
            elif total >= 50:
                results["trusted"] = results.get("trusted", 0) + 1
            else:
                results["new_or_unproven"] = results.get("new_or_unproven", 0) + 1

    elapsed = round(time.time() - t0, 1)
    results["elapsed_seconds"] = elapsed
    _log_routine_end(run_code, "completed", elapsed, results)
    return results


def routine_trip_anomalies(date_from=None, date_to=None, driver_id=None, park_id=None, limit=5000, dry_run=True):
    """Detecta viajes anomalos: card high amount, long outliers, burst activity."""
    trips = fetch_normalized_trips(date_from, date_to, driver_id, park_id, limit)
    # Filtrar viajes duplicados
    trip_ids_seen = set()

    flags_raised = 0
    cases_created = 0
    trips_analyzed = len(trips)

    for trip in trips:
        trip_id = trip.get("source_trip_id")
        if trip_id in trip_ids_seen:
            continue
        trip_ids_seen.add(trip_id)

        driver_id_t = trip.get("driver_id")
        if not driver_id_t:
            continue

        trust_data = compute_driver_trust(driver_id_t, trip.get("park_id"))
        triggered, score, severity = evaluate_trip(trip, trust_data)

        if not triggered:
            continue

        triggered_codes = [t["rule_code"] for t in triggered]
        anomaly_rules = {"HIGH_CARD_AMOUNT_NEW_DRIVER", "LONG_TRIP_OUTLIER", "BURST_ACTIVITY_NEW_DRIVER"}
        if not any(r in anomaly_rules for r in triggered_codes):
            continue

        flags_raised += 1

        if not dry_run:
            _upsert_trip_risk(trip, triggered, score, severity)
            action = recommended_action(triggered, severity)
            case = create_or_update_case(driver_id_t, trip.get("park_id"), severity, score, triggered, action)
            if case and case.get("id"):
                cases_created += 1

    return {"trips_analyzed": trips_analyzed, "flags_raised": flags_raised, "cases_created": cases_created}


def routine_referral_abuse(date_from=None, date_to=None, driver_id=None, park_id=None, limit=5000, dry_run=True):
    """Detecta patrones de viajes cortos para bono referido."""
    trips = fetch_normalized_trips(date_from, date_to, driver_id, park_id, limit)
    flags_raised = 0

    for trip in trips:
        driver_id_t = trip.get("driver_id")
        if not driver_id_t:
            continue
        trust_data = compute_driver_trust(driver_id_t, trip.get("park_id"))
        triggered, score, severity = evaluate_trip(trip, trust_data)
        triggered_codes = [t["rule_code"] for t in triggered]
        if "SHORT_TRIP_BONUS_PATTERN" in triggered_codes:
            flags_raised += 1
            if not dry_run:
                _upsert_trip_risk(trip, triggered, score, severity)
                action = recommended_action(triggered, severity)
                create_or_update_case(driver_id_t, trip.get("park_id"), severity, score, triggered, action)

    return {"flags_raised": flags_raised}


def routine_pickup_clusters(date_from=None, date_to=None, driver_id=None, park_id=None, dry_run=True):
    """Detecta viajes repetidos desde el mismo origen."""
    trips = fetch_normalized_trips(date_from, date_to, driver_id, park_id, limit=5000)
    flags_raised = 0

    for trip in trips:
        driver_id_t = trip.get("driver_id")
        if not driver_id_t:
            continue
        triggered, score, severity = evaluate_trip(trip, {})
        triggered_codes = [t["rule_code"] for t in triggered]
        if "REPEATED_PICKUP_CLUSTER" in triggered_codes:
            flags_raised += 1
            if not dry_run:
                _upsert_trip_risk(trip, triggered, score, severity)
                action = recommended_action(triggered, severity)
                create_or_update_case(driver_id_t, trip.get("park_id"), severity, score, triggered, action)

    return {"flags_raised": flags_raised}


def routine_park_concentration(dry_run=True):
    """Detecta parks con concentracion de drivers sospechosos."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT park_id, COUNT(DISTINCT driver_id) AS suspicious_count
                FROM fraud.driver_risk_snapshot
                WHERE severity IN ('high', 'critical')
                GROUP BY park_id
                HAVING COUNT(DISTINCT driver_id) >= 3
            """)
            parks = [{"park_id": r[0], "suspicious_count": r[1]} for r in cur.fetchall()]
            cur.close()

        if not dry_run:
            with get_db() as conn:
                cur = conn.cursor()
                for p in parks:
                    cur.execute("""
                        INSERT INTO fraud.driver_risk_snapshot
                            (driver_id, park_id, risk_score, severity, triggered_rules,
                             suspicious_trip_count, completed_trip_count,
                             recommended_action, action_reason, computed_at)
                        SELECT
                            'PARK_LEVEL', %s, 20, 'medium',
                            '[{"rule_code":"PARK_CONCENTRATION_RISK"}]'::jsonb,
                            %s, 0,
                            'monitor',
                            %s::jsonb,
                            now()
                        ON CONFLICT (driver_id, park_id) DO UPDATE SET
                            severity = 'medium',
                            triggered_rules = '[{"rule_code":"PARK_CONCENTRATION_RISK"}]'::jsonb,
                            suspicious_trip_count = %s,
                            computed_at = now()
                    """, (
                        p["park_id"], p["suspicious_count"],
                        Json({"suspicious_count": p["suspicious_count"]}),
                        p["suspicious_count"],
                    ))
                conn.commit()
                cur.close()

        return {"parks_flagged": len(parks), "dry_run": dry_run}
    except Exception:
        return {"parks_flagged": 0, "dry_run": dry_run}


def routine_identity_clusters(dry_run=True):
    """Alias para routine_bank_account_cluster. Detecta clusters de cuenta bancaria."""
    return routine_bank_account_cluster(dry_run=dry_run)


def routine_bank_account_cluster(dry_run=True):
    """Detecta clusters de drivers compartiendo cuenta bancaria.

    Usa get_bank_identity_rows(source='auto') para fuentes multiples:
    1. public.payment_details si tiene filas
    2. fraud.payment_identity_source si public.payment_details esta vacia

    NO expone account_number completo. Usa masking y hash.
    NO ejecuta acciones reales.
    """
    result = {
        "total_rows_scanned": 0,
        "total_valid_bank_accounts": 0,
        "total_clusters_detected": 0,
        "clusters_2_plus": 0,
        "clusters_3_plus": 0,
        "clusters_5_plus": 0,
        "drivers_affected": 0,
        "cases_created": 0,
        "cases_updated": 0,
        "recommended_actions_summary": {},
        "source_info": {},
        "dry_run": dry_run,
    }

    # 1. Obtener identidades bancarias del adapter multi-source
    rows, source_info = get_bank_identity_rows(source="auto")
    result["source_info"] = source_info
    result["total_rows_scanned"] = len(rows)

    if not rows:
        return result

    # 2. Agrupar por account_hash
    clusters_map = {}
    for r in rows:
        driver_id = r["driver_id"]
        account_hash = r["account_hash"]
        if not account_hash or not driver_id:
            continue

        if account_hash not in clusters_map:
            clusters_map[account_hash] = {
                "bank_name_norm": r.get("bank_name_norm"),
                "masked_account_number": r.get("masked_account_number"),
                "source_name": r.get("source_name"),
                "drivers": {},
            }
        if driver_id not in clusters_map[account_hash]["drivers"]:
            clusters_map[account_hash]["drivers"][driver_id] = {
                "park_id": r.get("park_id"),
            }

    result["total_valid_bank_accounts"] = len(clusters_map)

    # 3. Filtrar clusters con 2+ drivers
    clusters = []
    for key_hash, cdata in clusters_map.items():
        dc = len(cdata["drivers"])
        if dc >= 2:
            cdata["cluster_key_hash"] = key_hash
            cdata["driver_count"] = dc
            clusters.append(cdata)

    clusters.sort(key=lambda x: x["driver_count"], reverse=True)
    result["total_clusters_detected"] = len(clusters)
    result["clusters_2_plus"] = len(clusters)
    result["clusters_3_plus"] = sum(1 for c in clusters if c["driver_count"] >= 3)
    result["clusters_5_plus"] = sum(1 for c in clusters if c["driver_count"] >= 5)

    # 4. Cruzar con trust_snapshot y risk_snapshot
    driver_ids_batch = set()
    for c in clusters:
        for did in c["drivers"]:
            driver_ids_batch.add(did)

    trust_map = {}
    risk_map = {}
    if driver_ids_batch:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT driver_id, trust_tier FROM fraud.driver_trust_snapshot
                WHERE driver_id = ANY(%s)
            """, (list(driver_ids_batch),))
            for r in cur.fetchall():
                trust_map[r[0]] = r[1]
            cur.execute("""
                SELECT driver_id, risk_score, severity FROM fraud.driver_risk_snapshot
                WHERE driver_id = ANY(%s)
            """, (list(driver_ids_batch),))
            for r in cur.fetchall():
                risk_map[r[0]] = {"risk_score": float(r[1] or 0), "severity": r[2]}
            cur.close()

    # 5. Enriquecer cada cluster y calcular severity
    for c in clusters:
        driver_list = []
        new_count = 0
        restricted_count = 0
        high_critical_count = 0
        for did, dinfo in c["drivers"].items():
            tier = trust_map.get(did, "unknown")
            risk = risk_map.get(did, {})
            driver_entry = {
                "driver_id": did,
                "park_id": dinfo.get("park_id"),
                "trust_tier": tier,
                "driver_risk_score": risk.get("risk_score", 0),
                "driver_severity": risk.get("severity", "low"),
                "total_completed_trips": 0,
            }
            driver_list.append(driver_entry)
            if tier in ("new_or_unproven", "restricted"):
                new_count += 1
            if tier == "restricted":
                restricted_count += 1
            if risk.get("severity") in ("high", "critical"):
                high_critical_count += 1

        c["drivers_array"] = driver_list
        c["new_or_unproven_count"] = new_count
        c["restricted_count"] = restricted_count
        c["high_or_critical_count"] = high_critical_count

        dc = c["driver_count"]
        if dc >= 5:
            c["severity"] = "critical"
        elif high_critical_count > 0 or restricted_count > 0:
            c["severity"] = "critical" if dc >= 3 else "high"
        elif dc >= 3:
            c["severity"] = "high"
        elif new_count > 0:
            c["severity"] = "medium"
        else:
            c["severity"] = "low"

        result["drivers_affected"] += dc

    # 6. Escribir/upsert
    if not dry_run and clusters:
        with get_db() as conn:
            cur = conn.cursor()
            for c in clusters:
                evidence = {
                    "bank_name_norm": c["bank_name_norm"],
                    "masked_account_number": c["masked_account_number"],
                    "driver_count": c["driver_count"],
                    "new_or_unproven_count": c["new_or_unproven_count"],
                    "restricted_count": c["restricted_count"],
                    "high_or_critical_count": c["high_or_critical_count"],
                    "source_name": c.get("source_name", "unknown"),
                    "source_mode": source_info.get("source_mode", "auto"),
                    "rule": "BANK_ACCOUNT_CLUSTER",
                }
                cur.execute("""
                    INSERT INTO fraud.external_identity_clusters
                        (cluster_type, cluster_key_hash, drivers, evidence, severity, computed_at)
                    VALUES ('bank_account', %s, %s, %s, %s, now())
                    ON CONFLICT (cluster_type, cluster_key_hash) DO UPDATE SET
                        drivers = EXCLUDED.drivers,
                        evidence = EXCLUDED.evidence,
                        severity = EXCLUDED.severity,
                        computed_at = now()
                """, (
                    c["cluster_key_hash"],
                    Json(c["drivers_array"]),
                    Json(evidence),
                    c["severity"],
                ))
            conn.commit()
            cur.close()

    # 7. Crear/actualizar casos
    if not dry_run:
        for c in clusters:
            if c["severity"] in ("high", "critical"):
                for d in c["drivers_array"]:
                    triggered = [{
                        "rule_code": "BANK_ACCOUNT_CLUSTER",
                        "rule_name": "Cluster de cuenta bancaria",
                        "severity": c["severity"],
                        "weight": 40,
                        "evidence": {
                            "masked_account": c["masked_account_number"],
                            "driver_count": c["driver_count"],
                            "severity": c["severity"],
                            "source": c.get("source_name", "unknown"),
                        },
                    }]
                    score = 40
                    action = ("disable_autocobro"
                              if c["severity"] == "critical" and d.get("trust_tier") == "new_or_unproven"
                              else "restrict_driver_review")
                    cas = create_or_update_case(d["driver_id"], d.get("park_id"), c["severity"], score, triggered, action)
                    if cas and cas.get("id"):
                        result["cases_created"] += 1

    # 8. Acciones summary
    actions_count = {"review": 0, "restrict_driver_review": 0, "disable_autocobro": 0, "monitor": 0}
    for c in clusters:
        sev = c["severity"]
        if sev == "critical":
            actions_count["disable_autocobro"] += c["driver_count"]
        elif sev == "high":
            actions_count["restrict_driver_review"] += c["driver_count"]
        elif sev == "medium":
            actions_count["review"] += c["driver_count"]
        else:
            actions_count["monitor"] += c["driver_count"]
    result["recommended_actions_summary"] = actions_count

    return result


def routine_balance_negative(dry_run=True):
    """Busca senales de saldo negativo. DISABLED: sin fuente de saldo/PLAC."""
    return {"status": "skipped", "reason": "no_balance_source_available", "dry_run": dry_run}


def _check_restriction(driver_id, park_id=None):
    """Verifica si el driver tiene casos abiertos high/critical."""
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


def _log_routine_start(run_code, routine_name, mode, dry_run, date_from, date_to):
    """Registra inicio de rutina en fraud.routine_run_log."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO fraud.routine_run_log
                    (run_code, routine_name, mode, dry_run, date_from, date_to, status, started_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'started', now())
            """, (run_code, routine_name, mode, dry_run, date_from, date_to))
            conn.commit()
            cur.close()
    except Exception:
        pass


def _log_routine_end(run_code, status, elapsed, results):
    """Registra fin de rutina en fraud.routine_run_log."""
    try:
        from psycopg2.extras import Json
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE fraud.routine_run_log
                SET status = %s, finished_at = now(), duration_seconds = %s,
                    result_summary = %s
                WHERE run_code = %s
            """, (status, elapsed, Json(results), run_code))
            conn.commit()
            cur.close()
    except Exception:
        pass


def _upsert_trip_risk(trip, triggered_rules, risk_score, severity, behavior_window=None):
    """Escribe o actualiza trip_risk_features. Incluye campos de ruta Fase 1F-5."""
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO fraud.trip_risk_features
                    (source_table, source_trip_id, driver_id, park_id, trip_datetime,
                     payment_method, amount, distance, duration_seconds, pickup_cluster_key,
                     pickup_address_norm, route_text, origin_cluster_key, destination_cluster_key,
                     route_signature, reverse_route_signature, route_parse_quality,
                     behavior_window, city, country,
                     triggered_rules, risk_score, severity, computed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                ON CONFLICT (source_table, source_trip_id) DO UPDATE SET
                    triggered_rules = EXCLUDED.triggered_rules,
                    risk_score = EXCLUDED.risk_score,
                    severity = EXCLUDED.severity,
                    behavior_window = EXCLUDED.behavior_window,
                    computed_at = now()
            """, (
                trip.get("source_table"), trip.get("source_trip_id"),
                trip.get("driver_id"), trip.get("park_id"),
                trip.get("trip_datetime"),
                trip.get("payment_method"), trip.get("amount"), trip.get("distance"),
                trip.get("duration_seconds"),
                trip.get("pickup_cluster_key"),
                trip.get("pickup_address"),
                trip.get("route_text"),
                trip.get("origin_cluster_key"),
                trip.get("destination_cluster_key"),
                trip.get("route_signature"),
                trip.get("reverse_route_signature"),
                trip.get("route_parse_quality"),
                behavior_window,
                trip.get("city"), trip.get("country"),
                Json(triggered_rules), risk_score, severity,
            ))
            conn.commit()
            cur.close()
    except Exception:
        pass  # La tabla puede no existir aun
