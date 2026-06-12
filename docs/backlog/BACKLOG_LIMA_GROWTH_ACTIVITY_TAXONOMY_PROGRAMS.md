# Lima Growth — Backlog: Activity, Taxonomy, Programs

**Created:** 2026-06-11  
**Phase:** Control Foundation — Lima Growth Foundation  
**Status:** Living document  

---

## Phase 1: Activity Foundation (ACT Series)

| ID | Item | Priority | Effort | Dependency | Status |
|----|------|----------|--------|-----------|--------|
| ACT-1A | Lifecycle tables + partial backfill | P0 | Done | None | DONE |
| ACT-1B | Full historical backfill (trips_2025) | P0 | Done | ACT-1A | DONE |
| ACT-1C | Driver population truth audit | P0 | Done | ACT-1B | DONE |
| ACT-1D | Historical activity closure (gap fix) | P0 | In progress | ACT-1C | IN PROGRESS |
| ACT-2A | Yango API Full Daily Sync | P1 | 3d | ACT-1D | PLANNED |
| ACT-2B | Identity bridge optimization | P2 | 2d | ACT-1D | PLANNED |

---

## Phase 2: Taxonomy (covered by LG-TAX series)

| ID | Item | Priority | Effort | Status |
|----|------|----------|--------|--------|
| TAX-1.0B | Taxonomy shadow (driver_state-based) | P1 | Done | SHADOW (bugged - 86% false positive) |
| TAX-2A | Recency truth audit | P0 | Done | ROOT CAUSE FOUND |
| TAX-2B | Activity from trips_2026 Lima (fix) | P0 | 2d | PLANNED |

---

## Phase 3: Programs Engine V2

| ID | Item | Priority | Effort | Dependency | Status |
|----|------|----------|--------|-----------|--------|
| PROG-1A | 50/14 Program (new driver acceleration) | P1 | 2d | ACT-1D + TAX-2B | PLANNED |
| PROG-1B | 90/300 Program (extended onboarding) | P1 | 2d | PROG-1A | PLANNED |
| PROG-1C | HVR Program (high value recovery) | P1 | 2d | ACT-1D + TAX-2B | PLANNED |
| PROG-1D | ACTIVE_GROWTH Program | P1 | 2d | TAX-2B | PLANNED |
| PROG-1E | STABLE_MONITOR Program | P2 | 1d | TAX-2B | PLANNED |
| PROG-1F | TOP_RETENTION Program | P2 | 1d | TAX-2B | PLANNED |

---

## Phase 4: Legacy Deprecation

| ID | Item | Priority | Effort | Dependency | Status |
|----|------|----------|--------|-----------|--------|
| LEGACY-1 | Deprecate `driver_state_snapshot.completed_orders_week` for activity | P1 | 1d | TAX-2B | PLANNED |
| LEGACY-2 | Deprecate `history_weekly` latest_week for activity | P1 | 1d | TAX-2B | PLANNED |
| LEGACY-3 | Deprecate `driver_360_daily` until repaired | P1 | — | Pipeline fix first | PLANNED |
| LEGACY-4 | Deprecate `program_eligibility` legacy | P2 | 2d | PROG-series | PLANNED |
| LEGACY-5 | Deprecate `prioritized_opportunity` legacy | P2 | 1d | PROG-series | PLANNED |

---

## Phase 5: Special Initiatives

| ID | Item | Priority | Effort | Dependency | Status |
|----|------|----------|--------|-----------|--------|
| INIT-1 | Registered-Not-Activated (RNA) Onboarding Program | P2 | 3d | ACT-1D | PLANNED |
| INIT-2 | Supply-only / Supply Hours Research | P2 | 2d | Yango API | PLANNED |
| INIT-3 | Cancellation Rate Investigation (Lima 60-70%) | P3 | 1d | None | BACKLOG |
| INIT-4 | Fleetroom Dashboard Integration | P3 | 3d | ACT-2A | BACKLOG |

---

## Known Gaps

| Gap | Severity | Fix |
|-----|----------|-----|
| trips_2026 Jan-Apr not in activity_event | HIGH | ACT-1D |
| driver_360_daily broken (179 rows) | HIGH | Pipeline needs repair |
| supply_hours_week = 0 for all drivers | MEDIUM | Supply data pipeline |
| last_trip_at stale for 57% of drivers | MEDIUM | driver_state pipeline |
| last_supply_at NULL for 100% | MEDIUM | Supply data pipeline |
| reactivated_flag not populated | MEDIUM | driver_state pipeline |

---

## Source of Truth Map (Post-ACT-1D)

| Domain | Canonical Source | Trust |
|--------|-----------------|-------|
| Driver Identity | `public.drivers` (Lima park_id) | HIGH |
| Trip Completion | `public.trips_2026` (condicion='Completado') | HIGH |
| Trip Cancellation | `public.trips_2026` (condicion='Cancelado') | HIGH |
| Historical Activity | `growth.yego_lima_driver_activity_event` | HIGH (post fix) |
| Driver Recency | `growth.yego_lima_driver_lifecycle_daily` | HIGH (post fix) |
| Supply Hours | Fleetroom (external) / Yango API per-driver | LOW (no bulk source) |
| Real-time Status | Yango API `current_status` | MEDIUM |
