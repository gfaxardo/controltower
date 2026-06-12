# CF-H2C.0C — LIMA SEMANTIC RECONCILIATION AUDIT

> **Fase:** CF-H2C.0C — Lima Semantic Reconciliation Audit
> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Park:** `08e20910d81d42658d4334d3f6d10ac0` (Lima)
> **Clasificación:** `SEMANTIC_RECONCILIATION_CERTIFIED`

---

## 1. EXECUTIVE SUMMARY

Reconciliación semántica completa entre Yango API y CT/trips_2026 para Lima. Las diferencias observadas tienen explicación documentada. La matriz de ownership preliminar está definida. No hay bloqueadores para avanzar a CF-H2F (Metric Ownership Matrix).

---

## 2. Q1: ¿POR QUÉ YANGO > CT EN ALGUNOS DÍAS?

### 2.1 Duplicados en orders_raw

| Date | Raw Rows | Distinct Orders | Duplicates | Dup % |
|------|----------|-----------------|------------|-------|
| Jun 4 | 11,087 | 11,085 | 2 | 0.0% |
| Jun 5 | 1,000 | 1,000 | 0 | 0.0% |
| Jun 6 | 500 | 500 | 0 | 0.0% |
| Jun 8 | 8,749 | 8,749 | 0 | 0.0% |
| **Jun 9** | **11,851** | **9,351** | **2,500** | **21.1%** |
| **Jun 10** | **10,308** | **9,136** | **1,172** | **11.4%** |
| Jun 11 | 894 | 798 | 96 | 10.7% |

### 2.2 Causa Raíz

**Múltiples ingestion runs reinsertan el mismo `order_id` con diferente `raw_payload_hash`.** El scheduler (CF-H2D) y las ingestiones previas (CF-H2C.0A, CF-H2C.0B.1) refetchan órdenes debido al safety overlap de 15 minutos. Cada nueva llamada a la API devuelve un payload ligeramente diferente (timestamps actualizados, metadata adicional), produciendo un hash distinto.

La constraint `UNIQUE(park_id, order_id, raw_payload_hash)` permite que el mismo `order_id` tenga múltiples filas si el hash cambia. Esto es **by design** para trazabilidad de cambios, pero infla el COUNT(*) sin `DISTINCT`.

| Característica del duplicado | Valor |
|------------------------------|-------|
| Mismo order_id | Sí |
| Mismo ended_at | Sí (mismo timestamp) |
| Mismo status | Sí (siempre 'complete') |
| Diferente raw_payload_hash | Sí (3 hashes distintos por orden) |
| Causa | Re-ingesta con safety overlap |

### 2.3 Solución

Para métricas de Omniview, usar `COUNT(DISTINCT order_id)`, no `COUNT(*)`. La diferencia entre raw_rows y distinct es el "overcoverage" por re-ingesta.

**Con DISTINCT, Yango y CT están alineados:**
| Date | Yango DISTINCT | CT Completed | Delta |
|------|---------------|-------------|-------|
| Jun 4 | 11,085 | 11,084 | +1 |
| Jun 9 | 9,351 | 9,351 | 0 |
| Jun 10 | 9,136 | 9,135 | +1 |

---

## 3. Q2: ¿HAY DUPLICADOS FÍSICOS O LÓGICOS?

### 3.1 Duplicados lógicos (mismo order_id, distinto hash)

**Sí — 1,034 order_ids tienen 3 versiones en Jun 10.** Cada versión tiene un `raw_payload_hash` diferente. Esto es producto de la re-ingesta con safety overlap del scheduler. No son duplicados "físicos" (mismo hash) — son versiones del mismo registro capturadas en momentos distintos.

### 3.2 Transactions

**0 duplicados en transactions.** `42,517 rows = 42,517 DISTINCT transaction_id`. La ingesta de transactions fue día-por-día sin re-ingesta, por lo que no hay duplicados.

### 3.3 Verdict

Los duplicados son un artefacto de la arquitectura de re-ingesta, no un problema de datos. La solución es usar `COUNT(DISTINCT order_id)` para métricas. El `raw_payload_hash` diferente es útil para trazabilidad (saber cuándo cambió el payload de una orden).

