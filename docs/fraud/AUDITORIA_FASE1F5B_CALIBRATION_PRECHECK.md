# AUDITORIA FASE 1F-5B — CALIBRATION PRECHECK

**Fecha**: 2026-05-20
**Branch**: master
**Working tree**: main.py + settings.py modified (wiring F1F), all fraud files untracked

---

## FASE 1F-5A State

| Check | Status |
|---|---|
| AUDITORIA_FASE1F5_TRIP_BEHAVIOR_RESULTS.md | EXISTS |
| AUDITORIA_FASE1F5A_FIRST_REAL_RUN.md | EXISTS |
| open_cases | 256 |
| behavioral cases (May 20) | 236 |
| rule_threshold_config table | NOT EXISTS (need to create) |
| enabled rules | 22 total, 11 behavioral |

## Files clean status

- main.py: modified (fraud router wiring)
- settings.py: modified (BANK_CLUSTER_SALT + env)
- All fraud files: untracked (expected)
- Omniview: untouched
- Plan vs Real: untouched

## Decision

**GO** — Precheck passed. Ready for threshold calibration.
