# LG-UI-1A — INFORMATION ARCHITECTURE

**Date:** 2026-06-11  
**Phase:** LG-UI-1A / Dashboard MVP

---

## DASHBOARD ARCHITECTURE

### LAYOUT

```
┌─────────────────────────────────────────────────────────┐
│  FRESHNESS BANNER                                       │
│  Programs: FRESH 0h  |  Queue: FRESH 0h  |  RNA: ...   │
│  System: HEALTHY  |  Scheduler: RUNNING                 │
├─────────────────────────────────────────────────────────┤
│  OVERVIEW  │ PROGRAMS │ SEGMENTS │ MOVEMENT │ RNA │ DX │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                   TAB CONTENT                           │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## TAB 1: OVERVIEW

**Objective:** ¿Dónde está el universo? ¿Está sano? ¿Qué cambió?

**Data sources:** operational_summary (serving_fact) + growth/health + growth/freshness

### KPIs

| KPI | Value | Source |
|-----|-------|--------|
| Total Universe | 18,545 drivers | driver_state_snapshot COUNT DISTINCT |
| Eligible Drivers | 28,128 | program_eligibility_daily COUNT DISTINCT |
| Prioritized Today | 5,383 | prioritized_opportunity_daily COUNT |
| Queue Ready | 52 | assignment_queue (status=READY) |
| Queue Capacity | from config | capacity_config |

### Sections

```
┌─ Overview ──────────────────────────────────────────────┐
│                                                          │
│  [KPI Cards: Universe | Eligible | Prioritized | Queue] │
│                                                          │
│  Program Distribution (bar chart)                        │
│    ACTIVE_GROWTH  ████████████████  17,685              │
│    CHURN_PREVENT  ████████           7,774              │
│    14_90          ███                2,669              │
│                                                          │
│  Queue Status (pie/donut)                                │
│    READY: 52  |  HELD: X  |  EXPORTED: X               │
│                                                          │
│  Channel Utilization (progress bars)                     │
│    LoopControl:  ████████░░  80%                        │
│                                                          │
│  Recent Activity (timeline)                              │
│    Today: 5,383 prioritized, 52 queued                  │
└──────────────────────────────────────────────────────────┘
```

**Actions:** Refresh data, Export queue, View programs detail

---

## TAB 2: PROGRAMS

**Objective:** ¿Qué programas están activos? ¿Cuántos drivers en cada uno?

**Data sources:** program_eligibility_daily, prioritized_opportunity_daily, assignment_queue

### Sections

```
┌─ Programs ──────────────────────────────────────────────┐
│                                                          │
│  Program Cards (4 cards)                                 │
│  ┌─ ACTIVE GROWTH ──────────────────────────────────┐   │
│  │  Eligible: 17,685  |  Prioritized: X  |  Queue: X │   │
│  │  Priority: 4  |  Program: Boost productivity      │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌─ CHURN PREVENTION ───────────────────────────────┐   │
│  │  Eligible: 7,774  |  Prioritized: X  |  Queue: X  │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌─ 14/90 ──────────────────────────────────────────┐   │
│  │  Eligible: 2,669  |  Prioritized: X  |  Queue: X  │   │
│  └──────────────────────────────────────────────────┘   │
│  ┌─ HIGH VALUE RECOVERY ────────────────────────────┐   │
│  │  Eligible: X  |  Prioritized: X  |  Queue: X      │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  Drilldown: Per-program Driver List                     │
│    driver_id | lifecycle | trips_7d | priority | action │
└──────────────────────────────────────────────────────────┘
```

---

## TAB 3: SEGMENTS

**Objective:** Distribución de drivers por lifecycle, actividad, valor, momentum.

**Data sources:** driver_state_snapshot, driver_lifecycle_daily, driver_taxonomy_v2_daily

### Sections

```
┌─ Segments ──────────────────────────────────────────────┐
│                                                          │
│  Lifecycle Distribution (bar chart)                      │
│    ACTIVE     ████████████████████  12,345              │
│    NEW_ACTIVE ████████               5,200              │
│    AT_RISK    ████                   2,500              │
│    DECLINING  ██                     1,200              │
│    CHURNED    █                        800              │
│                                                          │
│  Activity Bands                                          │
│    heavy (200+) | regular (50-199) | light (1-49)       │
│                                                          │
│  Value Tiers (percentile-based)                          │
│    Top 20% | Mid 60% | Bottom 20%                       │
│                                                          │
│  Momentum (trend)                                        │
│    rising | stable | falling                             │
│                                                          │
│  Drilldown: Filter by segment → driver list              │
└──────────────────────────────────────────────────────────┘
```

---

## TAB 4: MOVEMENT

**Objective:** Entradas, salidas, cambios relevantes entre estados.

**Data sources:** state_transition_trace, program_decision_trace, driver_list_history

### Sections

```
┌─ Movement ──────────────────────────────────────────────┐
│                                                          │
│  Today's Movement Summary                                │
│    Entries: X  |  Exits: X  |  Program Changes: X       │
│                                                          │
│  Transition Types (bar chart)                            │
│    ENTERED_PROGRAM:  X                                  │
│    EXITED_PROGRAM:   X                                  │
│    STATE_CHANGE:      X                                 │
│                                                          │
│  Top Movers (table)                                      │
│    driver_id | from → to | type | trigger               │
│                                                          │
│  Program Changes Timeline                                │
│    Date range: program assignment changes per day        │
│                                                          │
│  Drilldown: Per-driver movement history                  │
└──────────────────────────────────────────────────────────┘
```

---

## TAB 5: RNA

**Objective:** Registered Not Activated drivers — root causes y contactabilidad.

**Data sources:** Yango Loyalty endpoints, ops.mv_driver_lifecycle_monthly_kpis, public.trips_2026

### Sections

```
┌─ RNA ───────────────────────────────────────────────────┐
│                                                          │
│  RNA KPIs                                                │
│    Total RNA: X  |  N (new): X  |  R (reactivable): X  │
│                                                          │
│  Contactability                                          │
│    With phone: X  |  Without phone: X                   │
│                                                          │
│  Cancelled Signals                                       │
│    Drivers who cancelled after contact: X                │
│                                                          │
│  City Comparison                                         │
│    City A | RNA count | Contact % | Activation %        │
│                                                          │
│  Root Causes (manual KPI table)                          │
│    Onboarding friction | Payment | Trust | Other         │
│                                                          │
│  Drilldown: Per-city RNA driver list                     │
└──────────────────────────────────────────────────────────┘
```

---

## TAB 6: DRIVER EXPLORER

**Objective:** Tabla maestra con búsqueda y filtros completos.

**Data sources:** driver_state_snapshot, driver_lifecycle_daily, program_eligibility_daily, driver_list_history, taxonomy_v2_explanation

### Sections

```
┌─ Driver Explorer ───────────────────────────────────────┐
│                                                          │
│  Filters:                                                │
│    [Program ▼] [Lifecycle ▼] [Segment ▼] [RNA ▼]       │
│    [City ▼] [Park ▼] [Activity ▼] [Search...]          │
│                                                          │
│  Table (export-ready):                                   │
│    driver_id | name | phone | city | park |              │
│    lifecycle | segment | value_tier | momentum |         │
│    programs | trips_7d | trips_30d | last_trip |         │
│    queue_status | channel | priority |                   │
│                                                          │
│  Per-driver drilldown:                                   │
│    → Lifecycle explanation (why this status)             │
│    → Segment explanation (matched_rules)                │
│    → Program history (decision trace)                    │
│    → Movement timeline                                   │
│    → Contact history                                     │
│                                                          │
│  Export: CSV download                                    │
└──────────────────────────────────────────────────────────┘
```

---

## FRESHNESS BANNER (Global)

Always visible at top:

```
┌─ System Health ─────────────────────────────────────────┐
│  Programs: FRESH 0h | Queue: FRESH 0h | Universe: 18,545│
│  RNA: FRESH Xh | Movement: STALE Xh                     │
│  Scheduler: RUNNING (586 ticks) | System: HEALTHY       │
└──────────────────────────────────────────────────────────┘
```

Data from: `GET /growth/health` + `GET /growth/freshness` + `GET /growth/operability`

---

## DATA FLOW

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  growth/     │    │  serving_    │    │  direct DB   │
│  health      │    │  fact cache  │    │  queries     │
│  freshness   │    │  (8 types)   │    │  (programs,  │
│  operability │    │              │    │   movement,   │
└──────┬───────┘    └──────┬───────┘    │   RNA, etc.)  │
       │                   │            └──────┬────────┘
       ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────────┐
│                    DASHBOARD UI                           │
│  Freshness Banner → Overview → Programs → Segments →     │
│  Movement → RNA → Driver Explorer                        │
└──────────────────────────────────────────────────────────┘
```

All data is pre-computed (serving facts) or lightweight (COUNT/MAX queries with indexes). No heavy runtime computation in UI layer.
