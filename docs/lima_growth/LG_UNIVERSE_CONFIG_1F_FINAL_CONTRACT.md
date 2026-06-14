# LG-UNIVERSE-CONFIG-1F — Universe Config V2 Final Contract

**Date:** 2026-06-14
**Phase:** LG-UNIVERSE-CONFIG-1F (Contract Finalization)
**Mode:** CONTRACT ONLY — No implementation
**Predecessor:** `LG_UNIVERSE_AUDIT_1E_SEMANTICS_CONFIG_CONTRACT.md`
**Status:** CONTRACT_APPROVED

---

## 1. Executive Decision

### LG_UNIVERSE_CONFIG_1F_CONTRACT_APPROVED

The Universe Config V2 contract is frozen. 10 universes defined. Anchor date contract resolved. 12 configurable thresholds. Priority/channel policy established. 6 tables defined with grain, PK, writer, and freshness. Activation governance rules documented.

**No tables created. No rules changed. Ready for LG-UNIVERSE-SIM-1G implementation.**

---

## 2. Why Config V2 Is Needed

Current classification is hardcoded in `refresh_exclusive_driver_worklist_daily()`. Changing thresholds requires code deployment. Simulation requires manual SQL. No version history. Config V2 enables:
- Operator-controlled threshold tuning
- Simulation before activation
- Monday-only activation with audit trail
- Rollback to previous version
- Traceability: which config version produced which worklist

---

## 3. Final Universe Model (10 universes)

| # | Code | Label | Definition | Target | Exit | Channel | Export |
|---|------|-------|-----------|--------|------|---------|--------|
| 1 | NEW_0_14_TO_50 | Nuevos | hire_date ≤14d, trips <50 | 50 trips in window | 50 trips OR >14d | Agent/Call | Yes |
| 2 | REACTIVATED_TO_50 | Reactivados | reactivation_anchor ≤14d, trips <50 | 50 trips in new cycle | 50 trips OR inactive 7d | Agent/Call | Yes |
| 3 | RAMP_15_45_TO_100W | Ramp Up | anchor 15-45d, wk <100 | 100 trips/week | 100/wk OR >45d | Call/WhatsApp | Yes |
| 4 | CONSOLIDATION_46_90 | Consolidation | anchor 46-90d, wk <100 | 100 trips/week | 100/wk OR >90d | Call/Follow-up | Yes |
| 5 | ACTIVE_GROWTH_BAND_UP | Active Growth | anchor >90d, active, 1-99/wk | Move up one band | 100/wk OR band moved | WhatsApp/Call | Yes |
| 6 | PROTECTED_TOP | Protected | wk ≥100 OR (≤14d AND trips ≥50) | Sustain | <100/wk OR inactive | Monitor only | No |
| 7 | RECOVERY_HIGH_VALUE | Recovery High | 7-60d inactive, high value | Reactivation | Activity OR >60d | Agent human | Yes |
| 8 | RECOVERY_LOW_VALUE | Recovery Low | 7-60d inactive, low/default value | Reactivation | Activity OR >60d | SMS/WhatsApp | Yes |
| 9 | CEMETERY_LONG_CHURNED | Cemetery | >60d inactive | Separate from ops | Reactivation | Campaigns only | No |
| 10 | NO_DATA | No Data | Insufficient anchor or fields | Await data | Data available | — | No |

**NEW vs REACTIVATED decision:** Kept separate. New uses hire_date anchor. Reactivated uses post-inactivity reactivation anchor (different lifecycle).

---

## 4. Anchor Date Contract

| Scenario | Anchor Date | Fallback |
|----------|------------|----------|
| Nuevo (never activated) | `hire_date` from driver profile API | `first_trip_at` from explorer_fact | `MIN(date)` from driver_history_daily |
| Reactivado (45+d inactive then returned) | `first_trip_after_inactivity` from daily history | `MIN(date) WHERE date > last_inactivity_end` |
| Ramp / Consolidation / Active Growth | Same anchor as their entry point | `driver_history_daily.MIN(date)` |
| Recovery | N/A (inactivity_days is the metric) | — |
| Cemetery | N/A | — |

**Rule:** Every anchor decision must be recorded in `evidence_json`. If fallback is used, `anchor_source` field must indicate "fallback".

---

## 5. Threshold Parameters (12 configurable)

| Parameter | Default V2 | Editable | Requires Simulation |
|-----------|-----------|----------|-------------------|
| new_window_days | 14 | Yes | Yes |
| new_target_trips | 50 | Yes | Yes |
| reactivation_inactivity_threshold | 45 | Yes | Yes |
| reactivation_target_trips | 50 | Yes | Yes |
| ramp_start_day | 15 | Yes | Yes |
| ramp_end_day | 45 | Yes | Yes |
| consolidation_end_day | 90 | Yes | Yes |
| weekly_target_trips | 100 | Yes | Yes |
| recovery_inactivity_min | 7 | Yes | Yes |
| recovery_inactivity_max | 60 | Yes | Yes |
| cemetery_inactivity | 60 | Yes | Yes |
| high_value_best_week_threshold | 50 | Yes | Yes |
| active_growth_bands | [1-10,11-20,...,76-99] | Yes | Yes |
| capacity_per_agent_per_day | 50 | Yes | No |

---

## 6. Priority + Channel Policy

