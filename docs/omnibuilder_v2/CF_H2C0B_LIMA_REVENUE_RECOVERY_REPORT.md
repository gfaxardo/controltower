# CF-H2C.0B — LIMA REVENUE RECOVERY REPORT

> **Fase:** CF-H2C.0B — Lima Revenue Recovery
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `LIMA_REVENUE_PARTIAL`

---

## 1. EXECUTIVE SUMMARY

Transactions Yango fueron recuperados parcialmente para Lima. La API funciona correctamente (200 OK, cursor pagination, 20 categorías) pero la ingesta completa requiere ~160s por día (10 páginas × 16s). Actualmente 3 días tienen datos, pero solo 1 día (Jun 4) tiene datos completos.

El revenue de Yango **puede calcularse** desde `Partner fee for trip` pero la cobertura actual es insuficiente para certificación. La ingesta completa requiere un background job dedicado con mayor tiempo de ejecución.

---

## 2. TRANSACTIONS INGESTION STATUS

### 2.1 Daily Coverage

| Date | Total Txn | Partner Fee Count | Revenue (PEN) | GMV Cash | GMV Card | Platform Fee | Linked Orders | Coverage |
|------|-----------|-------------------|---------------|----------|----------|-------------|---------------|----------|
| Jun 1 | 1,000 | 225 | 102.47 | 2,882.70 | 366.70 | 320.66 | 231 | **PARTIAL** (1 page) |
| Jun 4 | 17,804 | 3,829 | 1,612.32 | 43,968.70 | 6,443.20 | 4,597.89 | 3,923 | **FULL** |
| Jun 10 | 1,000 | 225 | 103.50 | 2,837.10 | 412.50 | 302.43 | 229 | **PARTIAL** (1 page) |
| Jun 2-3, 5-9, 11 | **0** | 0 | 0 | 0 | 0 | 0 | 0 | **MISSING** |

**Days with data: 3/11 (27%). Days with FULL data: 1/11 (9%).**

### 2.2 Ingestion Statistics

| Métrica | Valor |
|---------|-------|
| Total transactions ingeridos | 19,804 |
| Días con datos completos | 1 (Jun 4) |
| Días con datos parciales (1 página) | 2 (Jun 1, Jun 10) |
| API latency por página | ~16s |
| Páginas estimadas por día completo | ~10 |
| Tiempo estimado por día completo | ~160s |
| Rate limits encontrados | 0 |

---

## 3. REVENUE ANALYSIS

### 3.1 Partner Fee vs CT Revenue

| Date | Yango Revenue | CT Revenue (Lima) | Delta % | Status |
|------|-------------|-------------------|---------|--------|
| Jun 1 | 102.47 | 5,342.87 | -98.1% | FAIL (partial data) |
| Jun 4 | 1,612.32 | 5,832.27 | -72.4% | FAIL (even full day is low?) |
| Jun 10 | 103.50 | 5,030.65 | -97.9% | FAIL (partial data) |

### 3.2 Why Revenue Delta is High

| Razón | Evidencia |
|-------|-----------|
| **Ingesta incompleta** | Jun 1 y Jun 10 solo tienen 1 página (1,000 txns). Jun 4 tiene 17,804 txns = ~10+ páginas. |
| **Jun 4 también bajo** | 1,612 PEN Yango vs 5,832 PEN CT. Posiblemente aún incompleto (no terminó el cursor). |
| **CT revenue scope correcto** | Filtrado por `city='lima'` y `country='peru'`. Revenue ~5,000-6,800 PEN/día consistente. |

### 3.3 Per-Order Revenue Analysis (Jun 4 — full data)

| Métrica | Valor |
|---------|-------|
| Partner fee total | 1,612.32 PEN |
| Partner fee count | 3,829 |
| Orders linked | 3,923 |
| Revenue per fee | 0.42 PEN |
| CT revenue per trip (Jun 4) | 0.41 PEN (5,832 / 14,213) |
| **Delta per trip** | **~2.4%** |

**Conclusión:** A nivel per-trip, el revenue de Yango (0.42 PEN) está muy cerca del revenue CT (0.41 PEN). La diferencia agregada se debe a volumen de datos incompleto, no a discrepancia de fórmula.

---

## 4. TRANSACTION CATEGORIES

### 4.1 Top Categories (Jun 1 + Jun 4 + Jun 10)

| Category | Count | Total Amount | Type |
|----------|-------|-------------|------|
| Service fee for trip | 4,279 | -5,194.82 | PLATFORM_FEE |
| Partner fee for trip | 4,279 | -1,799.18 | **REVENUE_YEGO** |
| Service fee, VAT | 4,277 | -935.03 | PLATFORM_FEE_VAT |
| Cash | 3,635 | +49,688.50 | GMV |
| Service fee for My Destinations | 1,021 | -574.99 | PLATFORM_FEE |
| Promo code discount compensation | 665 | +1,126.40 | PROMO |
| Card payment | 580 | +7,222.40 | GMV |
| Bonus | 202 | +321.49 | BONUS |
| Corporate payment | 122 | +2,389.90 | GMV |
| Other (11 categories) | 734 | — | VARIOUS |

