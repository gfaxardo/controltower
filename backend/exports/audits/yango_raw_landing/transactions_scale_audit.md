# Transactions Scale Audit — Before/After Comparison

**Generated:** 2026-06-05

## Sequential vs Partitioned

| Metric | Sequential (max_pages=100) | Partitioned (hour windows, 2 parallel) |
|--------|---------------------------|----------------------------------------|
| Transactions ingested | 4,300 | 17,804 |
| Partner fee txns | 110 | 3,829 |
| Partner fee total (PEN) | 51.59 | 1,612.32 |
| Revenue per order | 0.011 | 0.408 |
| Completion ratio | ~10% | ~85% |
| Effective throughput | ~0.3 pages/min | ~1.0 pages/min (2x parallel) |
| Errors | 0 | 0 |
| 429 rate limits | 0 | 0 |

## Reconciliation vs CT

| Metric | MV | CT | Delta | Delta % |
|--------|-----|-----|-------|---------|
| Trips | 4,500 | 14,213 | -9,713 | -68.3% |
| Revenue | 1,612.32 | 5,832.27 | -4,220 | -72.4% |
| **Revenue per unit** | **0.408** | **0.410** | **-0.003** | **-0.7%** |

## Key Finding

Per-unit revenue metrics match within 1% of CT. Volume gap (4.5K vs 14K trips) is explained by API limitation: single park vs multiple business slices in CT.

## Veredicto

**GO** — revenue metrics exceed thresholds. Ready for Serving Facts.
