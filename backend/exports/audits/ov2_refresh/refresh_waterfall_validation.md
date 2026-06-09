# Refresh Waterfall Validation

**Generated:** 2026-06-08T18:11:54.110215+00:00
**Verdict:** **GO**

| Check | Upstream | Upstream Val | Downstream | Downstream Val | Status |
|-------|----------|-------------|------------|---------------|--------|
| RAW_to_DAY | RAW_TRIPS | 2026-06-07 | DAY_FACT | 2026-06-07 | OK |
| DAY_to_WEEK | DAY_FACT | 2026-06-07 | WEEK_FACT | 2026-06-01 | OK |
| WEEK_to_MONTH | WEEK_FACT | 2026-06-01 | MONTH_FACT | 2026-06-01 | OK |
| DAY_to_SNAPSHOT | DAY_FACT | 2026-06-07 | SNAPSHOT | 2026-06-05 | OK |
| SNAPSHOT_to_UI | - | 2026-06-05 | - | UI endpoints | OK |