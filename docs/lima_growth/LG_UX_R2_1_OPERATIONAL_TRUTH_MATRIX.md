# LG-UX-R2.1 — Operational Truth Matrix

**Date:** 2026-06-05
**Phase:** LG-UX-R2.0 + LG-UX-R2.1 — KPI Registry + Operational Truth Audit
**Scope:** Discovery only. No UX changes. No badge/tooltip/design changes.

---

## 1. KPI Inventory — Complete Traceability

### Command Center Section

| # | KPI Label | Section | Component | Endpoint | JSON Field | Service | Source Table/View | Owner Engine | Freshness | Explainability | Status |
|---|-----------|---------|-----------|----------|------------|---------|-------------------|--------------|-----------|----------------|--------|
| 1 | Universo Total | Command Center | MetricCard | `GET /operational-summary` | `universe_total` | `operational_summary_service` | `growth.yango_lima_driver_state_snapshot` | Control Foundation (Diagnostic) | NO | Tooltip only | PASS |
| 2 | Elegibles (Pipeline Bar) | Command Center | Pipeline bar | `GET /operational-summary` | `eligible_total` | `operational_summary_service` | `growth.yango_lima_program_eligibility_daily` | Control Foundation | NO | None | PASS |
| 3 | Priorizados | Command Center | MetricCard + Pipeline bar | `GET /operational-summary` | `prioritized_total` | `operational_summary_service` | `growth.yango_lima_prioritized_opportunity_daily` | Control Foundation | NO | Tooltip only | PASS |
| 4 | Accionables Hoy | Command Center | MetricCard + Pipeline bar | `GET /operational-summary` | `actionable_today` | `operational_summary_service` | `growth.yango_lima_prioritized_opportunity_daily` (WHERE is_actionable_today=true) | Control Foundation | NO | Tooltip + explanation banner | PASS |
| 5 | Capacidad Diaria | Command Center | MetricCard | `GET /operational-summary` + `GET /capacity/summary` | `capacity_total` (summary) or calc from capacity | `operational_summary_service` + `capacity_service` | `growth.yango_lima_capacity_config` | Control Foundation | NO | Tooltip only | PASS |
| 6 | En Cola | Command Center | MetricCard | `GET /operational-summary` | `queue_total` | `operational_summary_service` | `growth.yango_lima_assignment_queue` | Control Foundation | NO | Subtitles (READY/HELD) | PASS |
| 7 | READY | Command Center | MetricCard subtitle | `GET /operational-summary` | `queue_ready` | `operational_summary_service` | `growth.yango_lima_assignment_queue` (WHERE queue_status='READY') | Control Foundation | NO | Implicit in subtitle | PASS |
| 8 | HELD | Command Center | MetricCard subtitle | `GET /operational-summary` | `queue_held` | `operational_summary_service` | `growth.yango_lima_assignment_queue` (WHERE queue_status='HELD') | Control Foundation | NO | Implicit in subtitle | PASS |
| 9 | Exportados (contactos) | Command Center | MetricCard | `GET /operational-summary` | `loopcontrol_contacts_inserted` | `operational_summary_service` | `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | Subtitle (N campanas) | PASS |
| 10 | Exportados (campanas) | Command Center | MetricCard subtitle | `GET /operational-summary` | `loopcontrol_campaigns_exported` | `operational_summary_service` | `growth.yango_lima_loopcontrol_campaign_export` (WHERE export_status='exported') | Control Foundation | NO | Implicit in subtitle | PASS |
| 11 | LoopControl Mode | Command Center | MetricCard | `GET /loopcontrol/config` | `mode` | `loopcontrol_export_service.validate_loopcontrol_config()` | `settings.py` + `growth.yango_lima_loopcontrol_config` | Control Foundation | NO | Subtitle (Integrado/DRY RUN) | PASS |
| 12 | Gap Capacidad | Command Center | MetricCard | `GET /operational-summary` | `actionable_today - capacity_total` (calc in frontend) | Frontend calculation | Multiple | Control Foundation | NO | Tooltip only | **PARTIAL** (frontend calc) |
| 13 | Daily Action Capacity | Command Center | Explanation banner | `GET /operational-summary` | `daily_action_capacity` | `operational_summary_service` | `growth.yango_lima_opportunity_policy_config` | Control Foundation | NO | Explanation text | PASS |
| 14 | By Program (prioritized count) | Command Center | SectionCard grid | `GET /operational-summary` | `by_program[].prioritized` | `operational_summary_service` | `growth.yango_lima_prioritized_opportunity_daily` GROUP BY program | Control Foundation | NO | None | PASS |
| 15 | Engine Health: Opportunity | Command Center | HealthDot | `GET /operational-summary` | `prioritized_total > 0` | Frontend logic from opSummary | Multiple | Control Foundation | NO | Color code (green/yellow/red) | **PARTIAL** (frontend logic, no backend health endpoint) |
| 16 | Engine Health: Queue | Command Center | HealthDot | `GET /operational-summary` | `queue_total > 0` | Frontend logic from opSummary | `growth.yango_lima_assignment_queue` | Control Foundation | NO | Color code | **PARTIAL** |
| 17 | Engine Health: Export | Command Center | HealthDot | `GET /operational-summary` | `loopcontrol_campaigns_exported > 0` | Frontend logic from opSummary | `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | Color code | **PARTIAL** |
| 18 | Engine Health: LoopControl | Command Center | HealthDot | `GET /loopcontrol/config` + `GET /operational-summary` | `enabled && campaigns_exported > 0` | Frontend logic from config + opSummary | `settings.py` + `loopcontrol_campaign_export` | Control Foundation | NO | Color code | **PARTIAL** |