| Priority | Universe | Channel | Est. Agents (capacity=50) |
|----------|----------|---------|--------------------------|
| 1 | Recovery High | Agente humano | 18 |
| 2 | New / Reactivated | Agente / Call center | 2 |
| 3 | Ramp Up | Call center / WhatsApp | 4 |
| 4 | Consolidation | Call center / Follow-up | 7 |
| 5 | Active Growth | WhatsApp / Call center by band | 33 |
| 6 | Recovery Low | SMS / WhatsApp masivo | — |
| — | Protected | No trabajar | — |
| — | Cemetery | No trabajar (campañas) | — |

**Formula:** `required_agents = CEIL(drivers_in_universe / capacity_per_agent_per_day)`

---

## 7. Table Contract (6 tables)

### 7.1 `growth.universe_config_version`
| Dimension | Value |
|-----------|-------|
| Grain | 1 row per version |
| PK | `version_id` (uuid) |
| Critical columns | version_code, status, effective_from, effective_to, created_by, approved_by |
| Writer | Config service (future) |
| Reader | Worklist writer, Control Loop sync, UI |
| Freshness | N/A (static config) |

### 7.2 `growth.universe_definition_config`
| Dimension | Value |
|-----------|-------|
| Grain | 1 row per (version_id, universe_code) |
| PK | (version_id, universe_code) |
| Critical columns | priority_order, is_actionable, export_to_control_loop, recommended_channel, target_metric, exit_condition_code |
| Writer | Config service |
| Reader | Worklist writer |

### 7.3 `growth.universe_rule_config`
| Dimension | Value |
|-----------|-------|
| Grain | 1 row per (version_id, universe_code, rule_group, field_name) |
| PK | composite |
| Critical columns | field_name, operator, value, condition_logic, null_behavior |
| Writer | Config service |
| Reader | Simulation engine, Worklist writer |

### 7.4 `growth.universe_simulation_run`
| Dimension | Value |
|-----------|-------|
| Grain | 1 row per simulation |
| PK | `simulation_id` (uuid) |
| Critical columns | version_id, source_generated_date, status, total_drivers, diff_vs_current |
| Writer | Simulation engine |
| Reader | UI, approval workflow |

### 7.5 `growth.universe_simulation_result`
| Dimension | Value |
|-----------|-------|
| Grain | 1 row per (simulation_id, driver_profile_id) |
| PK | (simulation_id, driver_profile_id) |
| Critical columns | current_universe, simulated_universe, changed_flag, reason_current, reason_simulated |
| Writer | Simulation engine |
| Reader | UI review |

### 7.6 `growth.universe_config_activation_audit`
| Dimension | Value |
|-----------|-------|
| Grain | 1 row per activation event |
| PK | auto-increment or uuid |
| Critical columns | version_id, activated_at, activated_by, previous_version, rollback_version |
| Writer | Config service |
| Reader | Audit, rollback |

---

## 8. Activation Governance

| Rule | Detail |
|------|--------|
| Active limit | One ACTIVE version per scope (Lima) |
| DRAFT | No impact on production |
| SIMULATED | Requires simulation_result rows |
| APPROVED | Requires operator/approver sign-off |
| ACTIVE | Monday activation preferred |
| RETIRED | Audit preserved, not deleted |
| Rollback | Reverse to previous ACTIVE version |
| Traceability | `control_loop_state` and `worklist_daily` record `config_version` used |
| Weekly changes | One version change per week maximum |

---

## 9. Simulation Impact Report Contract

Every simulation must produce:
- Total drivers by universe (current vs simulated)
- Exportable delta (+/-)
- Drivers moved between universes (count by from→to)
- Workload by channel (driver count)
- Required agents per universe
- Top 5 most-impacted universes
- 20 sample drivers with changed classification
- Risk flags: large migrations, data quality issues, missing anchors

---

## 10. North Star / Backlog Updates

| Document | Update |
|----------|--------|
| `LG_NORTH_STAR_EXCLUSIVE_LISTS_CONTRACT.md` | Section: Universe Config V2 — versioned, simulatable, operator-controlled |
| `GROWTH_MACHINE_CANONICAL.md` | Section: Universe Config V2 tables, activation governance |
| `ACTIVE_SCOPE_CONTRACT.md` | In scope: simulation engine design. Not in scope: implementation yet |
| `KNOWN_CONSTRAINTS.md` | Constraint: hardcoded rules until V2 config is implemented + simulated |

**Backlog phases:**
- LG-UNIVERSE-SIM-1G — Simulation Engine (P0)
- LG-UNIVERSE-ACTIVATE-1H — Active Version Integration (P1)
- LG-UNIVERSE-UI-1I — Config UI / Simulation Review (P1)

---

## 11. What Was Not Implemented

0 tables. 0 migrations. 0 code. 0 rules changes. 0 backend. 0 frontend. 0 Control Loop changes.

---

## 12. Verdict

### LG_UNIVERSE_CONFIG_1F_CONTRACT_APPROVED

| Criterion | Status |
|-----------|--------|
| 10 universes defined | PASS |
| Anchor date contract resolved | PASS |
| 12 configurable thresholds | PASS |
| Priority + channel policy | PASS |
| 6 tables with grain/PK/writer/freshness | PASS |
| Activation governance rules | PASS |
| Simulation impact report contract | PASS |
| North Star updates ready | PASS |
| 0 code changes | PASS |

**Next phase:** LG-UNIVERSE-SIM-1G — Universe Rule Simulation Engine.

---

*Contract frozen. No implementation. Ready for simulation engine build.*
