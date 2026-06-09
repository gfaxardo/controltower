# CT-GOV-043 — Cross-System Audit

**Date:** 2026-06-08
**Motor:** Control Foundation / Global Freshness Governance
**Status:** CANONICAL

---

## 1. AUDIT SCOPE

Two systems audited against the new governance standards:
- **Omniview** — Control Tower core operational dashboard
- **Lima Growth** — Yego driver growth management

---

## 2. OMNIVIEW AUDIT

### Serving Layer Inventory

| Check | Status |
|-------|:---:|
| All layers documented | YES (8 layers, OV2-F.1) |
| Source tables identified | YES |
| Refresh owner defined | YES |
| Scheduler owner defined | YES (APScheduler 04:00) |
| Layer date tracked | YES |
| Effective source date tracked | **NO** — GAP |

### Effective Source Date Contract

| Check | Status |
|-------|:---:|
| layer_date exposed | PARTIAL (operating-date endpoint) |
| effective_source_date exposed | **NO** |
| freshness_gap_days exposed | **NO** |
| freshness_status exposed | PARTIAL (FreshnessBanner) |

### Freshness SLA

| Check | Status |
|-------|:---:|
| SLA defined per layer | YES (OV2-F.1) |
| SLA monitored | PARTIAL (watchdog every 15min) |
| SLA violations detected | YES (week_fact 48 days) |
| SLA violations remediated | **NO** — week_fact still 48 days behind |

### Ownership

| Check | Status |
|-------|:---:|
| 1 table = 1 writer | YES (OV2-F.4A cleanup) |
| Legacy writers deprecated | YES (4 deprecated) |
| Double writers detected | NONE |

### Waterfall

| Check | Status |
|-------|:---:|
| RAW → FACT → SNAPSHOT → UI defined | YES |
| All transitions validated | PARTIAL (week_fact gap) |
| No STALE_PROPAGATED | UNKNOWN (no effective source date check) |

### Runtime Certification

| Check | Status |
|-------|:---:|
| Version exposed | PARTIAL (backend-identity) |
| Git hash exposed | **NO** |
| Build time exposed | **NO** |

### Classification

```
OMNIVIEW: PARTIAL
- Serving layer inventory: COMPLIANT
- Effective source date: NON_COMPLIANT
- SLA: PARTIAL (defined but week_fact not fixed)
- Ownership: COMPLIANT
- Waterfall: PARTIAL (week_fact broken)
- Runtime: NON_COMPLIANT
```

---

## 3. LIMA GROWTH AUDIT

### Serving Layer Inventory

| Check | Status |
|-------|:---:|
| All layers documented | YES (14 layers, R3.0C) |
| Source tables identified | YES |
| Refresh owner defined | YES |
| Layer date tracked | YES |
| Effective source date tracked | **YES** (R3.0E) |

### Effective Source Date Contract

| Check | Status |
|-------|:---:|
| layer_date exposed | YES |
| effective_source_date exposed | YES (`/freshness-chain/status`) |
| freshness_gap_days exposed | YES |
| freshness_status exposed | YES (FRESH/STALE/STALE_PROPAGATED) |

### Freshness SLA

| Check | Status |
|-------|:---:|
| SLA defined per layer | YES (R3.0C) |
| SLA monitored | YES (autonomous_tick every 5min) |
| SLA violations detected | YES (Yango stale, now resolved) |
| SLA violations remediated | YES (R3.0F normalization) |

### Ownership

| Check | Status |
|-------|:---:|
| 1 table = 1 writer | YES |
| Legacy writers deprecated | YES (driver_360, eligible_universe) |
| Dead layers documented | YES (R2.0 decision memo) |

### Waterfall

| Check | Status |
|-------|:---:|
| RAW → HISTORY → SNAPSHOT → SERVING → UI defined | YES |
| All transitions validated | YES (R3.0A dependency cert) |
| STALE_PROPAGATED detected and resolved | YES (R3.0E → R3.0F) |

### Runtime Certification

| Check | Status |
|-------|:---:|
| Version exposed | YES (`/` returns 2.0.0) |
| Source system exposed | YES (YANGO_API_LIVE) |
| Git hash exposed | **NO** |

### Classification

```
LIMA GROWTH: COMPLIANT
- Serving layer inventory: COMPLIANT
- Effective source date: COMPLIANT
- SLA: COMPLIANT
- Ownership: COMPLIANT
- Waterfall: COMPLIANT
- Runtime: PARTIAL (git_hash missing)
```

---

## 4. GAP SUMMARY

| # | System | Gap | Severity | Remediation |
|---|--------|-----|:---:|-------------|
| 1 | Omniview | No effective source date tracking | HIGH | Implement `/freshness-chain` endpoint |
| 2 | Omniview | week_fact 48 days stale | CRITICAL | Run bridge cascade rebuild |
| 3 | Both | No git_hash in runtime identity | LOW | Add to build process |
| 4 | Lima Growth | 3 UI endpoints bypass serving facts | LOW | Migrate to serving-first |

---

## FIRMA

```
CT-GOV-043 CROSS-SYSTEM AUDIT
Date: 2026-06-08
Status: Lima Growth COMPLIANT | Omniview PARTIAL
```
