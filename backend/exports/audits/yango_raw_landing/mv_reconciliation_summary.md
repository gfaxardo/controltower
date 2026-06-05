# raw_yango MVs vs Control Tower — Reconciliation

**Generated:** 2026-06-05T09:34:53.179673-05:00
**Date Range:** 2026-06-04 -> 2026-06-05 (CT exclusive end)
**Park ID (masked):** 08e20910***
**Days with MV+CT overlap:** 1 / 2

## 1. Summary

| Metric | MV (raw_yango) | CT (final) | CT (net) |
|--------|----------------|------------|----------|
| Trips | 4,500 | 14,213 | — |
| Revenue | 1,612.32 | 5,832.27 | 0.00 |
| Drivers | 1,546 | 1,770 | — |

## 2. Daily Detail

| Date | MV Trips | CT Trips | Trip Class | MV Revenue | CT Rev Final | CT Rev Net | Rev Class | MV Drivers | CT Drivers |
|------|----------|----------|------------|------------|-------------|-----------|-----------|------------|------------|
| 2026-06-04 | 2,977 | 14,213 | **NEEDS_INVESTIGATION** | 1,256.37 | 5,832.27 | 0.00 | **NEEDS_INVESTIGATION** | 900 | 1,770 |
| 2026-06-05 | 1,523 | 0 | **API_ONLY** | 355.95 | 0.00 | 0.00 | **API_ONLY** | 646 | 0 |

## 3. Classification

| Class | Criteria |
|-------|----------|
| MATCH | delta < 1% |
| MINOR_DELTA | 1% ≤ delta < 5% |
| MAJOR_DELTA | 5% ≤ delta < 20% |
| CT_ONLY | Data in CT but not MV |
| API_ONLY | Data in MV but not CT |
| NO_OVERLAP | No shared dates |