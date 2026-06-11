# CF-H2C — BACKLOG: REVENUE RECOVERY & DUPLICATE AUDIT

> **Motor:** Control Foundation
> **Fecha:** 2026-06-11
> **Contexto:** CF-H2C.1 Driver Identity CERTIFIED. Lima orders coverage >=95% en días completos. Revenue y duplicates siguen pendientes.

---

## CF-H2C.0B — LIMA REVENUE RECOVERY

### Objetivo

Recuperar y validar transactions/revenue de Yango API para Lima park desde 2026-06-01 hasta fecha actual.

### Estado Actual

| Métrica | Valor |
|---------|-------|
| Transactions para Jun 5-11 | **0 rows** |
| Transactions para Jun 4 | 17,804 rows (discovery run) |
| Revenue Yango calculado (Jun 4) | 1,612.32 PEN |
| Revenue CT (Lima, query needs fix) | Pendiente (scope incorrecto) |
| Latencia transactions | ~6 días (último dato: Jun 4) |

### Tareas

1. Reingestar transactions Lima Jun 1 → fecha actual
   ```bash
   python -m scripts.cf_h2c0a_lima_reingest --endpoint transactions --date-from 2026-06-01 --date-to 2026-06-11 --skip-completed
   ```
   - page_size=1000, sin max_pages, cursor `data.get("cursor")`
   - Rate limit cooldown entre días
   
2. Validar Partner fee for trip
   - Revenue diario = SUM(ABS(amount)) WHERE category_name = 'Partner fee for trip'
   - Comparar contra CT revenue_yego_final para Lima park específicamente
   - Query corregida: filtrar day_fact por park_id o city='lima'
   
3. Validar GMV cash/card
   - GMV = SUM(amount) WHERE category_name IN ('Cash', 'Card payment')
   - Comparar contra CT gmv_passenger_paid
   
4. Calcular revenue delta diario
   - delta_pct = ABS(yango_rev - ct_rev) / ct_rev * 100
   - Status: PASS (<=5%), WARN (5-20%), FAIL (>20%)
   
5. Medir freshness
   - last_transaction_event_at
   - operational_delay_minutes

### GO Criteria

| # | Criterio | Threshold |
|---|----------|-----------|
| 1 | Transactions no en 0 para >=80% de días | >=80% |
| 2 | Revenue delta diario | <=5% (días completos) |
| 3 | Revenue delta agregado (30d) | <=3% |
| 4 | GMV coverage | >=95% |
| 5 | Freshness | <=24h delay |

### Bloquea

- CF-H2D (Near Real-Time Shadow Scheduler)
- CF-H2G (Omniview Source Canonical Mapper)

### Archivos Probables

- `backend/scripts/cf_h2c0a_lima_reingest.py` (ya existe, usar `--endpoint transactions`)
- `backend/scripts/cf_h2c0b_revenue_validate.py` (nuevo)
- `raw_yango.transactions_raw` (existente)
- `raw_yango.mv_revenue_day` (existente, requiere refresh)

### Estimación

- ~30-60s por día de transactions × 11 días = ~5-10 minutos
- API es rápida para transactions (~1-2s por página con page_size=1000)
- Bajo riesgo de rate limit

---

## CF-H2C.0C — LIMA DUPLICATE / OVERCOVERAGE AUDIT

### Objetivo

Explicar por qué Yango muestra más orders que CT en algunos días (Jun 9: 126.7%, Jun 10: 112.8%).

### Hipótesis

| # | Hipótesis | Probabilidad |
|---|-----------|-------------|
| H1 | Múltiples ingestion runs insertaron el mismo order_id con diferente raw_payload_hash (cambio de estado) | ALTA |
| H2 | CT sub-reporta por filtro de `condicion` más estricto | MEDIA |
| H3 | Yango API devuelve orders que CT no captura (diferente fuente) | MEDIA |
| H4 | Duplicados por re-ingesta sin UPSERT correcto | BAJA |
| H5 | Diferencia de timezone causa que orders de días adyacentes se cuenten en día equivocado | BAJA |

### Tareas

1. Auditar duplicados por order_id
   ```sql
   SELECT order_id, COUNT(*) AS versions, COUNT(DISTINCT raw_payload_hash) AS hashes
   FROM raw_yango.orders_raw
   WHERE park_id = '08e20910...' AND order_ended_at::date = '2026-06-10'
   GROUP BY order_id
   HAVING COUNT(*) > 1
   ORDER BY versions DESC;
   ```

2. Comparar order_id vs CT codigo_pedido
   ```sql
   SELECT COUNT(*) AS overlap
   FROM raw_yango.orders_raw y
   INNER JOIN public.trips_2026 t
     ON y.order_id = t.codigo_pedido
   WHERE y.park_id = '08e20910...' AND y.order_ended_at::date = '2026-06-10';
   ```

3. Verificar status distribuition de órdenes Yango
   - ¿Orders_raw tiene solo `complete` o también otros estados?
   - ¿CT `condicion = 'Completado'` es más restrictivo?

4. Verificar si hay orders Yango sin `condicion = 'Completado'` en CT
   - Orders Yango que existen en trips_2026 pero con condicion != 'Completado'

5. Cuantificar el exceso
   - orders_yango - orders_ct_matched = exceso real
   - Determinar si exceso son órdenes nuevas o duplicados

### GO Criteria

| # | Criterio |
|---|----------|
| 1 | Origen del exceso documentado y explicado |
| 2 | Duplicados cuantificados (si aplica) |
| 3 | Decisión: Yango es más completo que CT, o Yango tiene duplicados |
| 4 | Si Yango > CT y es legítimo → coverage se ajusta a min(100%, real) |

### Archivos Probables

- `backend/scripts/cf_h2c0c_duplicate_audit.py` (nuevo)

---

## BACKLOG ORDER (CF-H2C Series)

| Fase | Descripción | Estado | Bloquea |
|------|-------------|--------|---------|
| CF-H2C.1 | Driver Identity Foundation | **CERTIFIED** | — |
| CF-H2C.0B | Revenue Recovery | **IMMEDIATE** | CF-H2D, CF-H2G |
| CF-H2C.0C | Duplicate / Overcoverage Audit | **IMMEDIATE** | CF-H2F |
| CF-H2D | Near Real-Time Shadow Scheduler | BLOCKED | — |
| CF-H2E | Multipark Credential Expansion | BACKLOG | — |
| CF-H2F | Metric Ownership Matrix | BACKLOG | — |
| CF-H2G | Omniview Source Canonical Mapper | BACKLOG | — |
| CF-H2H | Omniview Source Promotion | BACKLOG | — |

---

## FIRMA

| Campo | Valor |
|-------|-------|
| **Creado por** | CF-H2C.1 Driver Identity Foundation |
| **Fecha** | 2026-06-11 |
| **Motor** | Control Foundation |
| **Próxima acción** | CF-H2C.0B Lima Revenue Recovery |
