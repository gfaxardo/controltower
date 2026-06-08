# OV2-F.3 — WATERFALL SIMULATION

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Freshness Chain
> **Status:** SIMULATION COMPLETE

---

## SIMULATION: RAW max = 2026-06-06 (today = 06-07, D-1)

| Layer | Expected Max | Actual Max | Gap | Auto? | Status |
|-------|-------------|-----------|-----|-------|--------|
| RAW | 2026-06-06 | 2026-06-06 | D-1 | ✓ (continuous) | **GREEN** |
| BRIDGE | 2026-06-06 | 2026-06-06 | D-1 | ✗ (manual F.2E) | **YELLOW** |
| DAY | 2026-06-06 | 2026-06-06 | D-1 | ✓ (scheduler daily) | **GREEN** |
| WEEK | 2026-06-01 | 2026-06-01 | Current week | ✗ (manual F.2E) | **YELLOW** |
| MONTH | 2026-06-01 | 2026-06-01 | Current month | ✓ (scheduler, raw path) | **YELLOW** |
| SNAPSHOT | 2026-06-05 | 2026-06-05 | D-2 | ✗ (manual) | **YELLOW** |

## GAPS

1. **Bridge not automatic** — F.2E was a manual execution. Will go stale unless re-run.
2. **Week not automatic** — F.2E rebuilt it, but next week won't update automatically.
3. **Month uses raw** — Drivers come from raw, not bridge. Will stale silently.
4. **Snapshots not automatic** — Must be triggered manually after facts update.

## IF RAW ADVANCES TOMORROW (06-07)

| Layer | Auto refresh? | Will it update? |
|-------|--------------|-----------------|
| RAW | ✓ | Yes (new trips ingested) |
| Bridge | ✗ | **NO — will stale** |
| Day | ✓ (APScheduler 04:00) | Maybe — if job actually loads new dates |
| Week | ✗ | **NO** |
| Month | ✓ (raw path) | Maybe |
| Snapshot | ✗ | **NO** |

**Result: 3 of 6 layers will go stale.**

---

*End of Waterfall Simulation*
