# Yego Pro Profitability — P1.4.5A Baseline + Scenario Governance

## Overview

Convierte el Simulator en herramienta gobernada de escenarios persistentes en PostgreSQL.
Agrega un baseline "OPERACIÓN REAL" calculado desde datos operativos y una registry
de escenarios con CRUD completo.

## Files Modified/Created

| File | Change |
|---|---|
| `backend/sql/yego_pro_simulation_scenarios.sql` | NEW — DDL tabla `ops.yego_pro_simulation_scenarios` |
| `backend/app/services/yego_pro_profitability_service.py` | ADD — `get_baseline_scenario`, `list_scenarios`, `save_scenario`, `update_scenario`, `duplicate_scenario`, `archive_scenario` |
| `backend/app/routers/yego_pro_profitability.py` | ADD — 6 endpoints (baseline + CRUD scenarios) |
| `frontend/src/services/api.js` | ADD — 7 API functions |
| `frontend/src/components/YegoProProfitabilityPage.jsx` | MOD — baseline card, comparator, backend-persisted scenarios table |

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/simulator/baseline` | Calcula "OPERACIÓN REAL" desde datos operativos |
| GET | `/simulator/scenarios` | Lista escenarios guardados |
| POST | `/simulator/scenarios` | Guarda nuevo escenario |
| PATCH | `/simulator/scenarios/{id}` | Actualiza (renombrar, favorito, archivar) |
| POST | `/simulator/scenarios/{id}/duplicate` | Duplica escenario |
| POST | `/simulator/scenarios/{id}/archive` | Archiva (soft-delete) |

## Baseline "OPERACIÓN REAL"

Fuentes:
- `module_weekly_billing` → profit, margin, fuel, maintenance, driver_payout, platform_commission, bono_yango
- `trips_2026` → trips_30d, revenue_30d, active_drivers, ticket_avg
- `module_calculated_shifts` → daily trips day/night breakdown
- `ops.yego_pro_bonus_config` → bonus tables

KPIs mostrados:
- Viajes generales/dia
- Viajes Premier (estimados al 7% de viajes generales)
- Ticket promedio general y Premier
- Revenue 30d
- Conductores activos
- Bono Yango semanal
- Payout conductor %
- Fuente/confianza por KPI

## Scenario Registry

Table: `ops.yego_pro_simulation_scenarios`

| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | |
| park_id | TEXT | |
| scenario_name | TEXT | |
| scenario_type | TEXT | baseline/manual/conservative/aggressive/custom |
| inputs | JSONB | Full simulator input payload |
| outputs | JSONB | Subtotals, bonus_result, shift_label |
| calculation_trace | JSONB | Step-by-step trace |
| confidence | TEXT | HIGH/ESTIMATED |
| is_favorite | BOOLEAN | Star toggle |
| is_archived | BOOLEAN | Soft-delete |
| created_at | TIMESTAMPTZ | |
| updated_at | TIMESTAMPTZ | |

## UI Features

### Baseline Card
- Blue card at top of Simulator
- Shows real operational KPIs from database
- "Cargar baseline" button sets all inputs to real values
- "Duplicar como escenario" creates editable copy
- Source/confidence badges per KPI

### Scenario Management
- Save to PostgreSQL (not localStorage)
- Favorite (star) toggle
- Rename inline
- Duplicate (creates backend copy)
- Archive (soft-delete, recoverable)
- Load scenario restores all inputs and results

### Comparator
- Select "Comparar" on any saved scenario
- Side-by-side columns: revenue, bonos, costos, payout, utilidad, margen, payback
- Delta column shows difference vs current scenario

## QA

| Check | Result |
|---|---|
| `psql -f yego_pro_simulation_scenarios.sql` | PASS — table + 4 indices |
| `python -m compileall backend\app` | PASS (0 errors) |
| `npm run build` | PASS (6.70s, 843 modules) |
| Baseline loads from DB | PASS — status OK, 14 KPI sources |
| Scenario save/read | PASS — persisted in PostgreSQL |
| Scenario rename | PASS |
| Scenario favorite toggle | PASS |
| Scenario duplicate | PASS |
| Scenario archive | PASS — excluded from default list |
| No NaN/undefined/loading infinito | PASS |

## Limitations

- Baseline Premier trips estimated as 7% of general trips (no Premier-specific source)
- `created_by` is always NULL (no auth context in Simulator)
- Comparator displays up to 9 KPIs (not exhaustive)
- Baseline not auto-refreshed on new billing data

## GO / NO-GO

**GO.** Builds pass. Backend tests pass. Scenario governance works end-to-end.
No destructive changes. No contamination of other modules.