### Programs Section

| # | KPI Label | Section | Component | Endpoint | JSON Field | Service | Source Table/View | Owner Engine | Freshness | Explainability | Status |
|---|-----------|---------|-----------|----------|------------|---------|-------------------|--------------|-----------|----------------|--------|
| 19 | Program Eligible Total | Programs | Card grid | `GET /programs/summary` | `programs[].eligible_total` | `program_eligibility_service.get_program_summary()` | `growth.yango_lima_program_eligibility_daily` | Control Foundation | NO | None | PASS |
| 20 | Program Prioritized Total | Programs | Card grid | `GET /programs/summary` | `programs[].prioritized_total` | `program_eligibility_service` (enriched) | `growth.yango_lima_prioritized_opportunity_daily` BY program | Control Foundation | NO | None | PASS |
| 21 | Program Actionable Today | Programs | Card grid | `GET /programs/summary` | `programs[].actionable_today` | `program_eligibility_service` (enriched) | `growth.yango_lima_prioritized_opportunity_daily` WHERE is_actionable | Control Foundation | NO | None | PASS |
| 22 | Program Queued Total | Programs | Card grid | `GET /programs/summary` | `programs[].queued_total` | `program_eligibility_service` (enriched) | `growth.yango_lima_assignment_queue` BY program | Control Foundation | NO | None | PASS |
| 23 | Program Exported Total | Programs | Card grid | `GET /programs/summary` | `programs[].exported_total` | `program_eligibility_service` (enriched) | `growth.yango_lima_loopcontrol_campaign_export` BY program | Control Foundation | NO | None | PASS |
| 24 | Program Status | Programs | Badge | `GET /programs/summary` | `programs[].status` | `program_eligibility_service` (computed) | Multiple | Control Foundation | NO | None | PASS |
| 25 | Total Drivers | Programs (Driver State) | MetricCardMini | `GET /driver-state/summary` | `total_drivers` | `driver_state_summary_service` | `growth.yango_lima_driver_state_snapshot` | Diagnostic Engine | NO | None | PASS |
| 26 | Snapshot Date | Programs (Driver State) | MetricCardMini | `GET /driver-state/summary` | `latest_date` | `driver_state_summary_service` | `growth.yango_lima_driver_state_snapshot` | Diagnostic Engine | **YES (date)** | Date shown | PASS |
| 27 | Lifecycle distribution | Programs (Driver State) | StateBreakdown bar | `GET /driver-state/summary` | `by_lifecycle_state[].state/count` | `driver_state_summary_service` | `growth.yango_lima_driver_state_snapshot` GROUP BY lifecycle | Diagnostic Engine | NO | Bar chart with % | PASS |
| 28 | Performance distribution | Programs (Driver State) | StateBreakdown bar | `GET /driver-state/summary` | `by_performance_state[].state/count` | `driver_state_summary_service` | `growth.yango_lima_driver_state_snapshot` GROUP BY performance | Diagnostic Engine | NO | Bar chart with % | PASS |
| 29 | Retention distribution | Programs (Driver State) | StateBreakdown bar | `GET /driver-state/summary` | `by_retention_state[].state/count` | `driver_state_summary_service` | `growth.yango_lima_driver_state_snapshot` GROUP BY retention | Diagnostic Engine | NO | Bar chart with % | PASS |