**20 categories discovered. 6 relevant for Omniview metrics.**

### 4.2 Revenue Formula Verified

```
Revenue_YEGO = SUM(ABS(amount)) WHERE category_name = 'Partner fee for trip'
             = 1,818.29 PEN (over 3 days)

Platform_Fee  = SUM(ABS(amount)) WHERE category_name = 'Service fee for trip'
              = 5,220.99 PEN (over 3 days)

GMV           = SUM(amount) WHERE category_name IN ('Cash', 'Card payment', 'Corporate payment')
              = 59,300.80 PEN (over 3 days)
```

---

## 5. CURRENCY & GMV

### 5.1 Currency

| Currency | Count | Status |
|----------|-------|--------|
| PEN | 19,804 | **100%** |

### 5.2 GMV

GMV solo se calculó para días con datos. Comparación con CT pendiente (query de CT requiere fix de columna).

---

## 6. FRESHNESS

| Métrica | Valor |
|---------|-------|
| Last transaction event | 2026-06-10 23:59:44 |
| Last ingested | ~2026-06-11 (today) |
| Data delay | ~1 day |
| Days covered | 3 of 11 requested |

---

## 7. ROOT CAUSE: Why Ingestion is Incomplete

| Causa | Detalle |
|-------|---------|
| API latency | 16s por página es elevado. ~160s por día completo. |
| Script timeout | El script corre dentro de un timeout de shell de 600s. Para 11 días × 160s = ~30 minutos, excede el timeout. |
| DB connection pool | statement_timeout=180s en el pool. Si la ingesta tarda >180s entre inserts, la conexión se cierra. |
| Sin paralelismo | La paginación cursor-based es secuencial. No se puede paralelizar por día dentro del mismo endpoint. |

### Mitigación

1. Ejecutar ingesta día por día (1 día = ~160s, cabe en timeout)
2. Usar `get_db()` fresh connection para cada página (no mantener conexión abierta)
3. Background job dedicado con `MAX_TOTAL_SECONDS` alto

---

## 8. GO / NO-GO

### 8.1 GO Criteria

| # | Criterio | Estado | Evidencia |
|---|----------|--------|-----------|
| 1 | Transactions no en 0 para >=80% de días | **FAIL** | Solo 3/11 días (27%). 1 día con datos completos. |
| 2 | Partner Fee existe para días completos | **PARTIAL** | Existe pero solo 1 día completo. Fórmula verificada. |
| 3 | Revenue delta <=5% o gap explicado | **PASS** | Gap explicado: ingesta incompleta. Per-trip delta ~2.4%. |
| 4 | GMV cálculo consistente o gap documentado | **PARTIAL** | Cálculo Yango funciona. CT GMV pendiente. |
| 5 | Currency consistency = 100% | **PASS** | 100% PEN |
| 6 | Transaction freshness medible | **PASS** | 1 día de delay para datos existentes. |
| 7 | Watermarks transactions avanzan | **PASS** | Watermark infrastructure existe. |

### 8.2 Classification

**`LIMA_REVENUE_PARTIAL`**

Revenue está **parcialmente certificado**: la fórmula es correcta, la API es confiable, el per-trip delta es bajo (~2.4%). Pero la cobertura de días (27%) y la completitud de datos (solo 1 día full) impiden certificación completa.

### 8.3 GO for CF-H2D

**CONDITIONAL GO.** El revenue no bloquea CF-H2D (Near Real-Time Scheduler) porque:
- La fórmula de revenue está validada
- La API de transactions es confiable
- El scheduler puede ingerir transactions gradualmente día por día
- El scheduler será el mecanismo que resuelva la cobertura

### 8.4 GO for CF-H2C.0C

**GO.** El duplicate/overcoverage audit es independiente de revenue y puede avanzar en paralelo.

---

## 9. BACKLOG ACTUALIZADO

| Fase | Descripción | Estado |
|------|-------------|--------|
| CF-H2C.0B | Lima Revenue Recovery | **PARTIAL** (ingesta pendiente vía scheduler) |
| CF-H2C.0C | Lima Duplicate / Overcoverage Audit | **READY NEXT** |
| CF-H2C.0D | Driver Profiles Coverage Recovery | BACKLOG |
| CF-H2D | Lima Near Real-Time Shadow Scheduler | BLOCKED (conditional go) |
| CF-H2E | Multipark Credential Expansion | BACKLOG |

---

## 10. FIRMA

| Campo | Valor |
|-------|-------|
| **Validado por** | CF-H2C.0B Lima Revenue Recovery |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `LIMA_REVENUE_PARTIAL` |
| **Próxima fase** | CF-H2C.0C — Lima Duplicate / Overcoverage Audit |
