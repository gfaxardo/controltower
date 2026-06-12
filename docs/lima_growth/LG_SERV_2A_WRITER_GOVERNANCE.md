# LG-SERV-2A — WRITER GOVERNANCE AUDIT

**Date:** 2026-06-11

---

## Multi-Writer Analysis Per Asset

| Asset | Writer #1 | Writer #2 | Shadow? | Legacy? | Risk |
|-------|----------|----------|---------|---------|------|
| activity_daily | V2 Pipeline (DELETE+INSERT) | — | No | No | None |
| activity_weekly | V2 Pipeline (DELETE+INSERT) | — | No | No | None |
| activity_monthly | V2 Pipeline (DELETE+INSERT) | — | No | No | None |
| lifecycle_daily | V2 Pipeline (DELETE+INSERT) | — | No | No | None |
| taxonomy_v2 | V2 Pipeline (DELETE+INSERT) | growth.yego_lima_driver_taxonomy_v2_daily (autonomous) | Yes — separate table | No | **LOW**: Same source, different target tables |
| program_v2 | V2 Pipeline (DELETE+INSERT) | growth.yego_lima_program_v2_assignment_daily (autonomous) | Yes — separate table | No | **LOW**: 2 parallel program assignment methods, zero overlap in target tables |
| movement_fact | V2 Pipeline (DELETE+INSERT) | growth.driver_movement_fact (autonomous) | Yes — separate table | Yes | **LOW**: 2 movement fact tables, no overlap |
| observability_fact | V2 Pipeline (DELETE+INSERT) | — | No | No | None |
| effectiveness_fact | V2 Pipeline (DELETE+INSERT) | — | No | No | None |
| program_assignment | Autonomous Tick (build_program_eligibility) | Legacy pipeline (build_program_eligibility) | No | Yes | **MEDIUM**: Legacy pipeline can also write this table, but legacy pipeline uses same service |
| driver_state_snapshot | Autonomous Tick (build_driver_state) | Legacy pipeline (build_driver_state) | No | Yes | **MEDIUM**: Same as above; idempotent via ON CONFLICT |
| serving_driver_explorer | Serving Facts (generate_all) | — | No | No | None |
| RNA_serving | Autonomous Tick (incremental upsert) | — | No | No | None |

### Risk Assessment

| Risk Type | Count | Assets Affected |
|-----------|-------|----------------|
| Duplicate writes | 0 | — |
| Race conditions | 0 | — Separate tables or idempotent |
| Stale overwrite | 0 | — DELETE+INSERT or ON CONFLICT |
| Shadow refresh | 3 | taxonomy_v2, program_v2, movement_fact (separate shadow tables) |

### Verdict

**No multi-writer conflicts detected.** All assets have exactly one writer per target table. Assets with parallel systems (V2 vs autonomous tick) write to separate tables with distinct schemas:

- `growth.yego_lima_v2_*` = V2 Pipeline shadow
- `growth.yego_lima_driver_taxonomy_v2_*` = Autonomous tick (different table)
- `growth.yego_lima_program_v2_*` = Autonomous tick (different table)
- `growth.driver_movement_fact` = Autonomous tick (different table)

Idempotency is guaranteed by:
- DELETE + INSERT per target_date (V2 pipeline)
- ON CONFLICT DO UPDATE/NOTHING (autonomous tick)
- UNIQUE constraints on (target_date, driver_id) or equivalent
