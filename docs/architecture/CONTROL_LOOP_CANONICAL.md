# CONTROL LOOP — CANONICAL DOCUMENTATION

**Version:** 1.0.0
**Date:** 2026-06-13
**Status:** FIRST DRAFT — Evidence-based from live repo audit
**Engine:** Control Foundation (#1)

---

## 1. OVERVIEW

The Control Loop domain encompasses two related but distinct subsystems:

1. **Plan Data Management** — Upload, parse, version, and resolve plan data (monthly targets) for Plan vs Real comparison
2. **Lima Growth Control Loop** — Driver action tracking, agent management, daily impact measurement for the Growth Machine

This document covers BOTH, as they share the "control loop" naming but operate on different data domains.

---

## 2. PLAN DATA MANAGEMENT (Control Loop — Plan Domain)

### 2.1 Architecture

```
Plan Upload (Excel/CSV)
    │
    ▼
Plan Parser (plan_parser_service.py / control_loop_upload_service.py)
    │
    ▼
ops.plan_trips_monthly (raw plan data)
    │
    ▼
control_loop_business_slice_resolve.py (normalize plan → business slice)
    │
    ▼
ops.v_plan_projection_control_loop (plan for projection)
ops.control_loop_plan_line_to_business_slice (mapping)
    │
    ▼
serving.omniview_projection_daily_fact (projection serving)
    │
    ▼
API (/ops/control-loop/*, /ops/business-slice/omniview-projection)
```

### 2.2 Services

| Service | File | Responsibility |
|---------|------|----------------|
| `control_loop_plan_vs_real_service.py` | `backend/app/services/` | Plan vs Real by business slice (canonical) |
| `control_loop_business_slice_resolve.py` | `backend/app/services/` | Normalize plan lines to business slices |
| `control_loop_upload_service.py` | `backend/app/services/` | Control loop plan upload |
| `control_loop_projection_parser.py` | `backend/app/services/` | Parse projection plan files |
| `control_loop_geo.py` | `backend/app/services/` | Geo normalization for control loop |
| `plan_parser_service.py` | `backend/app/services/` | General plan parser |
| `plan_template_parser_service.py` | `backend/app/services/` | Template-based plan parsing |
| `plan_normalization_service.py` | `backend/app/services/` | Plan data normalization |
| `plan_reconciliation_service.py` | `backend/app/services/` | Plan reconciliation |
| `projection_expected_progress_service.py` | `backend/app/services/` | Projection calculations (3210 lines) |

### 2.3 Key Tables

| Table | Schema | Purpose |
|-------|--------|---------|
| `plan_trips_monthly` | ops | Raw plan data (source of truth) |
| `plan_versions_metadata` | plan | Version metadata (keys, display names) |
| `v_plan_trips_monthly_latest` | ops | Resolves latest active version |
| `v_plan_projection_control_loop` | ops | Plan data normalized for projection |
| `control_loop_plan_line_to_business_slice` | ops | Plan→slice mapping |
| `projection_ownership` | ops | Ownership assignment |

### 2.4 Endpoints

#### Plan Versions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/plan/versions` | List plan versions |
| PATCH | `/plan/versions/{key}` | Update version metadata |
| POST | `/plan/upload_simple` | Simple plan upload |
| POST | `/plan/upload_ruta27_ui` | Ruta27 format upload |
| POST | `/plan/upload_control_loop_projection` | Control loop projection upload |
| GET | `/plan/unmapped-summary` | Unmapped plan lines |
| GET | `/plan/mapping-audit` | Mapping audit |
| GET | `/plan/reconciliation-audit` | Reconciliation audit |

#### Control Loop PvR
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ops/control-loop/plan-versions` | Plan versions for control loop |
| GET | `/ops/control-loop/plan-vs-real` | Plan vs Real by slice |

#### Projection (Omniview)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/ops/business-slice/omniview-projection` | Plan vs Real projection |
| GET | `/ops/business-slice/omniview-projection/serving-plan-versions` | Serving plan versions |

### 2.5 Plan Upload Formats

| Format | Template | Parser |
|--------|----------|--------|
| Simple | Generic CSV | `plan_parser_service.py` |
| Ruta27 | YEGO Ruta27 Excel template | `plan_template_parser_service.py` |
| Control Loop Projection | Projection format | `control_loop_upload_service.py` |

---

## 3. LIMA GROWTH CONTROL LOOP (Growth Machine)

### 3.1 Architecture

```
Opportunity Lists ──→ Actions ──→ Impact Measurement ──→ Attribution
         │                  │              │                    │
         ▼                  ▼              ▼                    ▼
    PENDING_ACTION    ACTION_ATTEMPTED  delta_vs_baseline   AGENT/CAMPAIGN
                      ACTION_CONFIRMED  moved_segment       SEGMENT/CHANNEL
                      NO_ACTION         reactivated
```

### 3.2 Services

| Service | File | Responsibility |
|---------|------|----------------|
| `yego_lima_control_loop_service.py` | `backend/app/services/` | Control loop summary, stale detection |
| `yego_lima_control_loop_sync_service.py` | `backend/app/services/` | Control loop data sync |
| `yego_lima_actionable_list_service.py` | `backend/app/services/` | Build/close actionable lists |
| `yego_lima_action_registry_service.py` | `backend/app/services/` | Action CRUD operations |
| `yego_lima_action_impact_service.py` | `backend/app/services/` | Daily impact calculation |
| `yego_lima_segment_migration_service.py` | `backend/app/services/` | Segment transitions |
| `yego_lima_list_outcome_service.py` | `backend/app/services/` | List outcomes |
| `yego_lima_impact_attribution_service.py` | `backend/app/services/` | Attribution engine |

### 3.3 Endpoints

#### Control Loop (LG-CTRL-1.0A)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/yego-lima-growth/control-loop/summary` | Control loop summary |
| GET | `/yego-lima-growth/control-loop/agents` | Agent summary |
| GET | `/yego-lima-growth/control-loop/stale` | Stale drivers |
| GET | `/yego-lima-growth/control-loop/driver/{id}` | Driver control loop |

#### Growth Control Loop (Fase 2C, 2C.1)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/yego-lima-growth/control-loop/build-actionable-lists` | Build daily lists |
| POST | `/yego-lima-growth/control-loop/close-unmanaged-items` | Close pending items |
| GET | `/yego-lima-growth/control-loop/actionable-list` | Get actionable list |
| POST | `/yego-lima-growth/control-loop/actions` | Create action |
| PATCH | `/yego-lima-growth/control-loop/actions/{id}/status` | Update action status |
| POST | `/yego-lima-growth/control-loop/build-daily-impact` | Build daily impact |
| GET | `/yego-lima-growth/control-loop/agent-performance-summary` | Agent performance |
| GET | `/yego-lima-growth/control-loop/driver-impact-timeline/{id}` | Driver timeline |

#### Segment Migration (Fase 2C.1)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/yego-lima-growth/control-loop/build-segment-transitions` | Build transitions |
| POST | `/yego-lima-growth/control-loop/build-list-outcomes` | Build outcomes |
| GET | `/yego-lima-growth/control-loop/transition-summary` | Transition summary |
| GET | `/yego-lima-growth/control-loop/movement-matrix` | Movement matrix |
| GET | `/yego-lima-growth/control-loop/list-outcome-summary` | Outcome summary |
| GET | `/yego-lima-growth/control-loop/driver-transition-timeline/{id}` | Driver timeline |
| GET | `/yego-lima-growth/control-loop/agent-movement-summary` | Agent movements |
| GET | `/yego-lima-growth/control-loop/campaign-movement-summary` | Campaign movements |

#### Attribution (Fase 2C.2)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/yego-lima-growth/control-loop/build-impact-attribution` | Build attribution |
| GET | `/yego-lima-growth/control-loop/attribution-summary` | Attribution summary |
| GET | `/yego-lima-growth/control-loop/attribution-agents` | By agent |
| GET | `/yego-lima-growth/control-loop/attribution-campaigns` | By campaign |
| GET | `/yego-lima-growth/control-loop/attribution-segments` | By segment |
| GET | `/yego-lima-growth/control-loop/attribution-action-types` | By action type |
| GET | `/yego-lima-growth/control-loop/attribution-channels` | By channel |
| GET | `/yego-lima-growth/control-loop/top-performing-agents` | Top agents |
| GET | `/yego-lima-growth/control-loop/top-performing-campaigns` | Top campaigns |

---

## 4. FRONTEND COMPONENTS

### 4.1 Plan vs Real / Control Loop (Omniview domain)

| Component | File | Description |
|-----------|------|-------------|
| `PlanVsRealView.jsx` | `frontend/src/components/` | Plan vs Real monthly view |
| `WeeklyPlanVsRealView.jsx` | `frontend/src/components/` | Plan vs Real weekly (Phase 2B) |
| `ControlLoopPlanVsRealView.jsx` | `frontend/src/components/` | Control loop PvR view |
| `BusinessSliceOmniviewMatrix.jsx` | `frontend/src/components/` | Matrix with projection mode |
| `RealVsProjectionView.jsx` | `frontend/src/components/` | Real vs Projection view |
| `UploadPlan.jsx` | `frontend/src/components/` | Plan upload UI |
| `PlanTabs.jsx` | `frontend/src/components/` | Plan upload tab navigation |

### 4.2 Lima Growth Control Loop

| Component | File | Description |
|-----------|------|-------------|
| `LimaGrowthDashboardV2.jsx` | `frontend/src/pages/` | Full growth dashboard V2 |
| Components under `lima-growth-v2/` | `frontend/src/pages/lima-growth-v2/` | V2 sections: control loop, queue, programs |

---

## 5. DATA FLOW — PLAN UPLOAD TO PROJECTION

```
1. User uploads plan file (Excel/CSV) via UploadPlan.jsx
2. POST /plan/upload_* → plan_parser_service.py validates and inserts into ops.plan_trips_monthly
3. Plan version recorded in plan.plan_versions_metadata
4. control_loop_business_slice_resolve.py normalizes plan lines → ops.control_loop_plan_line_to_business_slice
5. View ops.v_plan_projection_control_loop provides normalized plan data
6. refresh_omniview_projection_facts.py combines plan + real → serving.omniview_projection_daily_fact
7. GET /ops/business-slice/omniview-projection → projection_expected_progress_service.py
8. BusinessSliceOmniviewMatrix.jsx renders Plan vs Real in projection mode
```

---

## 6. DEFAULT PLAN VERSION

`DEFAULT_PLAN_VERSION = ruta27_2026_04_21` (defined in `serving_refresh_scheduler.py:30`)

Active plan versions (from live DB):
- `ruta27_2026_04_21` (DEFAULT)
- `ruta27_2026_04_17`
- `control_loop_20260526_185728`
- `e2e_20260526_165110`
- `unified_fresh_1779825863`
- `unified_v2_test`
- Plus 9 older `ruta27` versions

---

## 7. KNOWN GAPS

| Gap | Status | Priority |
|-----|--------|----------|
| `CT_SCHEDULER_ENABLED=false` in production → projection refresh is manual | OPEN | HIGH |
| Default plan version hardcoded (`ruta27_2026_04_21`) | OPEN | MEDIUM |
| Plan upload clear scripts (`clear_all_plan_data.py`, `clear_all_plans.py`) lack confirmation gates | OPEN | HIGH |
| `clear_plan_version.py` has no backup snapshot before delete | OPEN | MEDIUM |

---

## 8. CERTIFICATION STATUS

| Certification | Document | Status |
|---------------|----------|--------|
| Plan vs Real monthly | `CONTROL_FOUNDATION_CLOSURE_REPORT.md` | CLOSED |
| Plan upload & validation | `CONTROL_FOUNDATION_CLOSURE_REPORT.md` | CLOSED |
| Projection pipeline | `FASE1G_FINAL_CONTROL_FOUNDATION_REGRESSION.md` | CLOSED |
| Control loop PvR by slice | `CF_H1_FINAL_CERTIFICATION.md` | CLOSED |

---

## 9. CROSS-REFERENCES

- [SYSTEM_MAP.md](SYSTEM_MAP.md) — Full system map
- [KNOWN_CONSTRAINTS.md](KNOWN_CONSTRAINTS.md) — Known constraints
- [OMNIVIEW_V2_CANONICAL.md](OMNIVIEW_V2_CANONICAL.md) — Omniview domain
- [GROWTH_MACHINE_CANONICAL.md](GROWTH_MACHINE_CANONICAL.md) — Growth machine domain
- [OMNIVIEW_CANONICAL_REGISTRY.md](../../OMNIVIEW_CANONICAL_REGISTRY.md) — Full registry
- [CONTROL_LOOP_FOUNDATION.md](../lima_growth/CONTROL_LOOP_FOUNDATION.md) — Lima Growth control loop

---

*Generated from live repo audit. Evidence sources: `backend/app/services/control_loop_*.py`, `backend/app/routers/plan.py`, `backend/app/routers/yego_lima_growth_control_loop.py`, `backend/app/routers/yego_lima_control_loop_router.py`, `backend/app/routers/ops.py` (control loop section), `frontend/src/components/PlanVsRealView.jsx`, `frontend/src/components/ControlLoopPlanVsRealView.jsx`.*