### Execution Queue Section

| # | KPI Label | Section | Component | Endpoint | JSON Field | Service | Source Table/View | Owner Engine | Freshness | Explainability | Status |
|---|-----------|---------|-----------|----------|------------|---------|-------------------|--------------|-----------|----------------|--------|
| 30 | Queue Total Records | Execution Queue | KpiInline | `GET /assignment-queue` | `total_records` | `assignment_queue_service` | `growth.yango_lima_assignment_queue` | Control Foundation | NO | None | PASS |
| 31 | Queue READY Count | Execution Queue | KpiInline | `GET /assignment-queue` | `ready_count` | `assignment_queue_service` | `growth.yango_lima_assignment_queue` WHERE queue_status='READY' | Control Foundation | NO | Color (green) | PASS |
| 32 | Queue HELD Count | Execution Queue | KpiInline | `GET /assignment-queue` | `held_count` | `assignment_queue_service` | `growth.yango_lima_assignment_queue` WHERE queue_status='HELD' | Control Foundation | NO | Color (yellow) | PASS |
| 33 | Queue Exportados (contacts) | Execution Queue | KpiInline | `GET /operational-summary` | `loopcontrol_contacts_inserted` | `operational_summary_service` | `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | None | PASS |
| 34 | Build Result (created count) | Execution Queue | Inline text | `POST /assignment-queue/build` | `created_count` | `assignment_queue_service.create_assignment_batch()` | `growth.yango_lima_assignment_queue` (INSERT) | Control Foundation | NO | Green text feedback | PASS |
| 35 | Export Result: campaign_id | Execution Queue | Green banner | `POST /assignment-queue/export` | `campaign_id_external` | `loopcontrol_export_service.export_from_contacts()` | LoopControl API → `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | Banner with details | PASS |
| 36 | Export Result: contacts_inserted | Execution Queue | Green banner | `POST /assignment-queue/export` | `contacts_inserted` | `loopcontrol_export_service` | LoopControl API response | Control Foundation | NO | Banner with details | PASS |
| 37 | Export Result: contacts_skipped | Execution Queue | Green banner | `POST /assignment-queue/export` | `contacts_skipped` | `loopcontrol_export_service` | LoopControl API response | Control Foundation | NO | Banner with details | PASS |
| 38 | Export Result: export_status | Execution Queue | Green banner | `POST /assignment-queue/export` | `export_status` | `loopcontrol_export_service` | `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | Banner with details | PASS |
| 39 | Queue Record: driver_name | Execution Queue | Table cell | `GET /assignment-queue` | `records[].driver_name` | `assignment_queue_service` | `growth.yango_lima_assignment_queue` | Control Foundation | NO | None | PASS |
| 40 | Queue Record: phone | Execution Queue | Table cell | `GET /assignment-queue` | `records[].phone` | `assignment_queue_service` | `growth.yango_lima_assignment_queue` | Control Foundation | NO | None | PASS |
| 41 | Queue Record: program_code | Execution Queue | Table cell + badge | `GET /assignment-queue` | `records[].program_code` | `assignment_queue_service` | `growth.yango_lima_assignment_queue` | Control Foundation | NO | Badge color | PASS |
| 42 | Queue Record: assigned_channel | Execution Queue | Table cell + ChannelBadge | `GET /assignment-queue` | `records[].assigned_channel` | `assignment_queue_service` | `growth.yango_lima_assignment_queue` | Control Foundation | NO | Badge color | PASS |
| 43 | Queue Record: queue_status | Execution Queue | Table cell + StatusBadge | `GET /assignment-queue` | `records[].queue_status` | `assignment_queue_service` | `growth.yango_lima_assignment_queue` | Control Foundation | NO | Badge color | PASS |
| 44 | Export History: campaign_name | Execution Queue | Table cell | `GET /loopcontrol/exports` | `exports[].campaign_name` | `loopcontrol_export_service.get_export_history()` | `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | None | PASS |
| 45 | Export History: campaign_id_external | Execution Queue | Table cell | `GET /loopcontrol/exports` | `exports[].campaign_id_external` | `loopcontrol_export_service` | `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | Mono font | PASS |
| 46 | Export History: contacts_sent | Execution Queue | Table cell | `GET /loopcontrol/exports` | `exports[].contacts_sent` | `loopcontrol_export_service` | `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | None | PASS |
| 47 | Export History: contacts_inserted | Execution Queue | Table cell | `GET /loopcontrol/exports` | `exports[].contacts_inserted` | `loopcontrol_export_service` | `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | Green color | PASS |
| 48 | Export History: export_status | Execution Queue | Table cell + StatusBadge | `GET /loopcontrol/exports` | `exports[].export_status` | `loopcontrol_export_service` | `growth.yango_lima_loopcontrol_campaign_export` | Control Foundation | NO | StatusBadge | PASS |

### Control Config Section

| # | KPI Label | Section | Component | Endpoint | JSON Field | Service | Source Table/View | Owner Engine | Freshness | Explainability | Status |
|---|-----------|---------|-----------|----------|------------|---------|-------------------|--------------|-----------|----------------|--------|
| 49 | Daily Action Capacity | Config | ConfigItem | `GET /operational-summary` | `daily_action_capacity` | `operational_summary_service` | `growth.yango_lima_opportunity_policy_config` | Control Foundation | NO | Highlight style | PASS |
| 50 | LoopControl Estado | Config | ConfigItem + StatusBadge | `GET /loopcontrol/config` | `enabled` | `loopcontrol_export_service.validate_loopcontrol_config()` | `settings.py` | Control Foundation | NO | LIVE/DRY_RUN badge | PASS |
| 51 | LoopControl Base URL | Config | ConfigItem | `GET /loopcontrol/config` | `base_url_configured` | `loopcontrol_export_service` | `settings.py` | Control Foundation | NO | Configurada/Falta | PASS |
| 52 | LoopControl Integration Key | Config | ConfigItem | `GET /loopcontrol/config` | `integration_key_configured` | `loopcontrol_export_service` | `settings.py` | Control Foundation | NO | Configurada/Falta (no value shown) | PASS |
| 53 | LoopControl Mode | Config | ConfigItem | `GET /loopcontrol/config` | `mode` | `loopcontrol_export_service` | `settings.py` | Control Foundation | NO | Text | PASS |
| 54 | Capacity Channel: agents | Config | Editable table cell | `GET /capacity/config` | `channels[].agents` | `capacity_service` | `growth.yego_lima_capacity_config` | Control Foundation | NO | Editable input | PASS |
| 55 | Capacity Channel: capacity_per_agent | Config | Editable table cell | `GET /capacity/config` | `channels[].capacity_per_agent` | `capacity_service` | `growth.yego_lima_capacity_config` | Control Foundation | NO | Editable input | PASS |
| 56 | Capacity Channel: Total | Config | Table cell (calc) | `GET /capacity/config` | `agents * capacity_per_agent` (calc) | Frontend calculation from capacity data | `growth.yego_lima_capacity_config` | Control Foundation | NO | Bold style | **PARTIAL** (frontend calc) |
| 57 | TOTAL Agents | Config | Summary row | `GET /capacity/config` | SUM of agents | Frontend reduce | `growth.yego_lima_capacity_config` | Control Foundation | NO | Summary row | **PARTIAL** (frontend calc) |
| 58 | TOTAL Capacity | Config | Summary row | `GET /capacity/config` | SUM(agents * capacity) | Frontend reduce | `growth.yego_lima_capacity_config` | Control Foundation | NO | Summary row | **PARTIAL** (frontend calc) |

---

## 2. Traceability Coverage

| Metric | Count |
|--------|-------|
| Total KPIs found | **58** |
| PASS (full traceability) | **49** |
| PARTIAL (frontend calc or logic) | **9** |
| FAIL (missing source) | **0** |
| Coverage % | **84.5% PASS** |

## 3. Missing Ownership

**WARNING:** All 58 KPIs belong to `Control Foundation` engine, except 4 KPIs (#25-28, Driver State) which belong to `Diagnostic Engine`.

No KPIs have dedicated owner assignment in code. Ownership is inferred from source tables:
- `Control Foundation`: 54 KPIs (driver_state_snapshot is shared with Diagnostic Engine for universe_total)
- `Diagnostic Engine`: 4 KPIs (lifecycle/performance/retention distributions)

## 4. Missing Freshness

**CRITICAL GAP:** 0 out of 58 KPIs have freshness metadata.

No KPI shows:
- When data was last refreshed
- Whether data is stale (>24h old)
- Whether the source snapshot is current

The only exception is KPI #26 (`latest_date`) which IS a freshness indicator but is shown as data, not as a freshness badge.

## 5. Missing Explainability

**GAP:** 58 out of 58 KPIs lack formal explainability.

Current explainability is limited to:
- Tooltips on MetricCards (8 KPIs)
- Explanation banner (1 KPI: capacity limit)
- Subtitles with breakdown (4 KPIs)
- Color codes on HealthDot (4 KPIs)

**0 KPIs** have: data lineage, calculation formula, source freshness, or audit trail.

## 6. KPIs Calculated in Frontend

| KPI | Calculation |
|-----|-------------|
| #12 Gap Capacidad | `actionable_today - capacity_total` |
| #15-18 Engine Health | `prioritized_total > 0`, `queue_total > 0`, etc. |
| #56 Channel Total | `agents * capacity_per_agent` |
| #57 TOTAL Agents | `SUM(agents)` |
| #58 TOTAL Capacity | `SUM(agents * capacity_per_agent)` |
| Program % in StateBreakdown | `Math.round((count / total) * 100)` |

These should ideally come from the backend to ensure consistency.

## 7. Endpoints Used (Summary)

| Endpoint | KPIs Served | Status |
|----------|------------|--------|
| `GET /operational-summary` | 18 KPIs | PASS |
| `GET /driver-state/summary` | 5 KPIs | PASS |
| `GET /programs/summary` | 6 KPIs | PASS |
| `GET /assignment-queue` | 7 KPIs + table records | PASS |
| `POST /assignment-queue/build` | 1 KPI (result) | PASS |
| `POST /assignment-queue/export` | 4 KPIs (result) | PASS |
| `GET /loopcontrol/config` | 5 KPIs | PASS |
| `GET /loopcontrol/exports` | 5 KPIs | PASS |
| `GET /capacity/config` | 3 KPIs + table | PASS |

**9 endpoints** serving **58 KPIs** across **4 sections**.

## 8. Risks

| Risk | Severity | Description |
|------|----------|-------------|
| No freshness layer | **HIGH** | 0/58 KPIs show data age. User cannot distinguish fresh vs stale data. |
| Frontend health logic | **MEDIUM** | Engine health indicators computed in JS, not from backend health check. |
| Frontend calculations | **LOW** | 6 KPIs computed in JS (gap, totals, percentages). Could drift from backend. |
| No explainability | **MEDIUM** | No KPI has formal formula/lineage/audit trail. |
| Single engine dependency | **LOW** | 54/58 KPIs depend on Control Foundation. If that engine fails, most dashboard is blind. |

## 9. GO / NO-GO for Freshness Layer (R2.2)

**GO** — The KPI inventory is complete and traceable. All 58 KPIs have identified sources. The main gap is freshness metadata (0/58), which R2.2 should address. No KPIs are untraceable or broken.

### Blockers for R2.2:
- None — inventory is clear, sources are identified, only freshness layer is missing.

### Priority list for R2.2:
1. Add `refreshed_at` to `operational-summary` response (the pipeline endpoint)
2. Add `refreshed_at` to `driver-state/summary` response
3. Add `refreshed_at` to `programs/summary` response
4. Create `/health` or extend summary with staleness indicators
5. Show freshness badge on MetricCards
