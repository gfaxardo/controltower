# OV2-B.1 — RAW YANGO LIVE INGESTION PILOT

> **Fase:** OV2-B.1 — Live Ingestion Pilot  
> **Fecha:** 2026-06-05  
> **Park:** YEGO Lima (`08e20910...`)  
> **Propósito:** Validar que la ingesta live de raw_yango funciona contra la API real de Yango, los datos se persisten correctamente y la cobertura/reconciliación es medible.

---

## 1. RESUMEN DE EJECUCIÓN

| Aspecto | Resultado |
|---------|-----------|
| **Fecha probada** | 2026-06-04 (1 día) |
| **Endpoints** | transactions, orders |
| **Registros insertados** | orders_raw: 1,500 | transactions_raw: 500 |
| **Errores** | 0 |
| **Rate limits (429)** | 0 |
| **Latencia** | ~1.7 min para 5 páginas transactions; orders tiempo similar |
| **Dry-run respetado** | Confirmado (`--confirm-live` gate) |
| **Driver_profiles** | No ingerido en este piloto |

---

## 2. ESTADO PREFLIGHT

### 2.1 Migración

```
alembic current: 179 → 180 → 181_raw_yango_landing → 182 → 183 → 184 (head)
```

Migración 181 (`raw_yango`) aplicada exitosamente. Schema `raw_yango` con 6 tablas creadas.

### 2.2 Credencial

Registro insertado en `raw_yango.api_park_credentials_registry`:
- `credential_id`: `yego_lima_park`
- `park_id`: `08e20910d81d42658d4334d3f6d10ac0`
- `fleet_name`: YEGO Lima
- `env_var_name`: `YANGO_LIMA`
- `api_base_url`: `https://fleet-api.yango.tech`
- `is_active`: true

API key NO almacenada — solo nombre de variable de entorno.

---

## 3. INGESTA LIVE

### 3.1 Transactions

```
python -m scripts.ingest_yango_raw_landing \
  --endpoint-group transactions --date-from 2026-06-04 --date-to 2026-06-04 \
  --max-pages 5 --confirm-live
```

| Métrica | Valor |
|---------|-------|
| Requests | 5 |
| Success | 5 |
| Errors | 0 |
| Rate limits (429) | 0 |
| Pages fetched | 5 |
| Records inserted | 500 |
| Elapsed | 1m 44.9s |

### 3.2 Orders

```
python -m scripts.ingest_yango_raw_landing \
  --endpoint-group orders --date-from 2026-06-04 --date-to 2026-06-04 \
  --max-pages 5 --confirm-live
```

| Métrica | Valor |
|---------|-------|
| Records inserted | 1,500 (3 páginas con datos, 5 max) |
| Errors | 0 |
| Rate limits | 0 |

---

## 4. VALIDACIÓN DE TABLAS RAW

### 4.1 Counts

| Tabla | Rows |
|-------|------|
| `orders_raw` | 1,500 |
| `transactions_raw` | 500 |
| `driver_profiles_raw` | 0 |
| `api_park_credentials_registry` | 1 |
| `ingestion_errors` | 0 |

### 4.2 Calidad de payload

| Check | orders_raw | transactions_raw |
|-------|-----------|-----------------|
| `raw_payload` no vacío | OK | OK |
| `raw_payload_hash` poblado | OK | OK |
| `api_run_id` poblado | OK | OK |
| `park_id` correcto | `08e20910...` | `08e20910...` |
| Fechas data correctas | `order_ended_at` = 2026-06-04 | `event_at` = 2026-06-04 |
| Duplicados | 0 | 0 |

### 4.3 Categorías de transacciones identificadas

Categorías encontradas en la muestra de 500 transacciones:
- `Partner fee for trip` — 110 txns
- `Service fee for trip`
- `Service fee, VAT`
- `Cash`
- `Card payment`
- `Cancel reservation fee`

---

## 5. COBERTURA

| Tabla | Rows | Distinct Days | Coverage |
|-------|------|---------------|----------|
| `orders_raw` | 1,500 | 1 | 100% (1/1) |
| `transactions_raw` | 500 | 1 | 100% (1/1) |
| `driver_profiles_raw` | 0 | 0 | 0% |

Revenue candidate (`Partner fee for trip`):
- Count: 110 transacciones
- SUM(ABS(amount)): 51.59 PEN

---

## 6. RECONCILIACIÓN

### 6.1 Estado

**No fue posible reconciliar para la misma fecha.** CT (`ops.real_business_slice_day_fact`) tiene datos hasta 2026-05-31. raw_yango tiene datos para 2026-06-04. No hay overlap de fechas.

