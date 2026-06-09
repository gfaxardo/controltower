# OV2-F.6B — YANGO SOURCE GOVERNANCE — FINAL REPORT

> **Date:** 2026-06-08
> **Motor:** Control Foundation / Reconciliation
> **Phase:** OV2-F.6B — Yango Source Governance & Coverage Diagnostic
> **Status:** **YANGO_SOURCE_PARTIAL — Ingestion incomplete, engine certified**

---

## 1. WHY DOES THE DELTA EXIST?

Yango ingestion was limited to `--max-pages=10`, fetching only 1,000 orders for 2026-06-06. CT bridge counts 12,303 completed trips for the same park+date. The 12.3× delta is entirely attributable to incomplete Yango data ingestion.

## 2. WHERE IS IT GENERATED?

**Layer 1 (API → raw):** Incomplete ingestion. NOT in the MV or the reconciliation engine.

## 3. IS THE API COMPLETE?

**No.** The Yango Fleet API was queried with `--max-pages=10`, which limits results. The API supports paginated access but full ingestion requires unlimited or higher page counts.

## 4. ARE THE MVs COMPLETE?

**Yes.** `raw_yango.mv_orders_day` accurately aggregates raw data (1,000 orders_raw = 1,000 mv_orders_day). No data loss in the MV layer.

## 5. DOES THE PARK MATCH?

**Yes.** Same `park_id` (08e20910d81d42658d4334d3f6d10ac0) on both sides.

## 6. DO THE KPIs MATCH?

**Yes.** Both count completed trips/orders. Driver definitions are semantically equivalent (completed-only).

## 7. CAN WE TRUST YANGO?

**Partially.** As a reconciliation source for the Lima main park, yes — with full ingestion. As a primary data source, no — missing 21 parks, no history, different ID systems, no slice mapping, no automation.

## 8. CAN WE MIGRATE?

**No.** Yango cannot replace trips_2025/trips_2026 as the primary source. See `OV2_F6B_MIGRATION_READINESS.md` for the full gap analysis.

## 9. RISKS

| Risk | Severity | Mitigation |
|------|----------|------------|
| Ingestion truncation | HIGH | Remove `--max-pages` limit |
| No automated Yango ingestion | HIGH | Add to scheduler cascade |
| Driver ID mismatch | MEDIUM | Create mapping table |
| Category ≠ business slice | MEDIUM | Map Yango categories to CT slices |

## 10. NEXT STEP

1. Run full Yango ingestion (no `--max-pages` limit) for 2026-06-06
2. Refresh MVs
3. Re-run reconciliation → expect MATCH or MINOR_DELTA
4. Schedule daily Yango ingestion
5. Build driver ID mapping table

---

## CLASSIFICATION

### YANGO_SOURCE_PARTIAL

- Reconciliation engine: **CERTIFIED** ✅
- CT side: **CERTIFIED** ✅
- Yango API: **PARTIAL** (limited ingestion)
- Yango MVs: **ACCURATE** ✅
- Migration readiness: **BLOCKED**

---

## DELIVERABLES

| # | Document |
|---|----------|
| 1 | `OV2_F6B_SOURCE_INVENTORY.md` |
| 2 | `OV2_F6B_PARK_COVERAGE_AUDIT.md` |
| 3 | `OV2_F6B_DATE_WINDOW_AUDIT.md` |
| 4 | `OV2_F6B_KPI_SEMANTICS_AUDIT.md` |
| 5 | `OV2_F6B_RAW_TO_MV_RECONCILIATION.md` |
| 6 | `OV2_F6B_YANGO_COVERAGE_WATERFALL.md` |
| 7 | `OV2_F6B_ROOT_CAUSE_CLASSIFICATION.md` |
| 8 | `OV2_F6B_MIGRATION_READINESS.md` |
| 9 | `OV2_F6B_YANGO_SOURCE_GOVERNANCE_REPORT.md` (this document) |

---

*End of OV2-F.6B Yango Source Governance Report*
