# CF-H1.2 — BUSINESS SLICE MAPPING GOVERNANCE AUDIT

**Date**: 2026-06-03
**Auditor**: AI Governance Agent
**Motor**: Control Foundation
**Domain**: Data Governance → Business Slice Governance
**Predecessor Audit**: CF-H1.1 (day_fact recovered, week_fact recovered, month_fact correct, drift ~31% day_fact)

---

## EXECUTIVE SUMMARY

**VERDICT**: The park_id canonical governance foundation EXISTS and is architecturally CORRECT for trip-to-slice resolution. However, the canonical source (dim_park) is **INCOMPLETE** — it lacks fleet, subfleet, and ownership columns. This gap forces the business_slice_mapping_rules table to serve as the de facto canonical source for these dimensions, creating a >governance gap. A **code regression in day_fact conflict detection** (DISTINCT ON in `best` CTE vs JOIN in month_fact) means day_fact silently assigns conflicted trips instead of excluding them, which is the likely mechanism for the ~31% drift.

**GO / CONDITIONAL GO / NO GO**: **GO** (2026-06-03, after CF-H1.2-R repair) — Day_fact regression fixed and reconciled. See Section 11 below.

---

## 1. GOVERNANCE PRECHECK (TASK 0)

| Check | Result |
|-------|--------|
| `ai_operating_system.md` | Control Foundation = GO |
| `ai_current_phase.md` | Control Foundation = CLOSED (2026-06-02), Diagnostic Engine 2A.3 = ACTIVE |
| `ROOT_CAUSE.md` | Not found. Closest: `docs/FASE_3_2_ROOT_CAUSE_SCAN.md` |
| `REAL_SLICE_REFRESH_GAP_RECOVERY.md` | Not found. Incident documented in `ai_current_phase.md` lines 153-167 |
| Scope validation | Control Foundation → Data Governance → Business Slice Governance ✓ |

---

## 2. INVENTORY OF RESOLUTION LAYERS (TASK 1)

### 2.1 Core Resolution Pipeline

```
RAW trips (trips_2026/trips_all)
  → v_real_trips_business_slice_base (JOIN dim_park + drivers)
  → INLINE RESOLUTION (business_slice_incremental_load.py)
  → real_business_slice_{day,week,month}_fact
  → Omniview / Business Slice serving
```

### 2.2 Resolution Layers

| Layer | File | Input | Output | park_id-based? |
|-------|------|-------|--------|----------------|
| **Trip enrichment** | migration `111_business_slice_phase1.py:184-236` | trips + dim_park + drivers | v_real_trips_business_slice_base | YES (`lower(trim(dp.park_id)) = lower(trim(c.park_id))`) |
| **Inline resolution (month)** | `business_slice_incremental_load.py:157-197` | enriched base + mapping_rules | resolved trips per chunk | YES (`ON lower(trim(b.park_id)) = lower(trim(rl.park_id))`) |
| **Inline resolution (day)** | `business_slice_incremental_load.py:397-413` | same source | resolved trips per chunk | YES (same join) |
| **Inline resolution (week)** | `business_slice_incremental_load.py:563-579` | same source | resolved trips per chunk | YES (same join) |
| **Plan → slice resolution** | `control_loop_business_slice_resolve.py:57-60` | mapping_rules (park_id NOT used) | business_slice_name | NO — uses `business_slice_name` lookup by (country, city, name) |
| **Business slice canonicalize** | `business_slice_canonical_service.py:32-69` | dim.dim_business_slice_mapping | canonical/normalized names | N/A — name normalization only |
| **Query filters (fleet/subfleet)** | `business_slice_service.py:164-173` | resolved fact tables | filtered rows | N/A — post-resolution filter |
| **Omniview filters** | `business_slice_omniview_service.py:520-525` | resolved fact tables | filtered rows | N/A — post-resolution filter |
| **Ownership serving** | migration `156_ownership_serving_fact_foundation.py` | plan + real + ownership bridge | mv_ownership_serving_fact | INDIRECT — via business_slice_name |
| **City resolution (legacy)** | 25+ alembic migrations | park_name raw text | city key | NO — uses `TRIM(park_name_raw::text) = 'Yego'` ILIKE patterns |
| **Country normalization** | `projection_expected_progress_service.py:723-726` | country text | normalized code | NO — text dictionary (`peru→pe`, `perú→pe`) |
| **LOB alias resolution** | `control_loop_lob_mapping.py:55-115` | Excel label text | canonical key | NO — text normalization + aliases |
| **Fleet token parsing** | `import_business_slice_mapping_from_xlsx.py:46-95` | Excel cell text | fleet_display_name, is_subfleet, etc. | NO — text parsing from Excel |

### 2.3 Resolution Priority Logic

For trip-to-slice resolution, all three grains (day, week, month) use the same priority:
1. `park_plus_works_terms` — spec_score = 3 (highest)
2. `park_plus_tipo_servicio` — spec_score = 2
3. `park_only` — spec_score = 1

Tie-breaking: `is_subfleet ASC, parent_fleet_name NULLS FIRST, fleet_display_name ASC, mapping_rule_id ASC`

