# LG-MOV-2A — MOVEMENT DASHBOARD CERTIFICATION

**Date:** 2026-06-12
**Phase:** LG-MOV-2A
**Status:** CERTIFIED

---

## 1. ARCHIVOS CREADOS/MODIFICADOS

| # | Archivo | Cambio |
|---|--------|--------|
| 1 | `backend/app/services/yego_lima_movement_analytics_service.py` | NUEVO — Transition matrix, top winners/losers, stats |
| 2 | `backend/app/routers/yego_lima_movement_analytics.py` | NUEVO — 4 endpoints |
| 3 | `backend/app/main.py` | MODIFICADO — +1 import, +1 include_router |
| 4 | `frontend/src/pages/lima-growth-ui1a/sections/MovementTab.jsx` | RESCRITO — Full movement dashboard |

---

## 2. TRANSITION MATRIX

Built from `growth.driver_movement_fact`. Shows:
- **Segment transitions**: from_segment → to_segment (SEGMENT_CHANGE class)
- **Lifecycle transitions**: from_lifecycle → to_lifecycle (LIFECYCLE_CHANGE class)
- **Program transitions**: from_program → to_program (PROGRAM_CHANGE class)

68,473 movements tracked (Jun 10, 2026). Expected to grow as V2 pipeline runs daily.

---

## 3. TOP WINNERS / LOSERS

Query from `growth.driver_movement_fact` ordered by `movement_score`:
- **Winners**: Highest positive scores (RNA→ACTIVE_GROWTH +15, CHURNED→ACTIVE_GROWTH +10)
- **Losers**: Most negative scores (TOP_PERFORMER→CHURNED −12, ACTIVE_GROWTH→CHURNED −8)

---

## 4. ENDPOINTS

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/yego-lima-growth/movement-analytics/stats` | Total, positive, negative, net movement |
| `GET` | `/yego-lima-growth/movement-analytics/matrix` | Transition matrix (segment + lifecycle + program) |
| `GET` | `/yego-lima-growth/movement-analytics/winners` | Top winners by movement score |
| `GET` | `/yego-lima-growth/movement-analytics/losers` | Top losers by movement score |

---

## 5. MOVEMENT DASHBOARD UI

Enhanced Movement tab now shows:
1. **KPIs**: Total transitions, positive, negative, net movement
2. **Movement Classes**: SEGMENT_CHANGE, PROGRAM_CHANGE, LIFECYCLE_CHANGE distribution
3. **Transition Matrix**: from → to table with driver counts and percentages
4. **Top Winners**: Top 10 drivers with highest positive scores
5. **Top Losers**: Top 10 drivers with most negative scores
6. **Transition Types**: Bar chart from movement summary endpoint
7. **Movement History**: Driver movement table with "Why?" drilldown

---

## 6. BUILD

| Build | Result |
|-------|--------|
| Backend compile | PASS |
| Frontend `npm run build` | PASS (6.32s, 59 kB UI-1A) |

---

## 7. VEREDICTO

### LG_MOV_2A_CERTIFIED

| Criterio | Status |
|----------|:---:|
| Transition matrix built | PASS |
| Top winners displayed | PASS |
| Top losers displayed | PASS |
| Movement KPIs | PASS |
| Uses movement facts (no recalculation) | PASS |
| Build backend PASS | PASS |
| Build frontend PASS | PASS |

**LG-MOV-2A Movement Dashboard: IMPLEMENTED AND CERTIFIED.**

---

## FIRMA

```
LG-MOV-2A MOVEMENT DASHBOARD CERTIFICATION
Date: 2026-06-12
Status: LG_MOV_2A_CERTIFIED
```