### 6.2 Hallazgos del intento

- CT Perú/Lima: ~27K-28K trips/día (May 22-31)
- CT max date: 2026-05-31
- raw_yango orders en 2026-06-04: 1,500 (solo 3 páginas ingeridas de 5 configuradas)
- raw_yango Partner fee for trip: 51.59 PEN en 110 txns

### 6.3 Bugs encontrados en reconciliation script

1. **Date column mismatch**: Usaba `api_fetched_at::date` (fecha de ingesta) en vez de `order_ended_at::date`/`event_at::date` (fecha real del dato). **FIXED** en este piloto.
2. **TypeError date vs str**: `_build_reconciliation_daily` comparaba `datetime.date` con `str`. **FIXED** con `_norm_date()`.
3. **Country/city quoting**: Los valores en CT están almacenados con comillas literales (`'peru'`, `'lima'`), causando que `LOWER(TRIM(country)) = 'peru'` no matchee. **PENDIENTE FIX** — requiere `REPLACE(country, '''', '')` o limpieza de datos en CT.

---

## 7. PROBLEMAS ENCONTRADOS

| ID | Problema | Severidad | Estado |
|----|----------|-----------|--------|
| P1 | `api_ingestion_run` vacío — el script no trackea ingestion runs | MEDIUM | PENDIENTE |
| P2 | Reconciliation no usa fechas de datos reales (order_ended_at) | HIGH | FIXED |
| P3 | CT country/city con comillas incrustadas | MEDIUM | PENDIENTE |
| P4 | CT no tiene datos de Junio 2026 (max = May 31) | MEDIUM | NOTA |
| P5 | Coverage audit usa `api_fetched_at` (fecha de ingesta) | LOW | PENDIENTE |
| P6 | Orders ingestion timed out en primera ejecución (300s+) — requiere timeout mayor o optimización | LOW | NOTA |

---

## 8. DECISIÓN GO / NO-GO PARA OV2-B.2

### GO — con condiciones

**La ingesta live funciona.** La API de Yango es alcanzable, responde correctamente, las tablas raw se llenan sin errores ni duplicados, y la calidad de payload es buena.

**Condiciones antes de OV2-B.2 (Materialized Views):**

1. Ingerir al menos 7 días de datos (acumular cobertura)
2. Ingerir `driver_profiles` para completar las 3 tablas raw
3. Asegurar overlap de fechas con CT para reconciliación (ingerir Mayo 31 o esperar que CT tenga Junio)
4. Implementar `api_ingestion_run` tracking en el script de ingesta
5. Aumentar `--max-pages` para cobertura completa (1,500 orders de ~14K+ totales en Lima)
6. Evaluar latencia/throughput para ventana completa de 1 día con páginas ilimitadas

---

## 9. GOVERNANCE CHECK

| Regla | Estado |
|-------|--------|
| No modifica Omniview V1 | PASS |
| No modifica UI productiva | PASS |
| No reemplaza trips_2025/trips_2026 | PASS |
| No modifica serving actual | PASS |
| No backfill masivo (1 día, 5 páginas max) | PASS |
| No credenciales expuestas | PASS |
| Dry-run es default (`--confirm-live` gate) | PASS |
| Schema independiente (`raw_yango`) | PASS |

---

## 10. FIRMA

| Campo | Valor |
|-------|-------|
| **Ejecutado por** | OV2-B.1 Live Ingestion Pilot |
| **Fecha** | 2026-06-05 |
| **Próximo paso** | OV2-B.2 — acumular 7+ días, ingerir driver_profiles, reconciliar |
| **Estado** | `GO_CONDICIONAL` — live ingestion funciona, requiere más cobertura antes de MV |

---

## 11. ARCHIVOS GENERADOS

| Archivo | Ruta |
|---------|------|
| Coverage summary | `backend/exports/audits/yango_raw_landing/coverage_summary.md` |
| Coverage CSV | `backend/exports/audits/yango_raw_landing/coverage_by_park_day.csv` |
| Ingestion summary | `backend/exports/audits/yango_raw_landing/ingestion_summary.md` |
| Ingestion metrics | `backend/exports/audits/yango_raw_landing/ingestion_metrics.json` |
| Ingestion errors CSV | `backend/exports/audits/yango_raw_landing/ingestion_errors.csv` |
| Ingestion latency CSV | `backend/exports/audits/yango_raw_landing/ingestion_latency.csv` |
| Reconciliation summary | `backend/exports/audits/yango_raw_landing/reconciliation_summary.md` |
| Reconciliation CSV | `backend/exports/audits/yango_raw_landing/reconciliation_by_day.csv` |
