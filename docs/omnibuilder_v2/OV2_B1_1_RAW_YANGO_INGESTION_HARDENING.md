# OV2-B.1.1 — RAW YANGO INGESTION HARDENING

> **Fase:** OV2-B.1.1 — Ingestion Hardening  
> **Fecha:** 2026-06-05  
> **Park:** YEGO Lima (`08e20910...`)  
> **Propósito:** Endurecer la ingesta raw_yango corrigiendo tracking de runs, cobertura por fecha operativa y preparación para reconciliación real, antes de crear materialized views.

---

## 1. FIXES APLICADOS

### 1.1 api_ingestion_run tracking

**Problema:** El CLI script (`ingest_yango_raw_landing.py`) no registraba ejecuciones en `raw_yango.api_ingestion_run`.

**Fix:** Añadido llamado a `create_ingestion_run()` al inicio de cada ingesta real y `finish_ingestion_run()`/`fail_ingestion_run()` al finalizar, uno por endpoint group ejecutado.

**Estados:** `started` → `completed` / `failed`

**Verificación:** Driver profiles ingesta registrada como `ingest_20260605_064507_driver_profiles` con status=completed, 300 fetched/inserted, 0 errors.

### 1.2 operational_date column

**Problema:** Las tablas raw no tenían columna de fecha operativa. Coverage y reconciliation usaban `api_fetched_at` (fecha de ingesta) en vez de la fecha real del dato.

**Fix:** Migración 186 añade columna `operational_date DATE` a las 3 tablas raw:
- `orders_raw.operational_date`: derivado de `order_ended_at` o `order_created_at`
- `transactions_raw.operational_date`: derivado de `event_at`
- `driver_profiles_raw.operational_date`: derivado de `api_fetched_at::date` (temporal)

Índices agregados: `(park_id, operational_date)` en cada tabla.

**Backfill:** Datos existentes (1500 orders, 500 transactions) actualizados con valores derivados.

### 1.3 Coverage audit corregido

**Problema:** `audit_yango_raw_coverage.py` usaba `api_fetched_at::date` para medir cobertura, mostrando fechas de ingesta no operativas.

**Fix:** Cambiado a `operational_date` en:
- `_get_table_coverage()` — MIN/MAX/DISTINCT sobre `operational_date`
- `_get_daily_breakdown()` — GROUP BY `operational_date`

**Verificación post-backfill:**
| Table | Rows | Distinct Days |
|-------|------|---------------|
| orders_raw | 1,500 | 1 |
| transactions_raw | 500 | 1 |
| driver_profiles_raw | 300 | 1 |

### 1.4 Reconciliation normalization

**Problema:** CT (`ops.real_business_slice_day_fact`) almacena country/city con comillas incrustadas (`'peru'`, `'lima'`), causando que `LOWER(TRIM(country)) = 'peru'` no matchee.

**Fix:** Normalización en queries de reconciliation:
```sql
LOWER(TRIM(REPLACE(REPLACE(country, '''', ''), '\"', ''))) = %s
```
Elimina comillas simples y dobles antes de comparar.

---

## 2. MIGRACIONES

| Migración | Contenido |
|-----------|-----------|
| `181_raw_yango_landing` | Schema `raw_yango` + 6 tablas (ya aplicada en OV2-B.0) |
| `186_raw_yango_operational_date` | Añade `operational_date DATE` + índices |

Chain: `... → 184 → 185_yego_lima_impact_tracking → 186_raw_yango_operational_date (head)`

---

## 3. RUN TRACKING

Funcionando para nuevas ingestiones:

```
api_ingestion_run:
  ingest_20260605_064507_driver_profiles | ep=driver_profiles | st=completed | fetched=300 | ins=300 | err=0
```

Runs anteriores a este hardening no tienen registro (esperado).

---

## 4. COUNTS RAW_YANGO (post-hardening)

| Tabla | Rows | operational_date coverage |
|-------|------|--------------------------|
| orders_raw | 1,500 | 2026-06-04 |
| transactions_raw | 500 | 2026-06-04 |
| driver_profiles_raw | 300 | 2026-06-04 |
| api_ingestion_run | 1 | — |
| ingestion_errors | 0 | — |

Revenue candidate: 110 txns `Partner fee for trip`, 51.59 PEN.

---

## 5. DRIVER PROFILES

Ingesta exitosa: 300 perfiles en 3 páginas, 0 errores.  
Campos extraídos: `driver_profile_id`, `work_status`, `car_id`, `car_category`, `has_contract_issue`.  
Payload completo preservado en `raw_payload` JSONB.

---

## 6. RIESGOS PENDIENTES

| ID | Riesgo | Severidad | Estado |
|----|--------|-----------|--------|
| P1 | Reconciliation aún no probada con datos del mismo día (CT termina en May 31) | MEDIUM | PENDIENTE |
| P2 | Coverge script: missing_days puede reportar falsos si operational_date no coincide con el rango solicitado | LOW | MONITOR |
| P3 | Driver profiles operational_date = api_fetched_at (no fecha operativa real) | LOW | ACEPTABLE por ahora |
| P4 | Run tracking no se aplica a dry-runs (intencional) | LOW | BY DESIGN |

---

## 7. GOVERNANCE CHECK

| Regla | Estado |
|-------|--------|
| No modifica Omniview V1 | PASS |
| No modifica UI productiva | PASS |
| No reemplaza trips_2025/trips_2026 | PASS |
| No modifica serving actual | PASS |
| No backfill masivo | PASS |
| No credenciales expuestas | PASS |
| Dry-run default | PASS |
| Migración aditiva (ADD COLUMN IF NOT EXISTS) | PASS |
| Sin DROP de datos existentes | PASS |

---

## 8. GO / NO-GO PARA OV2-B.2

**GO.** Todos los fixes de hardening aplicados y verificados:
- Run tracking funcionando
- `operational_date` poblado en las 3 tablas
- Coverage audit usa fechas operativas reales
- Reconciliation normaliza country/city con comillas
- Driver profiles ingerido exitosamente
- Migración aplicada, índices creados

OV2-B.2 puede proceder con la creación de materialized views desde raw_yango.

---

## 9. FIRMA

| Campo | Valor |
|-------|-------|
| **Ejecutado por** | OV2-B.1.1 Ingestion Hardening |
| **Fecha** | 2026-06-05 |
| **Próximo paso** | OV2-B.2 — Materialized Views from raw_yango |
| **Estado** | `HARDENED` — ready for MV layer |