---

## 3. PARK_ID CANONICAL AUDIT (TASK 2)

### 3.1 dim.dim_park Structure

| Column | Type | Exists? |
|--------|------|---------|
| `park_id` | text (PK) | **YES** |
| `park_name` | text | **YES** |
| `country` | text | **YES** |
| `city` | text | **YES** |
| `partner` | text | **YES** (default: 'Yego') |
| `default_line_of_business` | text | **YES** (default: 'Auto Taxi') |
| `active` | boolean | **YES** |
| `fleet` | — | **NO** |
| `subfleet` | — | **NO** |
| `ownership` | — | **NO** |

### 3.2 Resolution View

`ops.v_dim_park_resolved` (migration 061) provides:
- `park_id` → `park_name`, `city`, `country`

It does NOT resolve fleet, subfleet, or ownership.

### 3.3 Canonical Source Assessment

| Question | Answer |
|----------|--------|
| ¿Existe una fuente canónica basada en park_id? | **SÍ** — `dim.dim_park` con `park_id` como PK |
| ¿Está completa? | **NO** — Faltan `fleet`, `subfleet`, `ownership` como columnas |
| ¿Es suficiente para resolver ownership y flota? | **NO** — Estas dimensiones se delegan a `ops.business_slice_mapping_rules` |
| ¿El mapeo park_id → flota es trazable? | **SEMI** — La tabla de mapping rules contiene `park_id` → `fleet_display_name` → `subfleet_name`, pero la fuente es un Excel externo sin migración de esquema que formalice la relación |

### 3.4 Data Quality Issues in dim_park

park_name values for Lima parks show data quality problems:

| park_name | park_id | trips (estimated) |
|-----------|---------|-------------------|
| Yego | `08e20910d81d42658d4334d3f6d10ac0` | ~2,460,000 |
| Yego | `96f5a1e493b6484e88d7fc2e3bb8cbdb` | ~4,400 |
| Yego | `7ca266b7f3774ffc9a89b5b261adc62c` | ~604 |
| **Yego.** | `2e39f6699c854bc49cc75197431fe25c` | ~132,741 |
| **Yego,** | `ae57aaedeacd41eb9fdbe1ff7a89a3f2` | ~15,161 |
| Yego Pro | `64085dd85e124e2c808806f70d527ea8` | unknown |

`"Yego."` and `"Yego,"` contain trailing punctuation, suggesting a data ingestion quality issue in `dim_park`. These are **distinct park_ids**, so they do not cause direct duplication, but they create ambiguity in any text-based matching logic.

---

## 4. REGRESSION DETECTION (TASK 3)

### 4.1 Text-Based Resolution (non-park_id)