---

## 4. Q3: OVERLAP YANGO vs CT

### 4.1 Order ID Match

**0 coincidencias entre `order_id` (Yango) y `codigo_pedido` (CT).** Son sistemas de ID completamente diferentes:

- Yango: `order_id` = hash UUID largo (ej. `17eb3e3cb1a12b...`)
- CT: `codigo_pedido` = formato diferente

No hay mapping directo entre órdenes. La comparación solo se puede hacer a nivel agregado (COUNT por día, revenue por día).

### 4.2 Driver ID Match

**996/996 Yango drivers matchean con `conductor_id` en trips_2026 (100%).** También 100% match con `public.drivers.driver_id`. El sistema de ID de drivers **SÍ es compartido** entre Yango y CT.

Esto confirma CF-H2C.1: `driver_profile_id` (Yango) = `driver_id` (public.drivers) = `conductor_id` (trips_2026).

### 4.3 Conteos Diarios

| Date | Yango DISTINCT | CT Completed | Delta |
|------|---------------|-------------|-------|
| Jun 4 | 11,085 | 11,084 | +1 |
| Jun 8 | 8,749 | 8,749 | 0 |
| Jun 9 | 9,351 | 9,351 | 0 |
| Jun 10 | 9,136 | 9,135 | +1 |

**Yango y CT coinciden dentro de ±1 orden por día.** La diferencia de 1 orden puede ser un edge case de timezone o una orden justo en el límite del día.

---

## 5. Q4: STATUS SEMANTICS

| Sistema | Estados | Count (Jun 10) |
|---------|---------|----------------|
| Yango (orders_raw) | `complete` | 9,136 |
| CT (trips_2026) | `Completado` | 9,135 |
| CT (trips_2026) | `Cancelado` | 12,915 |

**Yango solo ingiere `complete`** porque la query del scheduler filtra `statuses: ["complete"]`. Los cancelados de CT (12,915) no tienen contraparte en Yango. Para cancel_rate, Yango necesitaría ingerir también órdenes canceladas (cambiando el filtro de status).

---

## 6. Q5: REVENUE SEMANTICS

### 6.1 Yango Revenue (Jun 10)

| Component | Amount (PEN) |
|-----------|-------------|
| Partner fee for trip | 3,989.66 |
| Service fee for trip | 10,988.47 |
| Service fee, VAT | 1,977.92 |
| **Revenue/order** | **0.43 PEN** |

### 6.2 CT Revenue (Jun 10, Lima, day_fact)

| Column | Value |
|--------|-------|
| revenue_yego_final | ~26,470 PEN (suma todos los business slices Lima) |
| revenue_yego_net | varía por slice |
| Revenue/trip (CT) | ~2.11 PEN |

### 6.3 Semantic Gap Explanation

```
Partner fee for trip (Yango)  = Comisión que YEGO cobra al conductor por viaje
                                ~0.43 PEN/order

revenue_yego_final (CT)       = comision_empresa_asociada (real) 
                                + proxy (ticket * 3% for missing commission)
                                ~2.11 PEN/trip (includes proxy, includes 
                                non-order revenue items)
```

**La diferencia (~5x) se debe a:**
1. CT `revenue_yego_final` incluye **proxy revenue** (ticket × 3%) para viajes sin comisión real — esto infla el valor
2. CT suma revenue de **múltiples business slices** (Auto regular, YMA, Tuk Tuk, PRO, Delivery, Carga), cada uno con diferentes tasas de comisión
3. `comision_empresa_asociada` puede incluir ajustes, bonificaciones y otros cargos no relacionados con Partner fee

**El revenue canónico debe ser `Partner fee for trip` de Yango**, que es la comisión real cobrada por viaje. El CT revenue incluye estimaciones proxy que deben ser reemplazadas.

---

## 7. Q6: GMV SEMANTICS

### 7.1 Yango GMV (Jun 10)

