# LG_FIX_1A_ENDPOINT_SMOKE — Endpoint Smoke Real

**Generated:** 2026-06-12T19:36  
**Backend:** `127.0.0.1:8000` (local, running)  
**Method:** `Invoke-RestMethod` contra cada endpoint con timeout 30s

---

## Bloque 1: Health / Freshness / Operability

| # | Endpoint | HTTP | Latencia | Size | First-level Keys | Status |
|---|----------|------|----------|------|-----------------|--------|
| 1 | `GET /growth/health` | **200** | 85ms | 730B | `system_status, checked_at, operability, components_healthy, components_degraded, components_critical, stale_assets, broken_assets, root_causes, remediation` | CRITICAL |
| 2 | `GET /growth/freshness` | **200** | 1800ms | 3223B | `assets, checked_at, overall_status, summary` | OK |
| 3 | `GET /growth/operability` | **200** | 3ms | 3272B | `broken_assets, checked_at, components, dependency_issues, governance_operability, remediation, root_causes, stale_assets, summary, system_status` | OK |

**Payload `/growth/health` (resumido):**
```json
{
  "system_status": "CRITICAL",
  "components_healthy": 5,
  "components_degraded": 4,
  "components_critical": 4,
  "stale_assets": ["activity_daily","program_assignment","driver_state_snapshot","movement_fact","activity_weekly","RNA_serving","effectiveness_fact","serving_driver_explorer"],
  "broken_assets": ["program_assignment","driver_state_snapshot","RNA_serving","serving_driver_explorer"],
  "remediation": "CRITICAL: 12 assets are broken."
}
```

---

## Bloque 2: Operational / Refresh

| # | Endpoint | HTTP | Latencia | Size | First-level Keys | Status |
|---|----------|------|----------|------|-----------------|--------|
| 4 | `GET /yego-lima-growth/refresh/operational-date` | **200** | 1116ms | 192B | `is_fresh, max_eligibility_date, max_opportunity_date, max_snapshot_date, operational_data_date, today_action_date` | OK |
| 5 | `GET /yego-lima-growth/operational-summary?date=2026-06-11` | **200** | 745ms | 8287B | `actionable_today, by_program, capacity_total, daily_action_capacity, date, eligible_total, explainability, explanation, freshness, loopcontrol_campaigns_exported, loopcontrol_contacts_inserted, prioritized_total, queue_exported, queue_exported_campaigns, queue_held, queue_ready, queue_total, universe_total` | OK |
| 6 | `GET /yego-lima-growth/driver-state/summary?date=2026-06-11` | **200** | 743ms | 1247B | `by_lifecycle_state, by_performance_state, by_retention_state, date, explainability, freshness, latest_date, total_drivers` | OK |
| 7 | `GET /yego-lima-growth/operational-truth?date=2026-06-11` | **200** | 9469ms | 6522B | `date, kpis, latest_operational_date, overall_status, total_kpis, warnings, warnings_count` | **SLOW** |

**Payload `/yego-lima-growth/operational-date`:**
```json
{
  "operational_data_date": "2026-06-12",
  "today_action_date": "2026-06-12",
  "max_snapshot_date": "2026-06-12",
  "max_eligibility_date": "2026-06-12",
  "max_opportunity_date": "2026-06-12",
  "is_fresh": true
}
```

**Payload `/yego-lima-growth/driver-state/summary?date=2026-06-11`:**
```json
{
  "date": "2026-06-11",
  "total_drivers": 148167,
  "latest_date": "2026-06-11",
  "by_lifecycle_state": [{"count":15811, "state":"ESTABLISHED"}, ...],
  "by_retention_state": [...],
  "by_performance_state": [...]
}
```

---

## Bloque 3: Programs

| # | Endpoint | HTTP | Latencia | Size | First-level Keys | Status |
|---|----------|------|----------|------|-----------------|--------|
| 8 | `GET /yego-lima-growth/programs/summary?date=2026-06-11` | **200** | 1594ms | 2083B | `eligibility_date, freshness, notice, programs, source` | OK |
| 9 | `GET /yego-lima-growth/programs/status?date=2026-06-11` | **200** | 4455ms | 1545B | `critical, date, healthy, programs, total_programs, warning` | SLOW |

**Payload `/programs/summary` (per program):**
```json
{
  "program_code": "PROGRAM_ACTIVE_GROWTH",
  "eligible_total": 17685,
  "prioritized_total": 1125,
  "actionable_today": 0,
  "queued_total": 3,
  ...
}
```
**WARNING: Returns keys `eligible_total`, `prioritized_total` — UI espera `eligible_drivers`, `prioritized`.**

---

## Bloque 4: Taxonomy / Lifecycle

| # | Endpoint | HTTP | Latencia | Size | First-level Keys | Status |
|---|----------|------|----------|------|-----------------|--------|
| 10 | `GET /yego-lima-growth/taxonomy/summary?date=2026-06-11` | **200** | 1933ms | 222B | `distributions, signal_quality_warnings, snapshot_date, taxonomy_version, top_personas, total_drivers` | **DATA MISMATCH** |
| 11 | `GET /drivers/lifecycle-distribution` | **200** | 3105ms | 938B | `freshness_status, kpis, refreshed_at, remediation, source, status, summary, warnings` | OK |

**Payload `/taxonomy/summary`:**
```json
{
  "snapshot_date": "2026-06-11",
  "total_drivers": 0,
  "taxonomy_version": "v2",
  "distributions": {
    "operational_status": [],
    "operational_segment": [],
    "value_overlay": [],
    "momentum": []
  },
  "top_personas": [],
  "signal_quality_warnings": false
}
```
**WARNING: `total_drivers = 0` + todas las distribuciones vacías. La UI espera `lifecycle_distribution`, pero la key real es `distributions`.**