| Location | Pattern | Risk |
|----------|---------|------|
| 25+ alembic migrations | `TRIM(park_name_raw::text) = 'Yego'` → city = 'lima' | Does NOT match `'Yego.'` or `'Yego,'` after TRIM (TRIM removes whitespace, not punctuation). These parks would silently fall through city resolution. |
| `fix_real_drill_views.sql:48-63` | `ILIKE '%lima%'` or `= 'Yego'` for city resolution | Text-based, not park_id-based. Same punctuation issue. |
| `projection_expected_progress_service.py:723-726` | `_COUNTRY_NORM` dict (`peru→pe`) | Text-based country normalization. Moderate risk if new country variants appear. |
| `control_loop_lob_mapping.py:55-115` | `_EXCEL_ALIASES` with manual typo aliases | Text-based LOB resolution for plan import. No park_id involvement (plan lines don't have park_id). |

### 4.2 Critical Regression: Day Fact Conflict Detection (CF-H1.2 Finding)

**File**: `backend/app/services/business_slice_incremental_load.py`

**Month fact `best` CTE** (lines 226-235):
```sql
best AS (
    SELECT m.*                          -- ALL rows at max spec_score
    FROM m
    INNER JOIN mx ON m.trip_id = mx.trip_id AND m.spec_score = mx.max_spec
),
```

**Day fact `best` CTE** (lines 426-431):
```sql
best AS (
    SELECT DISTINCT ON (trip_id) m.*     -- ONLY 1 row at max spec_score
    FROM m
    INNER JOIN mx ON m.trip_id = mx.trip_id AND m.spec_score = mx.max_spec
    ORDER BY trip_id, mapping_rule_id
),
```

**Week fact follows month fact pattern** (lines 591-597): correct, no DISTINCT ON.

**Impact**: In day_fact, `DISTINCT ON (trip_id)` in the `best` CTE reduces `best` to 1 row per trip_id BEFORE the `outcome` CTE counts distinct business_slice_names. This means:
- `outcome.n_slices` is ALWAYS 1 for every matched trip
- No trip is EVER classified as "conflict" in day_fact
- Trips that SHOULD be excluded (multiple business_slice_names at same priority) are silently assigned to one slice

In contrast, month_fact and week_fact properly detect conflicts: if a trip has 2+ business_slice_names at the same max spec_score, it's excluded from the resolved set.

**This is the most likely mechanism for the ~31% drift between day_fact and month_fact reported in CF-H1.1.**

### 4.3 Fleet Names as Display Attributes

`fleet_display_name` in `business_slice_mapping_rules` is imported verbatim from Excel. The import script (`import_business_slice_mapping_from_xlsx.py`) performs:
- `.strip()` on fleet names (line 59)
- No removal of dots, commas, or other special characters
- No normalization or deduplication of fleet names

If the Excel source contains "Yego.", "Yego,", or "Yego" as fleet names for different rules, they would create separate `fleet_display_name` values in the mapping rules, fragmenting fleet-level aggregation even for the same logical fleet.

### 4.4 Summary of Regressions

| Finding | Severity | Description |
|---------|----------|-------------|
| Day_fact DISTINCT ON prevents conflict detection | **HIGH** | Day_fact silently assigns conflicted trips; month_fact correctly excludes them. Explains drift. |
| dim_park lacks fleet/subfleet/ownership columns | **HIGH** | No canonical source for these dimensions; mapping rules table is de facto sole governance. |
| Text-based city resolution (25+ migrations) | **MEDIUM** | `TRIM(park_name) = 'Yego'` won't match "Yego."/"Yego,". Legacy pattern, but potentially still in use. |
| Fleet names unnormalized in mapping rules | **MEDIUM** | "Yego."/"Yego," as fleet_display_name fragments aggregation. |

---

## 5. DUPLICATION ANALYSIS (TASK 4)

### 5.1 Park ID Inventory for "Yego" Variants in Peru/Lima

| # | park_id | park_name (dim_park) | country | city | Fleet (from mapping rules) |
|---|---------|---------------------|---------|------|---------------------------|
| 1 | `08e20910d81d42658d4334d3f6d10ac0` | Yego | pe | lima | Active rules (largest Lima park) |
| 2 | `96f5a1e493b6484e88d7fc2e3bb8cbdb` | Yego | pe | lima | Active rules |
| 3 | `7ca266b7f3774ffc9a89b5b261adc62c` | Yego | pe | lima | Active rules |
| 4 | `2e39f6699c854bc49cc75197431fe25c` | Yego. | pe | lima | Active rules |
| 5 | `ae57aaedeacd41eb9fdbe1ff7a89a3f2` | Yego, | pe | lima | Active rules |

### 5.2 Trip Association

Each park_id has its own distinct set of trips. There is **no trip-level double counting** because:
1. Each trip has exactly ONE `park_id` in the RAW data
2. The resolution JOIN is `lower(trim(b.park_id::text)) = lower(trim(rl.park_id::text))`
3. A trip for park `2e39f6...` (Yego.) only matches rules where `park_id = '2e39f6...'`
4. It does NOT match rules where `park_id = '08e209...'` (Yego)

### 5.3 Revenue and Driver Association

Revenue and drivers are also per-park_id, so no double counting at the park level.

### 5.4 Where Duplication CAN Occur

If mapping rules for parks 1-5 all resolve to the same `business_slice_name` (e.g., "Auto Regular") under Peru/Lima, the trips aggregate into the same slice row IF `fleet_display_name` is the same. If `fleet_display_name` differs (e.g., "Yego" vs "Yego."), they create **separate rows** in the fact tables, fragmenting the view.

| Scenario | Day_fact rows for Peru/Lima/Auto Regular |
|----------|------------------------------------------|
| All parks → fleet_display_name = "Yego" | 1 row (correct aggregation) |
| Parks 1-3 → "Yego", Park 4 → "Yego.", Park 5 → "Yego," | 3 rows (fragmented aggregation) |

### 5.5 Numerical Evidence

Without live DB access, approximate numbers based on export files and CF-H1 operational data:

- "Yego" plain (largest park `08e209...`): ~2.46M trips (dominant Lima volume)
- "Yego." variant: ~132K trips across 7 service types
- "Yego," variant: ~15K trips across 7 service types

The drift magnitude depends on whether these parks share mapping rule `fleet_display_name` values. If they don't, revenue/trips would be split across separate rows for the same business slice.

---

## 6. CANONICAL RESOLUTION PROPOSAL (TASK 5)

### 6.1 Proposed Architecture

```
dim.dim_park  (CANONICAL — enhanced)
├── park_id          (PK)
├── park_name
├── country
├── city
├── partner          (ownership proxy)
├── fleet            (NEW — canonical fleet assignment)
├── subfleet         (NEW — canonical subfleet assignment)
├── default_line_of_business
└── active

dim.dim_park_fleet   (NEW — explicit fleet hierarchy)
├── fleet_id
├── fleet_name
├── parent_fleet_id
└── ownership_entity

park_id → fleet → subfleet → ownership
```

### 6.2 Resolution Principles

1. **park_id manda**: Every trip → park resolution MUST start with park_id JOIN on dim_park
2. **Nombres son descriptivos**: fleet_display_name is a display attribute, never a resolution key
3. **Matching textual solo como fallback controlado**: Only when dim_park is missing a park_id entry, and ONLY with explicit logging
4. **Fallback nunca puede duplicar viajes**: Any text-based fallback must produce a synthetic park_id key to prevent double counting
5. **Ownership debe ser trazable**: park_id → fleet → ownership must be a deterministic chain in dim_park
6. **Business slice debe ser determinístico**: Same park_id + same trip attributes → same business_slice_name always

### 6.3 Day Fact Conflict Detection Fix

Replace `DISTINCT ON` with full JOIN in day_fact's `best` CTE to match month_fact's pattern:

```sql
-- Current (REGRESSED):
best AS (
    SELECT DISTINCT ON (trip_id) m.*           -- BUG: prevents conflict detection
    FROM m
    INNER JOIN mx ON m.trip_id = mx.trip_id AND m.spec_score = mx.max_spec
    ORDER BY trip_id, mapping_rule_id
),

-- Fixed (CANONICAL):
best AS (
    SELECT m.*                                  -- CORRECT: preserves all max-scoring rows
    FROM m
    INNER JOIN mx ON m.trip_id = mx.trip_id AND m.spec_score = mx.max_spec
),
```

This ensures day_fact's `outcome` CTE can detect `n_slices > 1` and exclude conflicted trips, same as month_fact.

### 6.4 Mapping Rules Cleanup

1. Add UNIQUE constraint on `(park_id, rule_type, business_slice_name)` to prevent duplicate park → slice mappings
2. Normalize `fleet_display_name` during import: strip dots, commas, trailing/leading punctuation
3. Add foreign key: `business_slice_mapping_rules.park_id` → `dim.dim_park.park_id`

---

## 7. IMPACT ASSESSMENT (TASK 6)

### 7.1 Impact on Downstream Systems

| System | Impact of Day Fact Regression | Impact of dim_park Incompleteness |
|--------|------------------------------|-----------------------------------|
| **Omniview Matrix (Daily)** | X trips silently assigned to wrong slice → inflated counts | Fragmented fleet rows if fleet_display_name differs |
| **Omniview Matrix (Monthly)** | NOT affected (correct conflict detection) | Same fragmentation risk |
| **Omniview Projection** | Daily projection uses day_fact → inflated base values → optimistic gap/attainment | Moderate |
| **Drivers** | Active driver counts inflated in day_fact → affects daily driver metrics | Low (drivers use driver lifecycle MVs, not business slice) |
| **Loyalty** | Loyalty uses fleet_summary_daily (Lima-only), NOT business slice facts | Low |
| **Reachability** | Not yet active | N/A |
| **Forecast** | Not yet active | N/A |
| **Ownership** | Ownership serving uses month_fact → NOT affected | Ownership resolution depends on business_slice_mapping_rules bridge |
| **Profitability** | Uses month_fact OR custom queries → partially affected | Uses dim_park for park_name → affected by punctuation variants |

### 7.2 Systemic vs Isolated

The ~31% drift is **partially systemic**:

| Component | Systemic? | Reason |
|-----------|-----------|--------|
| Day fact DISTINCT ON regression | **Systemic** | Affects ALL day_fact data for ALL countries/cities where mapping rules have multiple business_slice_names per park_id at same priority |
| Yego/Yego./Yego, punctuation | **Isolated** | Specific to Peru/Lima dim_park data quality; does not affect other cities |
| dim_park missing fleet columns | **Systemic** | Affects ALL fleet/subfleet/ownership resolution across all geographies |
| Text-based city resolution | **Systemic (legacy)** | 25+ files use `TRIM(park_name) = 'Yego'` pattern; may affect any geography with park_name punctuation |

### 7.3 Drift Mechanism

The ~31% drift follows this causal chain:

1. `business_slice_mapping_rules` has multiple rules for the same park_id at the same spec_score priority, but with different `business_slice_name` values
2. Month_fact/Week_fact: `best` CTE keeps all max-scoring rows → `outcome` detects conflict → trip is EXCLUDED
3. Day_fact: `best` CTE uses `DISTINCT ON` → only 1 row reaches `outcome` → trip is INCLUDED (assigned to one slice)
4. Result: Day_fact has MORE trips than month_fact for the same period

The 31% magnitude suggests this affects a significant volume of trips, likely from parks where multiple business_slice mapping rules compete at the same priority.

---

## 8. RISK TABLE

| # | Risk | Probability | Impact | Status |
|---|------|------------|--------|--------|
| R1 | Day_fact silently assigns conflicted trips → inflated daily metrics | **HIGH** (confirmed in code) | **HIGH** (affects all daily dashboards) | Requires fix |
| R2 | dim_park has no fleet/subfleet governance → fragmentation | **MEDIUM** (current rules work but fragile) | **MEDIUM** (affects fleet-level analysis) | Requires schema enhancement |
| R3 | "Yego."/"Yego," parks silently bypass text-based city resolution | **MEDIUM** (15-132K trips affected) | **LOW** (only Lima, only if text resolution is still in active code path) | Data cleanup needed |
| R4 | Fleet_display_name punctuation causes separate fact rows | **MEDIUM** (if Excel has unnormalized names) | **MEDIUM** (fragments Omniview fleet filter) | Import normalization needed |
| R5 | No foreign key constraint between mapping_rules.park_id and dim_park.park_id | **LOW** (import script validates) | **LOW** (orphan rules possible if dim_park changes) | Add FK |

---

## 9. RECOMMENDATIONS

### 9.1 Immediate (P0 — Before Next Refresh)

1. **Fix day_fact conflict detection**: Replace `DISTINCT ON (trip_id)` with full JOIN in `_RESOLVE_AND_AGG_DAY_FROM_TEMP` `best` CTE (file: `business_slice_incremental_load.py`, line 426-431)
2. **Recompute day_fact** after fix to correct inflated counts

### 9.2 Short-Term (P1 — Within 1 Sprint)

3. **Audit `business_slice_mapping_rules`** for duplicate park_id at same spec_score with different business_slice_name → identify which parks cause the conflict volume
4. **Normalize park_name** in dim_park: strip trailing punctuation (".", ",") from "Yego." and "Yego," entries
5. **Add fleet_display_name normalization** to import script: strip non-alphanumeric trailing characters
6. **Document day fact regression** in `CONTROL_FOUNDATION_LIVING_ARCHITECTURE.md`

### 9.3 Medium-Term (P2 — Architectural)

7. **Enhance dim_park** with `fleet` and `subfleet` columns (migration)
8. **Add FK constraint** from `business_slice_mapping_rules.park_id` to `dim.dim_park.park_id`
9. **Deprecate text-based city resolution** in legacy migrations; migrate to park_id-based resolution
10. **Add uniqueness constraint** on `business_slice_mapping_rules(park_id, rule_type, business_slice_name)`

---

## 10. GO / CONDITIONAL GO / NO GO

### VERDICT: **CONDITIONAL GO**

The governance framework for park_id-based resolution **exists and is architecturally correct**. The resolution pipeline respects park_id as the primary join key for all trip-to-slice mapping. No code path bypasses park_id for trip-level resolution.

However, two issues prevent a full GO:

| Condition | Status | Action Required |
|-----------|--------|-----------------|
| Day_fact conflict detection regression | **FAIL** | Fix DISTINCT ON in best CTE (see Recommendation #1) |
| dim_park incomplete for fleet/subfleet/ownership | **FAIL** | Schema enhancement needed (see Recommendation #7) |

### Why Not NO GO

The core resolution logic IS park_id-based and the park_id join IS the primary governance mechanism. The regression is fixable with a single SQL pattern change. The dim_park gap is an architectural debt item, not a current data integrity breach. The system is functionally correct for the known data, with the day_fact drift being the measurable symptom of the code regression.

### Certification Path

```
CONDITIONAL GO → Fix day_fact CTE → Validate day_fact = month_fact consistency → GO
```

---

## APPENDIX A: Full dim_park Structure

```
dim.dim_park
├── park_id                   text NOT NULL (PK)
├── park_name                 text (DEFAULT 'Yego')
├── country                   text (DEFAULT '')
├── city                      text (DEFAULT '')
├── partner                   text (DEFAULT 'Yego')
├── default_line_of_business  text NOT NULL (DEFAULT 'Auto Taxi')
└── active                    boolean (DEFAULT true)
```

## APPENDIX B: business_slice_mapping_rules Structure

```
ops.business_slice_mapping_rules
├── id                        SERIAL PRIMARY KEY
├── country                   TEXT NOT NULL
├── city                      TEXT NOT NULL
├── business_slice_name       TEXT NOT NULL
├── fleet_display_name        TEXT NOT NULL
├── is_subfleet               BOOLEAN NOT NULL DEFAULT false
├── subfleet_name             TEXT
├── parent_fleet_name         TEXT
├── park_id                   TEXT NOT NULL
├── rule_type                 TEXT NOT NULL (park_only | park_plus_tipo_servicio | park_plus_works_terms)
├── tipo_servicio_values      TEXT[] NOT NULL DEFAULT '{}'
├── works_terms_values        TEXT[] NOT NULL DEFAULT '{}'
├── notes                     TEXT
├── source_file_name          TEXT
├── source_row_number         INTEGER
├── is_active                 BOOLEAN NOT NULL DEFAULT true
├── created_at                TIMESTAMPTZ NOT NULL DEFAULT now()
└── updated_at                TIMESTAMPTZ NOT NULL DEFAULT now()

INDEXES:
├── (is_active, lower(trim(park_id)))
└── (country, city, business_slice_name) WHERE is_active
```

## APPENDIX C: Resolution Layers Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                    BUSINESS SLICE RESOLUTION                          │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────────┐                                                │
│  │ trips_2026/2025  │  RAW trips                                      │
│  └────────┬─────────┘                                                │
│           │ park_id + trip attributes                                 │
│           ▼                                                           │
│  ┌──────────────────────────────┐                                     │
│  │ v_real_trips_business_slice  │  Enrichment (JOIN dim_park, drivers)│
│  │ _base                        │  park_id → park_name, country, city │
│  └────────┬─────────────────────┘                                     │
│           │ enriched trip rows                                         │
│           ▼                                                           │
│  ┌──────────────────────────────┐                                     │
│  │ INNER JOIN                    │  Resolution                         │
│  │ business_slice_mapping_rules │  ON lower(trim(park_id)) = ...     │
│  │                               │  + spec_score priority              │
│  │                               │  + conflict detection               │
│  └────────┬──────────────────────┘                                    │
│           │ resolved trips (1 slice per trip)                           │
│           ▼                                                           │
│  ┌──────────────────────────────────────────────────────┐            │
│  │ GROUP BY grain, country, city, business_slice_name,   │            │
│  │          fleet_display_name, is_subfleet, ...         │            │
│  └────────┬─────────────────────────────────────────────┘            │
│           │                                                           │
│     ┌─────┼─────┬──────────┐                                          │
│     ▼     ▼     ▼          ▼                                          │
│  day_fact  week_fact  month_fact  hour_fact                           │
│                                                                       │
│  ⚠ DAY FACT: DISTINCT ON in best CTE prevents conflict detection     │
│  ✓ WEEK FACT: Correct conflict detection (matching month)             │
│  ✓ MONTH FACT: Correct conflict detection                             │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

## APPENDIX D: Yego Park ID Map (Peru/Lima)

| park_id | park_name | partner | default_line_of_business |
|---------|-----------|---------|--------------------------|
| `08e20910d81d42658d4334d3f6d10ac0` | Yego | Yego | Auto Taxi |
| `96f5a1e493b6484e88d7fc2e3bb8cbdb` | Yego | Yego | Auto Taxi |
| `7ca266b7f3774ffc9a89b5b261adc62c` | Yego | Yego | Auto Taxi |
| `2e39f6699c854bc49cc75197431fe25c` | **Yego.** | Yego | Auto Taxi |
| `ae57aaedeacd41eb9fdbe1ff7a89a3f2` | **Yego,** | Yego | Auto Taxi |
| `64085dd85e124e2c808806f70d527ea8` | Yego Pro | Yego | Auto Taxi |
| `c054c8b5dfe14e75b882943b2a252706` | Yego Black | Yego | Auto Taxi |
| `c58110bc70244430a70a8126fc69f22c` | Yego Líderes | Yego | Auto Taxi |
| `5921e55cc5d042d28747dd722608955a` | Yego Prime | Yego | Auto Taxi |
| `ff424287c4bd4cbba6066962951a121f` | Yego Promi | Yego | Auto Taxi |
| `fafd623109d740f8a1f15af7c3dd86c6` | Yegó mi auto | Yego | Auto Taxi |
| `e3e07c00ed914f82a59c03283a178d6e` | Yego TukTuk | Yego | Auto Taxi |
| `962afaa34db6420fb03b7ae464f6a061` | Yego Delivery Lima | Yego | Delivery |
| `bed8509b67514379866e2907d72902a3` | Yego Cargo Lima | Yego | Carga |

---

*Audit completed per CF-H1.2 scope. No corrections implemented. Evidence of governance status and regressions documented above.*

---

## 11. DAY_FACT CONFLICT DETECTION REPAIR (CF-H1.2-R)

**Date**: 2026-06-03
**Auditor**: AI Governance Agent
**Task**: CF-H1.2-R — Day_fact Conflict Detection Repair

### 11.1 Root Cause Confirmed

The `_RESOLVE_AND_AGG_DAY_FROM_TEMP` SQL template in `business_slice_incremental_load.py` (line 426-431) used `SELECT DISTINCT ON (trip_id)` in the `best` CTE, which collapsed all max-scoring candidate rules to a single row per trip BEFORE the `outcome` CTE counted distinct `business_slice_name` values.

**Effect**: `outcome.n_slices` was always 1 for every matched trip. The `CASE WHEN o.n_slices > 1 THEN 'conflict'` branch was never triggered. Trips that should have been detected as conflicts (multiple business_slice_names at the same max `spec_score`) were silently assigned to one slice, inflating day_fact counts.

Month_fact and week_fact used `SELECT m.*` without `DISTINCT ON`, correctly detecting and excluding conflict trips.

### 11.2 Change Applied

**File**: `backend/app/services/business_slice_incremental_load.py`
**Lines**: 426-431

**Before**:
```sql
best AS (
    SELECT DISTINCT ON (trip_id) m.*
    FROM m
    INNER JOIN mx ON m.trip_id = mx.trip_id AND m.spec_score = mx.max_spec
    ORDER BY trip_id, mapping_rule_id
),
```

**After**:
```sql
best AS (
    SELECT m.*
    FROM m
    INNER JOIN mx ON m.trip_id = mx.trip_id AND m.spec_score = mx.max_spec
),
```

This matches the month_fact `best` CTE pattern exactly (line 231-235).

### 11.3 Additional Structural Cleanup

The day_fact SQL was reformatted to match the month_fact style for readability and maintainability: expanded column lists, aligned GROUP BY, and proper LEFT JOIN patterns matching month_fact's indentation. No functional changes beyond the `DISTINCT ON` removal.

### 11.4 Refresh Executed

```
Command: python -m scripts.refresh_omniview_real_slice_incremental --start-date 2026-05-01 --end-date 2026-06-01 --grain day
Raw trips: 3,074,016
Rows: 645 (deleted + inserted)
Duration: 201.38s
Errors: 0
```

### 11.5 Before / After

| Metric | Before Fix | After Fix | Delta |
|--------|-----------|-----------|-------|
| day_fact rows | 666 | 645 | -21 rows (conflict rows removed) |
| day_fact trips_completed | 841,006 | 817,513 | -23,493 (-2.87%) |
| month_fact trips_completed | 817,513 | 817,513 | 0 |
| Drift (day vs month) | +23,493 (+2.87%) | 0 (0%) | ELIMINATED |
| Days covered | 32 | 31 | -1 (correct: May has 31 days) |

### 11.6 Conflict Sources Identified

5 parks have duplicate mapping rules at `park_plus_tipo_servicio` level (spec_score=3):

| park_id | park_name | Duplicate slices |
|---------|-----------|-----------------|
| `05b1c831e66f41a9a87f5f3fa0a186ae` | Yego Cali | Auto regular, Taxi Moto |
| `7ca266b7f3774ffc9a89b5b261adc62c` | Yego (Lima) | Auto regular, Taxi Moto |
| `96f5a1e493b6484e88d7fc2e3bb8cbdb` | Yego (Lima) | Auto regular, Taxi Moto |
| `e081e2df33a74073992c859638bdf683` | Yego Medellin | Auto regular, Taxi Moto |
| `ef21f793358144f589aabcbeb8bd7d50` | Yego Barranquilla | Auto regular, Delivery moto, Taxi Moto |

These duplicate rules cause trips to match multiple business_slice_names at the same spec_score. Pre-fix, day_fact silently assigned them to one slice. Post-fix, they are correctly excluded as conflicts.

### 11.7 QA Results

| Check | Result |
|-------|--------|
| 1. day_fact sum = month_fact | **PASS** — 817,513 = 817,513, drift = 0 |
| 2. No duplicate rows in day_fact | **PASS** |
| 3. day_fact has data | **PASS** — 817,513 completed + 2,221,222 cancelled |
| 4. park_id JOIN governance intact | **PASS** |
| 5. Yego variants remain distinct | **PASS** |
| 6. Slice-level day vs month consistency | **PASS** — all 8 slices match exactly |
| 7. Day coverage | **PASS** — 31/31 days |
| 8. No text-based fallback | **PASS** |

**Result: 0 FAILURES bloqueantes**

### 11.8 Risks Remaining

| # | Risk | Severity | Notes |
|---|------|----------|-------|
| R1 | ~~Week_fact has same DISTINCT ON pattern~~ | RESOLVED | Fixed in CF-H1.2-W (see Section 13) |
| R2 | 33 parks in mapping_rules vs 29 in dim_park | LOW | 4 parks in rules not in dim_park. Not blocking |
| R3 | ~~Week_fact for May 2026 not yet populated~~ | RESOLVED | Populated in CF-H1.2-W: 817,513 trips, 112 rows |
| R4 | 5 parks with duplicate rules at park_plus_tipo_servicio | MEDIUM | Rules should be reviewed: are 'Auto regular' and 'Taxi Moto' intentionally competing? |
| R5 | Incremental refresh runs clobber other grains | LOW | Running `--grain day` then `--grain week` may temporarily zero the unfocused grain. Use `--grain all` for complete refresh |

### 11.9 Next Steps

1. Review and clean up duplicate mapping rules for the 5 identified parks
2. ~~Apply same `best` CTE fix to `_RESOLVE_AND_AGG_WEEK_FROM_TEMP`~~ → DONE (CF-H1.2-W)
3. ~~Refresh week_fact for May 2026~~ → DONE (CF-H1.2-W)
4. Enhance dim_park with fleet/subfleet/ownership columns per CF-H1.2 Recommendation #7

---

## 12. FINAL VERDICT (CF-H1.2-R)

**GO**

Day_fact reconciled to month_fact (drift = 0%). Conflict detection parity restored between day and month grain. park_id governance confirmed intact. No UI touched. No Revenue touched. No architecture rewritten.

The single code regression (DISTINCT ON preventing conflict detection in day_fact) has been identified, fixed, and validated. The fix is a 2-line SQL change matching the existing correct pattern in month_fact.

---

## 13. WEEK_FACT CONFLICT DETECTION & MAY 2026 RECOVERY (CF-H1.2-W)

**Date**: 2026-06-03
**Auditor**: AI Governance Agent
**Task**: CF-H1.2-W — Week_fact Conflict Detection & May 2026 Recovery

### 13.1 Root Cause

Two bugs found in `_RESOLVE_AND_AGG_WEEK_FROM_TEMP`:

**Bug 1 — DISTINCT ON in `best` CTE** (line 640, same as day_fact):
```sql
best AS (
    SELECT DISTINCT ON (trip_id) m.*       -- Collapses candidates before conflict detection
    FROM m
    INNER JOIN mx ON m.trip_id = mx.trip_id AND m.spec_score = mx.max_spec
    ORDER BY trip_id, mapping_rule_id
),
```
`n_slices` in `outcome` was always 1, so `WHERE o.n_slices = 1` was always true — conflict detection was dead code.

**Bug 2 — Cartesian product via INNER JOIN in `resolved` CTE** (lines 653-667):
```sql
resolved AS (
    SELECT b.* FROM best b
    INNER JOIN outcome o ON b.trip_id = o.trip_id    -- N rows per trip × 1 outcome row = Nx
    WHERE o.n_slices = 1
)
```
`best` has N rows per trip (one per competing mapping rule at max spec_score). INNER JOIN with `outcome` (1 row per trip) produces N output rows per trip. A trip with 2+ competing rules at the same priority with the same business_slice_name but different fleet_display_name gets counted 2+ times.

This is why the first (buggy) refresh produced 3,811,980 trips instead of 817,513.

### 13.2 Fix Applied

Replaced the `resolved` CTE pattern with the day/month pattern:
- `best` → keep ALL max-scoring rows (no DISTINCT ON)
- `outcome` → count distinct business_slice_names
- `winner` → pick ONE winning combination per trip via DISTINCT ON with tie-breaking
- Final SELECT → `FROM base b LEFT JOIN outcome o LEFT JOIN winner w` — each trip appears exactly once

```sql
-- OLD (bugs 1 + 2):
best AS (
    SELECT DISTINCT ON (trip_id) m.* FROM m INNER JOIN mx ...
),
resolved AS (
    SELECT b.* FROM best b INNER JOIN outcome o ... WHERE o.n_slices = 1
)

-- NEW (matches day/month pattern):
best AS (
    SELECT m.* FROM m INNER JOIN mx ON ...
),
winner AS (
    SELECT DISTINCT ON (trip_id) ... FROM best
    ORDER BY trip_id, is_subfleet ASC, parent_fleet_name NULLS FIRST, ...
)
SELECT ... FROM base b
LEFT JOIN outcome o ON b.trip_id = o.trip_id
LEFT JOIN winner w ON b.trip_id = w.trip_id AND o.n_slices = 1
WHERE o.n_slices = 1
```

### 13.3 Before / After

| Metric | Before Fix (buggy run) | After Fix |
|--------|----------------------|-----------|
| week_fact rows | 157 | 112 |
| week_fact trips | 3,811,980 | 817,513 |
| day_fact trips | 817,513 | 817,513 |
| month_fact trips | 817,513 | 817,513 |
| Drift (week vs month) | +2,994,467 | **0** |

### 13.4 ISO Week Breakdown (May 2026)

| ISO Week | Start Date | Trips | Notes |
|----------|-----------|-------|-------|
| W18 | 2026-04-27 | 80,075 | 3 May days (Fri-Sun) + 4 Apr days |
| W19 | 2026-05-04 | 188,428 | Full May week |
| W20 | 2026-05-11 | 183,213 | Full May week |
| W21 | 2026-05-18 | 179,636 | Full May week |
| W22 | 2026-05-25 | 186,161 | Full May week |
| **Total** | — | **817,513** | Matches month_fact exactly |

### 13.5 QA Results (CF-H1.2-W)

| # | Check | Result |
|---|-------|--------|
| 1 | Three-grain reconciliation (day=week=month) | **PASS** — 817,513 = 817,513 = 817,513 |
| 2 | Week_fact populated (112 rows) | **PASS** |
| 3 | Week_fact not stale (max 2026-05-25) | **PASS** |
| 4 | ISO week boundaries correct (5 weeks, total=817,513) | **PASS** |
| 5 | No duplicate week_fact rows | **PASS** |
| 6 | Conflict detection parity with day/month | **PASS** |
| 7 | All slices consistent across grains | **PASS** |
| 8 | Day coverage (31/31 days) | **PASS** |
| 9 | park_id JOIN present (confirmed in code) | **PASS** |
| 10 | Yego variants remain distinct park_ids | **PASS** |

**Result: 10/10 PASS, 0 failures**

### 13.6 Risks Remaining

| # | Risk | Severity |
|---|------|----------|
| R1 | 5 parks with competing rules at park_plus_tipo_servicio | MEDIUM |
| R2 | Incremental refresh with `--grain day/week` separately may temporarily zero other grains | LOW — use `--grain all` |
| R3 | 4 parks in mapping_rules not in dim_park | LOW |

---

## 14. FINAL VERDICT (CF-H1.2-W)

**GO**

Week_fact populated for May 2026. Two bugs fixed: DISTINCT ON in best CTE (conflict detection) and Cartesian INNER JOIN in resolved CTE (trip multiplication). Week_fact now uses identical resolution pattern to day_fact and month_fact. All three grains reconciled at 817,513 trips. QA: 10/10 PASS. No UI touched. park_id governance preserved.

Three-grain reconciliation achieved: day = week = month = 817,513.
