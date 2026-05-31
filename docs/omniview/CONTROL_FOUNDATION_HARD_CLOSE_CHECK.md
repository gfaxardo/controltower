# CONTROL FOUNDATION — HARD CLOSE CHECK

**Fecha**: 2026-05-31
**Motor**: Control Foundation

---

## 1. Status por Área

| Área | Estado | Evidencia |
|------|--------|-----------|
| **Daily** | GO | `FACT_DAILY` = 2026-05-29, 602 filas May 2026 |
| **Weekly** | GO | `FACT_WEEKLY` = 2026-05-25, 221 filas Apr+May |
| **Monthly** | GO | `FACT_MONTHLY` = 2026-05-01 |
| **Projection** | GO | `serving.omniview_projection_daily_fact` = 2026-05-31 |
| **Revenue** | GO | Certificado en CF-H2 |
| **Active Drivers** | GO | Certificado en CF-H1 (daily distinct) |
| **Governance** | GO | Endpoint + UI card + health check funcional |
| **Health Guard** | GO | `check_omniview_serving_freshness.py` → PASS |
| **Priority Layer** | GO | RC-1, exclusiones correctas, build PASS |
| **Closed Period Engine** | GO | `periodInfoMap` implementado, daily/weekly/monthly anchoring |
| **Per-KPI Freshness** | GO | `compute_kpi_freshness()` funcional, mismatch detection en UI |
| **Canonical Source** | GO | `ops.real_business_slice_day_fact` identificada y auditada |

---

## 2. Governance Current State

```
Status: WARNING (acceptable — 2d daily lag)
  DAILY:      2026-05-29  lag=2  WARNING
  WEEKLY:     2026-05-25  lag=6  OK
  MONTHLY:    2026-05-01  OK
  PROJECTION: 2026-05-31  lag=0  OK
```

**No más BLOCKED.** El WARNING es esperado porque el último día completo es May 29 (2 días atrás).

---

## 3. Health Guard

```
RAW → 2026-05-29
DAILY → 2026-05-29
WEEKLY → 2026-05-25
PROJECTION → 2026-05-31
```

Con `max_lag_days=2`: **PASS**.

---

## 4. Build

```
Built in 5.54s
0 errors
OmniviewMatrix chunk: 325 KB (gzip 90 KB)
```

---

## 5. Riesgos Pendientes

| Riesgo | Severidad |
|--------|-----------|
| APScheduler depende de backend vivo | LOW (monitoreado por governance) |
| Week_fact sin COUNT DISTINCT de drivers (usa proxy desde day_fact) | LOW (misma limitación que H-2) |
| Backfill desde raw source es lento (~20 min) | LOW (mitigado con backfill desde FACT_DAILY, 2.6s) |

---

## 6. Veredicto Final

```
CONTROL FOUNDATION = CLOSED
```

Todos los criterios GO cumplidos. Omniview puede proceder a UX-H2.

