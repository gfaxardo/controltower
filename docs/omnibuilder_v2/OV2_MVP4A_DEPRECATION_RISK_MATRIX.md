# OV2-MVP.4A — DEPRECATION RISK MATRIX

> **Fase:** OV2-MVP.4A — Deprecation Preparation
> **Sub-document:** Risk Matrix
> **Fecha:** 2026-06-12

---

## RISK CATALOG

### OPERATIONAL

| # | Risk | Prob | Impact | Mitigation | Owner |
|---|------|------|--------|------------|-------|
| O1 | Operators reject V2, demand V1 return | LOW | HIGH | Training + trial period before cutover | Ops Lead |
| O2 | V2 shows wrong data, operators make wrong decisions | LOW | CRITICAL | Reconciliation endpoint + V1 available as backup | Engineering |
| O3 | V2 slower than V1, operators frustrated | LOW | MEDIUM | Snapshot-first architecture is faster than V1 | Engineering |

### DATA

| # | Risk | Prob | Impact | Mitigation | Owner |
|---|------|------|--------|------------|-------|
| D1 | commission_pct showing N/A confuses operators | MEDIUM | LOW | Training covers this. N/A is better than false 0. | Engineering |
| D2 | V2 data diverges from V1 (same serving facts) | VERY LOW | HIGH | Both read same fact tables. Reconciliation endpoint. | Engineering |
| D3 | Freshness goes stale during trial | LOW | MEDIUM | Status bar shows freshness. Scheduler auto-refreshes. | Engineering |

### UX

| # | Risk | Prob | Impact | Mitigation | Owner |
|---|------|------|--------|------------|-------|
| U1 | Signal colors misinterpreted (green = everything ok) | LOW | LOW | Training covers signal contract. Legend in status bar. | Ops Lead |
| U2 | Source badges confusing (CT vs YAN) | LOW | LOW | Training covers source badges. Only CT active now. | Ops Lead |
| U3 | Fullscreen mode causes confusion (can't find filters) | LOW | LOW | Filters visible in fullscreen. Esc to exit. Training. | UX |

### ADOPTION

| # | Risk | Prob | Impact | Mitigation | Owner |
|---|------|------|--------|------------|-------|
| A1 | Operators forget V2 exists, keep using V1 | MEDIUM | MEDIUM | V2 in nav sidebar. Trial enforces V2-first. Metrics track adoption. | Ops Lead |
| A2 | Only some operators adopt, team splits | LOW | MEDIUM | Mandatory trial for all roles. Training for all. | Ops Lead |

### PERFORMANCE

| # | Risk | Prob | Impact | Mitigation | Owner |
|---|------|------|--------|------------|-------|
| P1 | Matrix loads slow with large date ranges | LOW | LOW | Snapshot cache. Default range is 7 days. | Engineering |
| P2 | DB connection pool exhausted | VERY LOW | MEDIUM | /infra-health endpoint monitored. Pool auto-scales. | Engineering |

### INFRASTRUCTURE

| # | Risk | Prob | Impact | Mitigation | Owner |
|---|------|------|--------|------------|-------|
| I1 | V2 endpoint goes down | LOW | HIGH | Rollback to V1 < 5 min. V1 uses separate router. | Engineering |
| I2 | Frontend build fails | VERY LOW | HIGH | V1 frontend unchanged. Rollback = rebuild without V1_LEGACY_MODE flag. | Engineering |

### SOURCE GOVERNANCE

| # | Risk | Prob | Impact | Mitigation | Owner |
|---|------|------|--------|------------|-------|
| S1 | Yango source accidentally promoted | VERY LOW | CRITICAL | Source promotion is BLOCKED (CF-H2H). V2 defaults to CT. | Engineering |
| S2 | Operators mistake YANGO shadow for canonical | LOW | MEDIUM | SHADOW MODE banner. Source badge. canonical_ready = false. | Engineering |

---

## SEVERITY SUMMARY

| Severity | Count | Risks |
|----------|-------|-------|
| CRITICAL | 2 | O2 (wrong data), S1 (accidental promotion) |
| HIGH | 3 | O1 (rejection), D2 (divergence), I1 (endpoint down), I2 (build fail) |
| MEDIUM | 5 | O3, D3, A1, P2, S2 |
| LOW | 5 | D1, U1, U2, U3, A2, P1 |

---

## RISK HEATMAP

```
                    IMPACT
                LOW   MED   HIGH   CRIT
        HIGH                          S1*
        MED    D1    A1               
PROB    LOW    U1    O3    O1    O2
              U2,U3   D3    I1,I2
        V.LOW  P1    P2    D2
```

---

## MITIGATION STATUS

| Risk | Mitigation Ready? |
|------|------------------|
| O1 (rejection) | YES — training + trial |
| O2 (wrong data) | YES — reconciliation + V1 backup |
| O3 (slower) | YES — snapshot architecture |
| D1 (commission N/A) | YES — training covers |
| D2 (divergence) | YES — same fact tables |
| D3 (stale) | YES — scheduler + status bar |
| U1-U3 (UX confusion) | YES — training |
| A1-A2 (adoption) | YES — mandatory trial |
| P1-P2 (performance) | YES — monitoring |
| I1-I2 (infrastructure) | YES — rollback runbook |
| S1-S2 (source governance) | YES — CF-H2H BLOCKED |

**All risks have mitigations. 0 unmitigated risks.**
