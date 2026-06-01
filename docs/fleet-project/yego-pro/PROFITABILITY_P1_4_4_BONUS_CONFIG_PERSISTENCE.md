# Yego Pro Profitability — P1.4.4 Bonus Config Persistence

## Overview

Hace persistentes las tablas de bonos Yango del Simulator en PostgreSQL (`ops.yego_pro_bonus_config`), reemplazando la configuracion efimera en memoria.

## Files Modified

| File | Change |
|---|---|
| `backend/sql/yego_pro_bonus_config.sql` | NEW — DDL, indices, seed function |
| `backend/app/services/yego_pro_profitability_service.py` | ADD — `get_bonus_config`, `save_bonus_config`, `reset_bonus_config_to_defaults` |
| `backend/app/routers/yego_pro_profitability.py` | ADD — 3 endpoints (GET/POST/RESET) |
| `frontend/src/services/api.js` | ADD — `getYegoProBonusConfig`, `saveYegoProBonusConfig`, `resetYegoProBonusConfig` |
| `frontend/src/components/YegoProProfitabilityPage.jsx` | MOD — SimulatorPanel: load/save/reset persistence, shortcuts |

## Database Table

**Schema:** `ops.yego_pro_bonus_config`

| Column | Type | Notes |
|---|---|---|
| id | BIGSERIAL PK | Auto-increment |
| park_id | TEXT NOT NULL | Park identifier |
| config_name | TEXT NOT NULL DEFAULT 'default' | Config grouping |
| bonus_type | TEXT NOT NULL | `general_branded`, `general_unbranded`, `premier` |
| trips_min | INTEGER NOT NULL | Minimum trips for tier (>0) |
| bonus_pct | NUMERIC(8,4) NOT NULL | Bonus percentage (>=0) |
| bonus_amount | NUMERIC(12,2) NOT NULL | Bonus amount (>=0) |
| effective_from | DATE NOT NULL DEFAULT CURRENT_DATE | Version start |
| effective_to | DATE NULL | Version end (set on deactivation) |
| is_active | BOOLEAN NOT NULL DEFAULT TRUE | Active version flag |
| source | TEXT NOT NULL DEFAULT 'manual' | `manual`, `seed`, `reset` |
| created_at | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |
| updated_at | TIMESTAMPTZ NOT NULL DEFAULT NOW() | |
| updated_by | TEXT NULL | Future: user tracking |

## Versioning Rules

- **No delete.** Old configs are never deleted.
- **Upsert pattern:** To save new config, all active rows for `(park_id, config_name)` are deactivated (`is_active=FALSE`, `effective_to=CURRENT_DATE`), then new rows are inserted.
- **Historical audit** preserved via `effective_from`/`effective_to` window.

## Seed Defaults

Function `ops.fn_yego_seed_bonus_defaults(park_id, config_name)` inserts defaults only if no active configs exist (idempotent).

**Park inicial:** `64085dd85e124e2c808806f70d527ea8`

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/fleet-project/yego-pro/profitability/simulator/bonus-config` | Read persisted config. Falls back to defaults with `NOT_PERSISTED` status. |
| POST | `/fleet-project/yego-pro/profitability/simulator/bonus-config` | Save new version. Body: `{config_name, tables: {general_branded: [...], general_unbranded: [...], premier: [...]}}` |
| POST | `/fleet-project/yego-pro/profitability/simulator/bonus-config/reset` | Restore defaults as new active version. |

## UI Integration

On Simulator open:
1. Loads `getYegoProSimulatorDefaults()` and `getYegoProBonusConfig()` in parallel.
2. If persisted config exists (`persisted=true`), uses those tables.
3. If not persisted, uses hardcoded defaults and shows "Configuracion no persistida todavia."

### Buttons
- **Guardar tablas de bonos** — saves current UI tables to PostgreSQL.
- **Restaurar defaults** — resets to defaults as new version.

### Status indicators
- Persistido / No persistido badge
- Updated timestamp

### Keyboard Shortcuts
| Shortcut | Action | Scope |
|---|---|---|
| Tab | Next cell in bonus table | Inside bonus config inputs |
| Enter | Next field/row in bonus table | Inside bonus config inputs |
| Ctrl+Enter | Run simulation | Global in Simulator |
| Ctrl+S | Save bonus tables | Only if bonus config panel is open |

## QA Checklist

- [x] Python `compileall` passes (0 errors)
- [x] Frontend `npm run build` passes
- [ ] GET bonus-config without records returns defaults (NOT_PERSISTED)
- [ ] POST saves changes, returns persisted=true
- [ ] GET after save returns persisted=true with saved data
- [ ] Browser refresh maintains changes (loaded from PostgreSQL)
- [ ] Reset saves defaults as new active version
- [ ] Negative values rejected (trips_min > 0, bonus_pct >= 0, bonus_amount >= 0)
- [ ] Invalid bonus_type rejected
- [ ] run_simulation uses persisted tables (no UI override after save)
- [ ] run_simulation uses UI override if edited without saving
- [ ] No NaN, no undefined, no infinite loading

## SQL Deployment

```bash
psql -d yego_integral -f backend/sql/yego_pro_bonus_config.sql
```

## Limitations

- `updated_by` is currently NULL (no auth context in Simulator).
- Only default `config_name="default"` used. Multiple named configs supported by schema but not exposed in UI.
- No row-level audit trigger on table (rely on `effective_from`/`effective_to` + `is_active`).

## GO / NO-GO

**GO.** Builds pass. Schema is additive. No destructive migrations. No refactors of other modules.
