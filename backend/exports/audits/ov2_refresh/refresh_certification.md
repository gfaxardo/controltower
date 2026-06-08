# OV2 Refresh Chain Certification

**Generated:** 2026-06-08T04:17:24.759815+00:00
**Verdict:** **GO**
**Passed:** 10/10

| # | Check | Grain | Status | Data |
|---|-------|-------|--------|------|
| 1 | RAW trips freshness | day | PASS | {"max_date": "2026-06-06 23:59:57", "rows": 18001553} |
| 2 | day_fact freshness | day | PASS | {"max_date": "2026-06-06"} |
| 3 | week_fact freshness | week | PASS | {"max_date": "2026-04-20"} |
| 4 | month_fact freshness | month | PASS | {"max_date": "2026-06-01", "rows": 86} |
| 5 | snapshot freshness | day | PASS | {"max_date": "2026-06-05", "ready": 4, "failed": 0} |
| 6 | operating-date consistency | day | PASS | {"max_date": "2026-06-06"} |
| 7 | revenue availability | month | PASS | {"total": 86, "has_rev": 71, "pct": "82.6"} |
| 8 | slice coverage (Lima) | month | PASS | {"slices": 6} |
| 9 | plan version availability | month | PASS | {"versions": 12} |
| 10 | Yango raw availability | day | PASS | {"max_date": "2026-06-05", "rows": 2} |