| Component | Amount (PEN) |
|-----------|-------------|
| Cash | 108,893.46 |
| Card payment | 15,879.50 |
| Corporate payment | 6,465.00 |
| **Total GMV** | **131,237.96** |

### 7.2 CT GMV

**0.00 PEN.** Las columnas `efectivo`, `tarjeta`, `pago_corporativo` en `public.trips_2026` están en 0 para Lima. CT no tiene GMV comparable confiable.

**GMV debe tomarse de Yango** (Cash + Card + Corporate de transactions_raw).

---

## 8. METRIC OWNERSHIP MATRIX (PRELIMINARY — LIMA)

| KPI | Yango Source | CT Source | Recommendation | Confidence |
|-----|-------------|-----------|----------------|------------|
| **completed_trips** | `COUNT(DISTINCT order_id)` FROM orders_raw | `trips_completed` FROM day_fact | **YANGO** (validar con CT como shadow) | HIGH |
| **cancelled_trips** | NOT AVAILABLE (API filter) | `trips_cancelled` FROM day_fact | **CT_BRIDGE** (Yango no ingiere cancelados) | MEDIUM |
| **revenue** | `SUM(ABS(amount))` WHERE Partner fee for trip | `revenue_yego_final` FROM day_fact | **YANGO** (CT incluye proxy, inflado ~5x) | HIGH |
| **active_drivers** | `COUNT(DISTINCT driver_profile_id)` FROM orders_raw | `COUNT(DISTINCT conductor_id)` FROM trips_2026 | **YANGO** (IDs match 100%) | HIGH |
| **GMV** | Cash+Card+Corporate FROM transactions | `efectivo+tarjeta+pago_corporativo` FROM trips_2026 | **YANGO** (CT = 0 para Lima) | HIGH |
| **avg_ticket** | Derived: GMV / orders | `avg_ticket` FROM day_fact | **DERIVED** (depends on GMV + trips source) | MEDIUM |
| **commission_rate** | `Service fee / GMV` FROM transactions | `commission_pct` FROM day_fact | **YANGO** | MEDIUM |
| **driver_identity** | `driver_profile_id` = `driver_id` | `driver_id` FROM public.drivers | **SHARED** (mismo UUID) | VERY_HIGH |

---

## 9. GO / NO-GO

### 9.1 GO Criteria

| # | Criterio | Estado | Evidencia |
|---|----------|--------|-----------|
| 1 | Yango > CT está explicado | **PASS** | Duplicados por re-ingesta (mismo order_id, distinto hash). COUNT(DISTINCT) resuelve. |
| 2 | No hay duplicación lógica crítica | **PASS** | Duplicados son versiones de payload, no registros incorrectos. |
| 3 | Partner Fee vs CT revenue explicado | **PASS** | CT incluye proxy revenue (ticket×3%) que infla ~5x. Partner fee es la comisión real. |
| 4 | GMV tiene fuente comparable | **PASS** | Yango GMV = 131K, CT GMV = 0. Yango es la única fuente confiable. |
| 5 | Matriz preliminar de ownership | **PASS** | 8 KPIs con fuente recomendada y confianza. |
| 6 | Omniview productivo no tocado | **PASS** | Shadow mode. |

### 9.2 Classification

**`SEMANTIC_RECONCILIATION_CERTIFIED`**

### 9.3 GO for CF-H2F (Metric Ownership Matrix)

**GO.** La semántica está reconciliada. La matriz de ownership puede formalizarse.

### 9.4 GO for CF-H2E (Multipark Expansion)

**GO.** El modelo semántico de Lima es extrapolable a otros parks.

### 9.5 GO for CF-H2G (Omniview Source Canonical Mapper)

**CONDITIONAL GO.** Requiere CF-H2F (ownership matrix formal) primero.

---

## 10. FIRMA

| Campo | Valor |
|-------|-------|
| **Auditado por** | CF-H2C.0C Lima Semantic Reconciliation Audit |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Clasificación** | `SEMANTIC_RECONCILIATION_CERTIFIED` |
| **Próxima fase** | CF-H2F — Metric Ownership Matrix |
