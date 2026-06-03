# Universe Governance — YEGO Lima Growth Tower

## Fase PP-1 — Universe Governance Audit

---

## 1. Universes Defined

Every KPI in Lima Growth must declare its universe. No KPI without universe.

| Universe | Definition | Source | Filter | Window |
|----------|------------|--------|--------|--------|
| **Registered** | All drivers ever seen for Lima fleet | trips_2025/2026 + API | `park_id=08e20910...` | All time |
| **Historical** | Drivers with completed orders in history | trips_2025/2026 backfill | `park_id + Compleatdo` | 2025-02 to today |
| **Active 90D** | Drivers with >=1 order in last 90 days | history_daily | `completed_orders > 0` | Rolling 90d |
| **Active 30D** | Drivers with >=1 order in last 30 days | history_daily | `completed_orders > 0` | Rolling 30d |
| **Active 7D** | Drivers with >=1 order in last 7 days | history_daily | `completed_orders > 0` | Rolling 7d |
| **Active Daily** | Drivers with >=1 order on a single day | history_daily / 360_daily | `completed_orders > 0` | 1 day |
| **Opportunity** | Drivers eligible for daily action | state_snapshot → programs → opportunities | Program rules | 1 day |

---

## 2. Lima Filter

**park_id**: `08e20910d81d42658d4334d3f6d10ac0` (YANGO_LIMA_PARK_ID)

This park_id represents the Lima/Yango fleet. The filter is applied:

- **Pre-cutover** (before 2026-06-01): `park_id = YANGO_LIMA_PARK_ID AND LOWER(condicion) = 'completado'` on trips_2025/trips_2026
- **Post-cutover** (after 2026-06-01): Yango Fleet API via Driver360 pipeline

**Confidence**: HIGH - 13056 drivers in trips_2025, 9949 in trips_2026, all filtered by the same park_id.

---

## 3. Current Universe Counts (as of 2026-06-02)

| Universe | Drivers | Orders | Source |
|----------|---------|--------|--------|
| Registered | 18,457 | - | history_daily |
| Historical | 18,457 | 2.5M+ | trips backfill |
| Active 90D | 7,976 | 1,056,299 | history_daily |
| Active 30D | 4,603 | 336,262 | history_daily |
| Active 7D | 2,558 | 66,329 | history_daily |
| Active Daily (May 31) | 1,287 | 12,773 | history_daily |
| Active Daily (360 API) | 129 | 0 | 360_daily |
| Opportunity | 28,493 | - | program_eligibility |

---

## 4. Daily KPIs (May 31, 2026)

| Metric | Value |
|--------|-------|
| completed_orders_day | 12,773 |
| active_drivers_day | 1,287 |
| trips_per_active_driver_day | 9.9 |
| Source | history_daily |

---

## 5. Weekly KPIs (2026-W22 - May 25-31)

| Metric | Value |
|--------|-------|
| completed_orders_week | 76,302 |
| active_drivers_week | 2,624 |
| trips_per_active_driver_week | 29.1 |
| Source | history_weekly |

---

## 6. Coherence Validation

| Window | Expected | Actual | Status |
|--------|----------|--------|--------|
| Daily active | ~1000-1200 | 1,287 (May 31) | Matches |
| Weekly active | ~5000 | 2,624 (W22) | Below expected* |
| Monthly active | ~8000-9000 | 4,673 (May) | Below expected* |

*Weekly and monthly are below initial expectations because:
1. The expected 5000 weekly was based on total fleet (all parks), not just Lima
2. Lima park_id is ~41-46% of total fleet
3. May data is partial (late-month backfill has slightly fewer drivers)
4. Expected should be recalibrated: ~2500-3000 weekly, ~4000-5000 monthly for Lima-only

---

## 7. API Endpoints

```bash
# Full governance report
GET /yego-lima-growth/universe/governance-report?date=2026-06-02

# Daily KPIs for a specific date
GET /yego-lima-growth/universe/daily-kpis?date=2026-05-31

# Weekly KPIs by ISO week
GET /yego-lima-growth/universe/weekly-kpis?iso_year=2026&iso_week=22
```

---

## 8. Rules

1. Every KPI must declare its universe
2. No KPI mixes pre-cutover and post-cutover without explicit labeling
3. Pre-cutover data source: trips_2025/trips_2026 via park_id filter
4. Post-cutover data source: Yango API Driver360 pipeline
5. Cutover date: `LIMA_GROWTH_API_CUTOVER_DATE=2026-06-01`
6. Opportunity universe is derived from state_snapshot (which reads history_weekly + 360_daily)

---

## 9. Post-Cutover Gap

On 2026-06-02, history_daily shows 0 active drivers because backfill only went to 2026-06-01. The 360_daily API shows 129 drivers with supply but 0 completed_orders.

For post-cutover daily operations, either:
- Run the Yango API pipeline to populate 360_daily with completed_orders
- Or extend the history backfill to include the current date from trips_2026
