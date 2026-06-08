# OV2-F.1 — DRILL READINESS AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Refresh Chain
> **Status:** AUDIT COMPLETE

---

## 1. DRILL LAYERS

| Depth | Layer | Target | Data Available? | Status |
|-------|-------|--------|-----------------|--------|
| 1 | Cell → Slice | `business_slice_name` | Yes — in cell contract | **READY** |
| 2 | Slice → City | `country` + `city` | Yes — in cell lineage_refs | **READY** |
| 3 | City → Fleet | `fleet` / `lob_base` | Partial — LOB available in plan, not in real facts | **PARTIAL** |
| 4 | Fleet → Subfleet | `segment` / `sub_lob` | Only in plan table (`segment` column) | **PARTIAL** |
| 5 | Subfleet → Park | `park_id` | In `raw_yango` MVs, not in business slice facts | **BLOCKED** |
| 6 | Cell → Driver | `driver_id` | Not in matrix cell. Available via `driver_daily_activity_fact` | **BLOCKED** |
| 7 | Cell → Raw Trip | `order_id` / `trip_id` | Not in matrix lineage. Available in `trips_2026` | **BLOCKED** |

## 2. PER-SOURCE DRILL CAPABILITY

### CT_TRIPS_2026

| Drill path | Table needed | Status |
|-----------|-------------|--------|
| Cell → day → hour → trip | `real_business_slice_day_fact` → `trips_2026` | **PARTIAL** — day_fact has date and slice, but no trip-level granularity |
| Cell → driver_count → driver_list | `driver_daily_activity_fact` | **BLOCKED** — driver data is in separate domain facts |
| Cell → park_id → Yango park | `raw_yango` + `park_id` mapping | **BLOCKED** — park mapping doesn't flow through to business slice facts |

### YANGO_API_RAW

| Drill path | Source | Status |
|-----------|--------|--------|
| Cell → order_date → orders | `raw_yango.mv_orders_day` | **READY** |
| Cell → driver_profile | `raw_yango.mv_driver_profiles_snapshot` | **READY** |
| Cell → transaction | `raw_yango.mv_transactions_day` | **READY** |

## 3. WHAT EXISTS TODAY

| Feature | Implementation | Depth |
|---------|---------------|-------|
| Cell inspector shows `source_table` | `CellInspector.jsx` | Layer 0 (metadata) |
| Cell shows `lineage_refs` (plan/real tables) | MatrixResponse contract | Layer 0 |
| Shell shows KPI lineage | `OmniviewV2Lineage` in shell sections | Layer 1 (KPI→table) |
| Real drill endpoint | `GET /ops/real/drill?country=&city=&slice=` | Layer 1-3 |
| Yango drill endpoints | `GET /yango-lima-growth/lab/*` | Layer 1-5 (Yango only) |

## 4. REQUIRED FOR FULL DRILL

| Gap | Action | Priority |
|-----|--------|----------|
| Add `fleet`/`lob` to business slice facts | Schema migration | P2 |
| Add `park_id` to cell lineage for Yango source | Repository enhancement | P2 |
| Add drill endpoint: cell → raw trips | New endpoint `GET /ops/omniview-v2/drill/{cell_id}` | P2 |
| Add driver drill from cell | Link `driver_daily_activity_fact` to business slice facts | P2 |
| Yango reconciliation drill | See `OV2_F1_YANGO_RECONCILIATION_DESIGN.md` | P2 |

## 5. DRILL READINESS SUMMARY

| Layer | Status | Blocker |
|-------|--------|---------|
| Cell → Slice | **READY** | — |
| Cell → City | **READY** | — |
| Cell → Fleet/LOB | **PARTIAL** | LOB not in real facts |
| Cell → Park ID | **BLOCKED** | Park mapping gap |
| Cell → Driver | **BLOCKED** | Separate domain |
| Cell → Raw Trip | **BLOCKED** | No row-level linking |
| Yango Cell → Order | **READY** | — |
| Yango Cell → Driver Profile | **READY** | — |

**Overall: PARTIAL** — 2 layers ready, 2 partial, 3 blocked. Clear path to READY with 4 P2 enhancements.

---

*End of Drill Readiness Audit*
