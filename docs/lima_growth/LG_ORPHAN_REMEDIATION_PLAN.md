# LG_ORPHAN_REMEDIATION_PLAN

**Phase:** LG-CF-RECOVERY-2B — Control Foundation Operational Closure  
**Generated:** 2026-06-12  
**Status:** DESIGN ONLY — NOT IMPLEMENTED

---

## ORPHAN 1: `growth.yego_lima_v2_taxonomy_daily`

### Who Writes Really

| Writer | How | Evidence |
|--------|-----|----------|
| **V2 pipeline Step 5** (`_build_taxonomy_v2_daily`) | Triggered manually via `POST /yego-lima-growth/v2-pipeline/run` | Pipeline run log: 17 manual runs. Latest at 17:31 on 06-12 triggered by `canonical-freshness`. |
| External SQL/ETL | One-shot execution before V2 pipeline existed | Row counts match lifecycle_daily exactly (same row counts per date). Data was populated externally before pipeline was built. |

**Current reality:** The V2 pipeline writes to this table (Step 5), but only when triggered manually. The table IS populated and fresh — just not automatically.

### Who Consumes

| Consumer | How | Criticality |
|----------|-----|-------------|
| `yego_lima_export_service.py:43` | `COALESCE(tx.segment, ds.segment)` for Driver Explorer export | P1 |
| `yego_lima_explainability_service.py` | Reads segment classification for explainability | P1 |
| `yego_lima_rna_priority_service.py` | Reads taxonomy for RNA scoring | P1 |
| Segments tab (UI) | Displays segment distribution | P1 |

### Canonical Source Decision

**This table IS the canonical source for segment classification.** It is NOT duplicated elsewhere. There is no alternative source of truth for `segment` and `sub_segment` in V1. The `driver_state_snapshot.historical_band` is a fallback proxy, not the same thing.

### Remediation

| Option | Description | Pros | Cons | Verdict |
|--------|-------------|------|------|---------|
| A | Promote V2 pipeline Step 5 to autonomous_tick | Automated. Uses existing code. No new writer needed. | Adds V2 pipeline dependency to autonomous_tick. | **SELECTED** |
| B | Create standalone writer that reads from lifecycle_daily | Simple. One source. No pipeline dependency. | Duplicates V2 pipeline logic. Two writers for same table. | Rejected |
| C | Accept orphan status | Zero effort. | Table freezes when manual triggers stop. Breaks Segments tab. | Rejected |

**Selected: Option A — add `_build_taxonomy_v2_daily()` call to autonomous_tick after lifecycle_daily is built.**

### Implementation Design

```python
# In autonomous_tick cascade, after lifecycle build:
if os.getenv("LG_TAXONOMY_V2_ENABLED", "false").lower() == "true":
    from app.services.yego_lima_v2_daily_pipeline_service import _build_taxonomy_v2_daily
    _build_taxonomy_v2_daily(target_date)
```

**Requires:** lifecycle_daily to be built first (already in V2 pipeline Step 4). Feature flag to control rollout.

---

## ORPHAN 2: `growth.driver_movement_fact`

### Who Writes Really

| Writer | How | Evidence |
|--------|-----|----------|
| External one-shot SQL | Executed once for date 2026-06-10 | 68,473 rows for single date. Zero INSERT INTO in codebase. |
| V2 pipeline Step 7 | Writes to `growth.yego_lima_v2_movement_fact` (DIFFERENT table) | Pipeline run log: Step 7 produces 466 rows for 06-12. Not the same table. |

**Current reality:** This table has NO active writer. It was populated once externally. It will NEVER refresh without external intervention.

### Who Consumes

| Consumer | How | What It Reads |
|----------|-----|-------------|
| `yego_lima_movement_analytics_service.py` | `movement/stats`, `movement/matrix` | Reads directly from `driver_movement_fact` |
| `yego_lima_effectiveness_service.py` | `program_effectiveness_fact` computation | Reads from `driver_movement_fact` |
| `yego_lima_rna_priority_service.py` | RNA priority scoring | Reads `movement_score` from `driver_movement_fact` |

### Canonical Source Decision

**`v2_movement_fact` should become the canonical source.** It has:
- Active writer (V2 pipeline Step 7, runs successfully)
- Multi-date data (06-10, 06-11, 06-12)
- More fields (movement_type, from_state, to_state, from_program, to_program, trigger_reason)
- Same grain (driver × date × movement_type)

**`driver_movement_fact` should be deprecated.** It has:
- No writer (orphan)
- Single date (06-10 only)
- Different schema (movement_date, from_lifecycle, to_lifecycle, movement_class, movement_score)

### Remediation

| Step | Action | Impact |
|------|--------|--------|
| 1 | Migrate `movement_analytics_service` to read from `v2_movement_fact` instead of `driver_movement_fact` | Stats, matrix, winners/losers now use V2 source |
| 2 | Migrate `effectiveness_service` to read from `v2_movement_fact` | Effectiveness computation uses V2 source |
| 3 | Migrate `rna_priority_service` to read from `v2_movement_fact` or derive movement_score | RNA scoring uses V2 source or derived value |
| 4 | Add column mapping layer: `movement_date → target_date`, `from_lifecycle → from_state`, `to_lifecycle → to_state`, `movement_class → movement_type` | Backward compatibility for consumers |
| 5 | Validate: run V2 pipeline, verify all 3 consumers produce correct results | Integration test |
| 6 | After 1 week of shadow mode: drop `driver_movement_fact` table | Cleanup |

### Implementation Design

**No new writer needed.** `_build_movement_fact()` already exists and writes to `v2_movement_fact`. The fix is purely consumer-side: change 3 reader services to read from the correct table.

---

## SUMMARY

| Orphan | Current State | Target State | Writer Needed? | Consumer Changes? |
|--------|-------------|--------------|---------------|-----------------|
| `v2_taxonomy_daily` | Populated by V2 pipeline (manual trigger) | Automated via autonomous_tick | NO (writer exists) | NO (consumers already read this table) |
| `driver_movement_fact` | Populated once externally. Frozen at 06-10. | Deprecated. Consumers read `v2_movement_fact`. | NO (`_build_movement_fact()` writes to V2 table) | YES (3 service files) |

**Both orphans can be resolved without creating new writers. The fix is: automate existing writers (taxonomy) and fix consumer routing (movement).**
