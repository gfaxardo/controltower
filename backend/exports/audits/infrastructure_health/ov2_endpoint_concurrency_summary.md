# OV2 Endpoint Concurrency Audit Summary (SERVING-ONLY — NO allow_runtime)

> **Context:** OV2-H.2 retest. Matrix and shell use snapshot-first (no runtime fallback).
> Operating-date always runs runtime (no snapshot available). 1 uvicorn worker.
> **Key result:** 0 connection refusals on matrix & shell (vs H.1B: shell 0/45, matrix c=5 5/15).

**Generated:** 2026-06-07T14:30:11.358127+00:00
**Base URL:** http://localhost:8000
**Requests per test:** 15

## Summary Table

| Endpoint | Conc | Success | Timeouts | Conn Errors | Other | p50 (ms) | p95 (ms) | Max (ms) |
|----------|------|---------|----------|-------------|-------|----------|----------|----------|
| /ops/omniview-v2/operating-date @ c=1 | c=1 | 15/15 | 0 | 0 | 0 | 2982.2 | 3018.1 | 3031.0 |
| /ops/omniview-v2/operating-date @ c=3 | c=3 | 12/15 | 3 | 0 | 0 | 4817.2 | 15000.0 | 15000 |
| /ops/omniview-v2/operating-date @ c=5 | c=5 | 15/15 | 0 | 0 | 0 | 5418.2 | 6801.8 | 7451.5 |
| /ops/omniview-v2/matrix @ c=1 | c=1 | 15/15 | 0 | 0 | 0 | 2054.7 | 2070.3 | 2073.0 |
| /ops/omniview-v2/matrix @ c=3 | c=3 | 15/15 | 0 | 0 | 0 | 2048.3 | 2073.5 | 2076.4 |
| /ops/omniview-v2/matrix @ c=5 | c=5 | 15/15 | 0 | 0 | 0 | 2044.7 | 2052.1 | 2058.3 |
| /ops/omniview-v2/shell @ c=1 | c=1 | 15/15 | 0 | 0 | 0 | 2045.2 | 2067.3 | 2068.0 |
| /ops/omniview-v2/shell @ c=3 | c=3 | 15/15 | 0 | 0 | 0 | 2050.4 | 2066.5 | 2068.9 |
| /ops/omniview-v2/shell @ c=5 | c=5 | 15/15 | 0 | 0 | 0 | 2039.8 | 2061.0 | 2066.0 |

## Per-Concurrency Health

### Concurrency 1: **PASS**
- /ops/omniview-v2/operating-date @ c=1: 15/15 success, p50=2982.2ms p95=3018.1ms max=3031.0ms
- /ops/omniview-v2/matrix @ c=1: 15/15 success, p50=2054.7ms p95=2070.3ms max=2073.0ms
- /ops/omniview-v2/shell @ c=1: 15/15 success, p50=2045.2ms p95=2067.3ms max=2068.0ms

### Concurrency 3: **FAIL**
- /ops/omniview-v2/operating-date @ c=3: 12/15 success, p50=4817.2ms p95=15000.0ms max=15000ms
- /ops/omniview-v2/matrix @ c=3: 15/15 success, p50=2048.3ms p95=2073.5ms max=2076.4ms
- /ops/omniview-v2/shell @ c=3: 15/15 success, p50=2050.4ms p95=2066.5ms max=2068.9ms

### Concurrency 5: **PASS**
- /ops/omniview-v2/operating-date @ c=5: 15/15 success, p50=5418.2ms p95=6801.8ms max=7451.5ms
- /ops/omniview-v2/matrix @ c=5: 15/15 success, p50=2044.7ms p95=2052.1ms max=2058.3ms
- /ops/omniview-v2/shell @ c=5: 15/15 success, p50=2039.8ms p95=2061.0ms max=2066.0ms

## GO/NO-GO Assessment

**NO-GO** — Failures or connection errors detected. Review failed rows above.