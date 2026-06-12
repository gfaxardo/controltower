# CF-H2E.3 — MULTIPARK INVENTORY

> **Fase:** CF-H2E.3 — Continuous Multipark Shadow
> **Sub-document:** Multipark Inventory
> **Fecha:** 2026-06-12

---

## PILOT PARKS (5)

| park_id | Park Name | City | Country | Tier | Credential Status | Auth Status | Shadow Status | Orders Ingested | Txns Ingested | Watermarks |
|---------|-----------|------|---------|------|-------------------|-------------|---------------|-----------------|---------------|------------|
| `08e20910...ac0` | Yego Lima | Lima | Peru | TIER_1 | REGISTERED | AUTH_OK | **ACTIVE** | 48,665 | 526,359 | orders + txns |
| `851e3075...b4ab8` | Yego Trujillo | Trujillo | Peru | TIER_2 | CREDENTIALS_READY | AUTH_OK | **READY** | 22 | 95 | orders + txns |
| `56e4607d...73003` | Yego Arequipa | Arequipa | Peru | TIER_2 | CREDENTIALS_READY | AUTH_OK | **READY** | 0 | 17 | txns only |
| `64085dd8...7ea8` | Yego Pro | Lima | Peru | TIER_2 | CREDENTIALS_READY | AUTH_OK | **READY** | 35 | 144 | orders + txns |
| `e3e07c00...d6e` | Yego TukTuk | Lima | Peru | TIER_3 | CREDENTIALS_READY | AUTH_OK | **READY** | 9 | 42 | orders + txns |

## EXCLUDED PARKS

| park_id | Park Name | Status | Reason |
|---------|-----------|--------|--------|
| `fafd6231...dd86c6` | Yego Mi Auto | **BLOCKED** | Not in dim_park. City unknown. Metadata incomplete. |

---

## CLASSIFICATION SUMMARY

| Status | Count | Parks |
|--------|-------|-------|
| ACTIVE | 1 | Lima |
| READY | 4 | Trujillo, Arequipa, Pro, TukTuk |
| BLOCKED | 1 | Mi Auto |

---

## KEY METADATA

| Attribute | Value |
|-----------|-------|
| Total parks registered | 6 |
| Pilot parks | 5 |
| Active ingestion | 1 (Lima) |
| Credentials present | 6/6 |
| Auth validated | 6/6 |
| Watermarks created | 5/5 (9/10 endpoints) |
| dim_park coverage | 5/6 (Mi Auto excluded) |

---

## CONTINUOUS SHADOW TARGET

| Park | Target Frequency | Expected Orders/Day | Expected Txns/Day |
|------|-----------------|-------------------|--------------------|
| Lima | Every 5 min | ~11,000 | ~51,000 |
| Trujillo | Every 15 min | ~1,500 | ~6,000 |
| Arequipa | Every 15 min | ~1,200 | ~5,000 |
| Pro | Every 15 min | ~800 | ~3,500 |
| TukTuk | Every 15 min | ~400 | ~1,800 |

*Estimates from CF-H2E.0 capacity model scaled down for dry-run actuals.*
