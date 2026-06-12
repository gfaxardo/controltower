# CF-H2E.3 — LOAD AUDIT + READINESS SCORE

> **Fase:** CF-H2E.3 — Continuous Multipark Shadow
> **Sub-documents:** Load Audit + Source Promotion Readiness Score
> **Fecha:** 2026-06-12

---

## 1. LOAD AUDIT

### 1.1 Real Data (CF-H2E.2 live cycle)

| Park | Orders Pages | Orders Time | Txns Pages | Txns Time | Total Time | Records/sec |
|------|-------------|-------------|------------|-----------|------------|-------------|
| Lima | 10 | 62.5s | 21 | 109.7s | 172.2s | 140 |
| Trujillo | 2 | 8.8s | 1 | 3.7s | 12.5s | 9 |
| Arequipa | 0 | 21.6s | 1 | 3.3s | 24.9s | 0.7 |
| Pro | 2 | 16.4s | 1 | 3.7s | 20.1s | 9 |
| TukTuk | 2 | 16.1s | 1 | 3.3s | 19.4s | 2.6 |
| **TOTAL** | **16** | **125s** | **25** | **124s** | **249s** | — |

### 1.2 API Latency per Page

| Endpoint | Avg | P50 | P95 |
|----------|-----|-----|-----|
| Orders | ~6.3s | ~3s | ~16s |
| Transactions | ~5.0s | ~3s | ~5s |

### 1.3 Scalability Estimate

| Parks | Total Pages | Est. Runtime | Within 5-min? | Recommendation |
|-------|------------|-------------|--------------|----------------|
| 5 (current) | 41 | 249s (4.2 min) | YES | Sequential OK |
| 10 | ~82 | ~498s (8.3 min) | NO | Parallel: 2 workers |
| 20 | ~164 | ~996s (16.6 min) | NO | Parallel: 4 workers |
| 50 | ~410 | ~2,490s (41.5 min) | NO | Parallel: 8+ workers |

### 1.4 Bottleneck

**Transactions are the bottleneck.** Lima alone does 21 pages × ~5s = 109.7s for transactions. Orders are faster per page but scale with volume.

### 1.5 Answer

**¿Cuántos parks soporta la arquitectura actual?**

5 parks sequential OK. 10+ requires parallelization (one worker per park). Current architecture can handle 20+ parks with 4 parallel workers.

**¿Cuál es el cuello de botella?**

Transaction API latency per page (~5s/page). Each transaction page returns 1,000 records max. High-volume parks generate many pages.

---

## 2. SOURCE PROMOTION READINESS SCORE

### 2.1 Variables

| Variable | Source | Weight | Current |
|----------|--------|--------|---------|
| `coverage` | Yango data availability per park | 25% | 60 |
| `freshness` | Watermark age | 20% | 80 |
| `stability` | Reconciliation MATCH rate | 25% | 85 |
| `reconciliation` | Delta within threshold | 15% | 90 |
| `auth_reliability` | Auth success rate | 10% | 100 |
| `scheduler_reliability` | Scheduler uptime | 5% | 100 |

### 2.2 Formula

```
readiness = (coverage * 0.25) + (freshness * 0.20) + (stability * 0.25)
          + (reconciliation * 0.15) + (auth * 0.10) + (scheduler * 0.05)
```

### 2.3 Current Score

| Component | Score | Weighted |
|-----------|-------|----------|
| coverage | 60 | 15.0 |
| freshness | 80 | 16.0 |
| stability | 85 | 21.3 |
| reconciliation | 90 | 13.5 |
| auth_reliability | 100 | 10.0 |
| scheduler_reliability | 100 | 5.0 |
| **TOTAL** | — | **80.8** |

### 2.4 Classification

| Score | Classification | Action |
|-------|---------------|--------|
| ≥ 90 | READY_FOR_CERTIFICATION | Open CF-H2H |
| 70-89 | PARTIAL | Continue shadow 30 days |
| < 70 | NOT_READY | Fix gaps first |

**Current: PARTIAL (80.8). Need 30 days of continuous shadow to reach READY.**

### 2.5 What's Missing

| Gap | Impact | Action |
|-----|--------|--------|
| Only 1 cycle of live ingestion | Coverage = 60% | Run continuous scheduler for 30 days |
| Trujillo/Arequipa/Pro/TukTuk haven't run continuously | Freshness = 80% | Activate scheduler for all parks |
| Reconciliation only has 1 day of data | Stability = 85% | Run daily reconciliation for 30 days |
| No multi-cycle failure tracking | Scheduler = untested | Run continuous loop for 30 days |