---

## Bloque 5: Movement

| # | Endpoint | HTTP | Latencia | Size | First-level Keys | Status |
|---|----------|------|----------|------|-----------------|--------|
| 12 | `GET /yego-lima-growth/movement/summary?date=2026-06-11` | **200** | 1163ms | 149B | `date, entries, exits, membership_records, program_decisions, state_changes, total_movements, transition_types` | OK (data=0) |
| 13 | `GET /yego-lima-growth/movement/records?date=2026-06-11&limit=5` | **404** | 8ms | — | — | **FAIL** |
| 14 | `GET /yego-lima-growth/movement-analytics/stats` | **200** | 1598ms | 240B | `movement_classes, negative_pct, negative_transitions, net_movement, positive_pct, positive_transitions, total_transitions` | OK |
| 15 | `GET /yego-lima-growth/movement-analytics/matrix` | **200** | 1592ms | 1879B | `lifecycle_transitions, program_transitions, score_distribution, segment_transitions, total_movements` | OK |
| 16 | `GET /yego-lima-growth/movement-analytics/winners?limit=5` | **500** | 771ms | — | — | **FAIL** |
| 17 | `GET /yego-lima-growth/movement-analytics/losers?limit=5` | **500** | 776ms | — | — | **FAIL** |

**Payload `/movement/summary`:**
```json
{ "date": "2026-06-11", "total_movements": 0, "program_decisions": 0, "state_changes": 0, "entries": 0, "exits": 0, "membership_records": 52, "transition_types": {} }
```

**Payload `/movement-analytics/stats`:**
```json
{ "total_transitions": 68473, "positive_transitions": 421, "negative_transitions": 54, "net_movement": 3565.0, "positive_pct": 0.61, "negative_pct": 0.08, "movement_classes": [{"class":"PROGRAM_CHANGE","count":67454},{"class":"SEGMENT_CHANGE","count":1019}] }
```

---

## Bloque 6: RNA (Loyalty + Priority + Pilot)

| # | Endpoint | HTTP | Latencia | Size | First-level Keys | Status |
|---|----------|------|----------|------|-----------------|--------|
| 18 | `GET /yango-loyalty/summary` | **200** | 2321ms | 3798B | `cities, city_categories, data_complete, day_of_month, expected_progress_pct, has_any_targets, kpis, manual_kpis_pending, month, rules, total_days` | OK |
| 19 | `GET /yango-loyalty/kpis` | **200** | 2331ms | 28546B | `expected_progress_pct, kpis, month` | OK |
| 20 | `GET /yango-loyalty/city-comparison` | **200** | 1361ms | 535B | `country, metrics, month` | OK |
| 21 | `GET /yego-lima-growth/rna-priority/summary` | **500** | 773ms | — | — | **FAIL** |
| 22 | `GET /yego-lima-growth/rna-priority/drivers?band=HOT&limit=5` | **500** | 777ms | — | — | **FAIL** |
| 23 | `GET /yego-lima-growth/rna-priority/bands` | **200** | 6ms | 693B | `bands, scoring_signals` | OK |
| 24 | `GET /yego-lima-growth/rna-pilot/summary` | **500** | 771ms | — | — | **FAIL** |

**WARNING: `/yango-loyalty/summary` NO contiene claves `total_rna`, `rna_new`, `rna_reactivable`, `with_phone`. Es el dashboard de KPIs mensuales de Yango Loyalty (AD, Supply Hours, Calls, etc.), NO RNA de Lima Growth.**

---

## Bloque 7: Effectiveness

| # | Endpoint | HTTP | Latencia | Size | First-level Keys | Status |
|---|----------|------|----------|------|-----------------|--------|
| 25 | `GET /yego-lima-growth/effectiveness/summary` | **500** | 770ms | — | — | **FAIL** |

---

## Bloque 8: Driver Explorer / Export

| # | Endpoint | HTTP | Latencia | Size | First-level Keys | Status |
|---|----------|------|----------|------|-----------------|--------|
| 26 | `GET /drivers/activity-summary?limit=5` | **200** | 21163ms | 45B | `drivers, limit, offset, total` | **EXTREMELY SLOW** |
| 27 | `GET /yego-lima-growth/export/options` | **200** | 1ms | 335B | `max_rows, safe_columns, sources` | OK |

---

## Resumen de Fallos

| Endpoint | HTTP | Root Cause Sospechada |
|----------|------|----------------------|
| `/movement/records` | 404 | Ruta no registrada en backend |
| `/movement-analytics/winners` | 500 | Tabla fuente sin datos (v2_movement_fact vacía) |
| `/movement-analytics/losers` | 500 | Igual que winners |
| `/rna-priority/summary` | 500 | Tabla `rna_priority_fact` no existe en DB |
| `/rna-priority/drivers` | 500 | Igual que summary |
| `/rna-pilot/summary` | 500 | Tabla `rna_pilot_measurement_fact` no existe en DB |
| `/effectiveness/summary` | 500 | `program_effectiveness_fact` solo 10 rows, `v2_effectiveness_fact` 0 rows |

**Endpoints 200 OK pero con DATA=0:**
| Endpoint | Issue |
|----------|-------|
| `/taxonomy/summary` | `total_drivers: 0`, distribuciones vacías — último dato 2026-06-10 |
| `/movement/summary` | `total_movements: 0`, `entries: 0`, `exits: 0` — último dato 2026-06-10 |

**Endpoints slow (>5s):**
| Endpoint | Latencia |
|----------|----------|
| `/operational-truth` | 9469ms |
| `/drivers/activity-summary` | 21163ms |
| `/programs/status` | 4455ms |
