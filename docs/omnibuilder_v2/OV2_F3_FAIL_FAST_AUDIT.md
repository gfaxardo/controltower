# OV2-F.3 — FAIL FAST AUDIT

> **Date:** 2026-06-07
> **Motor:** Control Foundation / Freshness Chain
> **Status:** AUDIT COMPLETE

---

## 1. FAIL-FAST COVERAGE

| Code | Defined? | Implemented? | Triggers? |
|------|----------|-------------|-----------|
| `RAW_STALE` | ✓ (F.1 rules) | ✗ | No — no freshness sensor running |
| `DAY_FACT_STALE` | ✓ (F.1 rules) | ✓ (F.2 audit detected it) | ✓ — audit script |
| `WEEK_FACT_STALE` | ✓ | ✓ (F.2 detected 48-day gap) | ✓ — audit script |
| `MONTH_FACT_STALE` | ✓ | ✗ | No |
| `SNAPSHOT_STALE` | ✓ | ✓ (certification checks) | ✓ — certification |
| `SNAPSHOT_MISSING` | ✓ | ✓ (endpoint returns fast MISSING) | ✓ — API level |
| `WATERFALL_BROKEN` | ✓ | ✓ (validator script) | ✓ — script |
| `DRIVER_BRIDGE_STALE` | ✓ (F.2D) | ✗ | No |
| `ACTIVE_DRIVERS_UPPER_BOUND` | ✓ (F.2C) | ✗ | No |
| `DB_SATURATION` | ✓ | ✗ | No — only manual detection |

## 2. WHAT HAPPENS IF REFRESH FAILS

| If this fails... | Current behavior | Gap |
|-----------------|-----------------|-----|
| RAW has no new data | day_fact stays at last date, no alert | No alert until audit runs |
| day_fact refresh fails | week/month stay stale, scheduler reports "success" | False positive masks failure |
| Bridge not updated | week drivers use stale bridge data | No detection |
| Snapshot refresh fails | UI shows stale data or SERVING_SNAPSHOT_MISSING | UI degrades gracefully but no backend alert |

## 3. VERDICT

**YELLOW** — Rules defined (F.1/F.2D) but only 4/10 implemented at runtime. Detection is script-based (manual), not automated.

---

*End of Fail Fast Audit*
