# LG_GOV_2A_ORPHAN_REGISTRY

**Phase:** LG-CF-GOV-2A — Governance Hardening  
**Generated:** 2026-06-12  
**Scope:** Tables without versioned writers, external writers, legacy survivors

---

## ORPHAN TABLE: `growth.yego_lima_v2_taxonomy_daily`

| Attribute | Value |
|-----------|-------|
| **Status** | **UNGOVERNED** |
| **Rows** | 410,920 |
| **Max Date** | 2026-06-12 (FRESH — external process) |
| **Writer in code** | NONE — zero `INSERT INTO` in entire repo |
| **V2 shadow writer** | `_build_taxonomy_v2_daily()` writes to SAME table name (not `v2_*` prefix) — BUT runs manually |
| **Reader count** | 3 readers: `yego_lima_export_service.py:43`, explainability, rna_priority |
| **Consumer UI tabs** | Segments (primary), Driver Explorer (COALESCE) |
| **How populated** | External one-shot SQL + V2 pipeline manual runs |
| **Risk** | If V2 pipeline stops being manually triggered, table freezes. No automated path. |
| **Fix required** | Integrate V2 pipeline into autonomous_tick OR create dedicated governed writer |

---

## ORPHAN TABLE: `growth.driver_movement_fact`

| Attribute | Value |
|-----------|-------|
| **Status** | **BROKEN + UNGOVERNED** |
| **Rows** | 68,473 |
| **Max Date** | 2026-06-10 (STALE — 2 days behind) |
| **Writer in code** | NONE — zero `INSERT INTO` in entire repo |
| **V2 shadow writer** | `_build_movement_fact()` writes to `growth.yego_lima_v2_movement_fact` (DIFFERENT table) |
| **Reader count** | 3 readers: movement_analytics (stats/matrix/winners/losers), effectiveness, rna_priority |
| **Consumer UI tabs** | Movement tab |
| **How populated** | One-shot external SQL for single date 2026-06-10 |
| **Risk** | Table will NEVER refresh without external intervention. Single-date data is insufficient for trend analysis. |
| **Fix required** | Replace with `v2_movement_fact` as source of truth, OR create dedicated governed writer for this table |

---

## LEGACY TABLE: `growth.yego_lima_driver_taxonomy_daily`

| Attribute | Value |
|-----------|-------|
| **Status** | **UNGOVERNED (LEGACY)** |
| **Rows** | 18,545 |
| **Max Date** | 2026-06-10 (STALE) |
| **Writer** | `build_driver_taxonomy()` in `yego_lima_taxonomy_service.py:127` — manual POST only |
| **Note** | Pre-V2 taxonomy table. Almost certainly deprecated in favor of `v2_taxonomy_daily`. |
| **Consumer** | Legacy Segments tab (replaced by V2) |
| **Risk** | Stale data being read by legacy paths |

---

## LEGACY TABLE: `growth.yango_lima_driver_segment_snapshot`

| Attribute | Value |
|-----------|-------|
| **Status** | **DEPRECATED** |
| **Rows** | Unknown |
| **Writer** | `build_driver_segments()` — manual POST only |
| **Note** | Original segment snapshot (migration 165). Replaced by `driver_state_snapshot` + taxonomy. |
| **Consumer** | `build_daily_actionable_lists()` reads from it |
| **Risk** | If still read by actionable lists, its staleness propagates downstream |

---

## UNGOVERNED TABLE: `growth.yego_lima_loopcontrol_result_sync`

| Attribute | Value |
|-----------|-------|
| **Status** | **UNGOVERNED** |
| **Rows** | ~10 (near-empty) |
| **Writer** | `sync_loopcontrol_results()` — only on external LoopControl export |
| **Note** | Table populated by external system (LoopControl), not by any scheduled process in this repo. |
| **Consumer** | Explorer fact, impact tracking, RNA pilot |
| **Risk** | 10 rows = not operationally useful. Contact fields in Explorer always NULL. |

---

## EMPTY TABLE: `growth.yego_lima_impact_tracking`

| Attribute | Value |
|-----------|-------|
| **Status** | **UNGOVERNED** |
| **Rows** | 0 |
| **Writer** | Impact builders in `yego_lima_impact_service.py` — manual only |
| **Note** | Table exists but never populated. Purpose: measure post-contact driver behavior change. |
| **Risk** | Impact fields in Explorer always NULL. No post-contact measurement. |

---

## NOT DEPLOYED: `growth.yego_lima_driver_explorer_fact`

| Attribute | Value |
|-----------|-------|
| **Status** | **NOT DEPLOYED** |
| **Rows** | Table does not exist |
| **Writer** | `build_driver_explorer_fact()` — exists in code but migration 220 not applied |
| **Note** | Designed in LG-EXP-1B/1C/1D. Endpoint created in LG-EXP-1E. Table never created in production. |
| **Risk** | Driver Explorer UI cannot use canonical endpoint until fact is populated. |

---

## SUMMARY CLASSIFICATION

| Classification | Definition | Count | Tables |
|---------------|-----------|-------|--------|
| **HEALTHY** | Versioned writer + automated scheduler | 18 | Core operational layer (snapshot, eligibility, queue, serving, signals, logs) |
| **UNGOVERNED** | Data exists but writer is external, manual-only, or not in cascade | 5 | `v2_taxonomy_daily`, `driver_movement_fact`*, `v2_*` shadow tables, `loopcontrol_result_sync`, `impact_tracking` |
| **LEGACY** | Deprecated by newer tables but still read | 2 | `driver_taxonomy_daily`, `driver_segment_snapshot` |
| **DEPRECATED** | Should be removed or fully replaced | 1 | `driver_segment_snapshot` |
| **NOT DEPLOYED** | Designed and coded but not in production | 1 | `driver_explorer_fact` |

**5 UNGOVERNED tables represent the core governance debt. 2 LEGACY tables represent deprecated code still being consumed.**
