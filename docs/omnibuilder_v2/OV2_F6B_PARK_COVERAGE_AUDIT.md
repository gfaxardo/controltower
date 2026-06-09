# OV2-F.6B — PARK COVERAGE AUDIT

> **Date:** 2026-06-08
> **Status:** AUDIT COMPLETE — MATCH

## PARK: 08e20910d81d42658d4334d3f6d10ac0

| Field | CT | Yango | Match |
|-------|-----|-------|-------|
| park_id | 08e20910d81d42658d4334d3f6d10ac0 | 08e20910d81d42658d4334d3f6d10ac0 | ✅ |
| Country | peru | (implicit from config) | ✅ |
| City | lima | (implicit from config) | ✅ |
| Fleet name | Yego. Lima | (Yango API) | ✅ |
| Is only park? | No (CT has 22 parks) | Yes (only 1 ingested) | ⚠️ |

## CT PARK SCOPE

CT bridge has 22 distinct parks in Lima. Only 1 matches Yango. The reconciliation correctly filters by park_id.

## YANGO PARK SCOPE

Yango orders_raw has only 1 park. The ingestion only targets the Lima main park (configured in `.env`).

## VERDICT

**PARK MATCH** — Same park_id. CT aggregates across slices within the park. Yango returns all categories for the park. No park scope mismatch.

---

*End of Park Coverage Audit*
