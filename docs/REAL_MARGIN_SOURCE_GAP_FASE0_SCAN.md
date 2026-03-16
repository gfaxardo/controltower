# FASE 0 — Scan y mapeo: huecos de margen en fuente (módulo REAL)

**Objetivo:** Localizar dónde insertar la lógica de detección/alerta de "completados sin comisión/margen" y "cancelados con margen", sin implementar aún.

---

## A. Fuentes y capas de datos

### Tablas/vistas fuente de trips recientes

| Objeto | Tipo | Alcance | Columnas clave |
|--------|------|---------|----------------|
| `public.trips_2026` | Tabla | Viajes desde 2026 | `fecha_inicio_viaje`, `condicion`, `comision_empresa_asociada` |
| `public.trips_all` | Tabla | Viajes históricos (<2026) | Idem |
| `ops.v_trips_real_canon` | Vista | Unión trips_all + trips_2026 | `id`, `fecha_inicio_viaje`, `condicion`, `comision_empresa_asociada`, `source_table` |
| `ops.v_trips_real_canon_120d` | Vista | Mismo contrato, filtro `fecha_inicio_viaje >= current_date - 120` | Idem; **index-friendly** para ventana reciente |

Definición de la canónica 120d: `backend/alembic/versions/098_real_lob_root_cause_indexes_and_120d_views.py`. Incluye `comision_empresa_asociada` y `condicion` en el SELECT.

### Vista canónica de trips reales usada por REAL

- **Drill / day / week:** La cadena es `ops.v_real_trip_fact_v2` → `ops.mv_real_lob_hour_v2` → `ops.mv_real_lob_day_v2` → `ops.mv_real_lob_week_v3` → `real_drill_dim_fact` (populate desde day_v2/week_v3).
- **v_real_trip_fact_v2** (099): lee de `ops.v_trips_real_canon_120d`; expone `comision_empresa_asociada` como margen en la MV; `condicion` se normaliza a `trip_outcome_norm` ('completed' / 'cancelled').
- **Dónde vive margen/comisión en fuente:** En la **fuente raw** está en `comision_empresa_asociada` (trips_2026, trips_all, y por tanto en v_trips_real_canon y v_trips_real_canon_120d). En v_real_trip_fact_v2 se usa el mismo campo; en day_v2/week_v2 es `SUM(margin_total)` con `margin_total = comision_empresa_asociada`.

### Cadena hourly-first hasta drill REAL

1. `ops.v_trips_real_canon_120d` (o v_trips_real_canon) → `ops.v_real_trip_fact_v2` (por viaje: margin_total = comision_empresa_asociada, trip_outcome_norm desde condicion).
2. `v_real_trip_fact_v2` → `ops.mv_real_lob_hour_v2` → `ops.mv_real_lob_day_v2` → `ops.mv_real_lob_week_v3`.
3. `populate_real_drill_from_hourly_chain`: lee day_v2 y week_v3, escribe `ops.real_drill_dim_fact` (trips, margin_total, cancelled_trips desde migración 103).

### Clasificación completed/cancelled en fuente

- **En fuente:** columna `condicion` en trips_2026/trips_all y en v_trips_real_canon / v_trips_real_canon_120d. Valores típicos: `'Completado'`, `'Cancelado'` (o variantes con ILIKE '%cancel%' en 099).
- **En v_real_trip_fact_v2:** `trip_outcome_norm`: 'completed' cuando `condicion = 'Completado'`, 'cancelled' cuando `condicion = 'Cancelado'` o ILIKE '%cancel%'.

**Conclusión A:** El **mejor punto para medir el hueco de margen en fuente** es sobre **ops.v_trips_real_canon_120d** (o v_trips_real_canon si se necesita ventana >120d): contar por `(fecha_inicio_viaje::date, país, LOB, park, tipo_servicio)` con:
- `condicion = 'Completado'` → completed_trips; con `comision_empresa_asociada IS NOT NULL` → completed_trips_with_margin; el resto completed_trips_without_margin.
- `condicion` cancelado → cancelled_trips; con `comision_empresa_asociada IS NOT NULL` → cancelled_trips_with_margin (anomalía secundaria).

Para dimensiones (país, LOB, park, tipo_servicio) hace falta join a parks y a la capa LOB (v_real_trip_fact_v2 o vista que ya tenga LOB/país). Por tanto el **cálculo más fiel a “fuente”** es a nivel **v_trips_real_canon_120d** con join mínimo a parks (país/ciudad); para LOB/tipo_servicio se puede usar **v_real_trip_fact_v2** agregado por día para no duplicar lógica.

---

## B. Alerting / diagnósticos existentes

### Scripts de auditoría / freshness / anomalías

| Script | Persistencia | Propósito |
|--------|--------------|-----------|
| `scripts.run_data_freshness_audit` | `ops.data_freshness_audit` | Lag de fechas: source_max_date, derived_max_date, status (OK, LAGGING, SOURCE_STALE, etc.). |
| `scripts.audit_control_tower` | `ops.data_integrity_audit` | Checks de integridad: trip loss, B2B, LOB mapping, duplicates, joins; columnas: timestamp, check_name, status, metric_value, details (text). |
| `scripts.audit_real_margin_and_coverage` | **No persiste** | Solo imprime evidencia: day_v2/week_v3/drill margin NULL, cancelaciones, duplicados. |

### Tablas donde se persisten hallazgos

| Tabla | Contrato | Uso posible para margen |
|-------|----------|--------------------------|
| `ops.data_freshness_audit` | dataset_name, source/derived max date, status, alert_reason, checked_at | Orientada a **fechas**; no a calidad de margen. No reutilizable para “% completados sin margen”. |
| `ops.data_integrity_audit` | id, timestamp, check_name, status, metric_value (numeric), details (text) | Se puede añadir check_name `real_margin_source_gap` y poner pct en metric_value, JSON en details. Contrato limitado (una fila por check por ejecución). |

Para cumplir con “alert_code, severity, detected_at, grain_date, dimensions, affected_trips, denominator_trips, pct, message, metadata” y breakdown por dimensión, lo más limpio es una **tabla dedicada** de hallazgos de calidad de margen, p. ej. `ops.real_margin_quality_audit` o `ops.data_quality_findings` con tipo `REAL_MARGIN_SOURCE_GAP_*`. Así se evita sobrecargar `details` y se permite consultar por fecha/dimensión.

### Endpoints backend para diagnósticos

| Endpoint | Servicio | Uso |
|----------|----------|-----|
| `GET /ops/data-freshness` | data_freshness_service | Última auditoría por dataset (fechas, status). |
| `GET /ops/data-freshness/global` | get_freshness_global_status | Estado global para banner (fresca/atrasada/falta data). |
| `GET /ops/data-pipeline-health` | get_freshness_audit | Tabla expandida para “Ver salud del pipeline”. |
| `GET /ops/integrity-report` | data_integrity_service | Reporte de integridad (checks OK/WARNING/CRITICAL). |
| `POST /ops/data-freshness/run` | run_data_freshness_audit | Ejecuta freshness y escribe en data_freshness_audit. |
| `POST /ops/integrity-audit/run` | audit_control_tower | Ejecuta integridad y escribe en data_integrity_audit. |

No existe hoy un endpoint específico de “calidad de margen REAL” ni de “hueco de margen en fuente”.

### Componentes frontend donde ya hay alertas / banners

- **GlobalFreshnessBanner.jsx:** usa `getDataFreshnessGlobal({ group: 'operational' })` cuando la pestaña es Real; muestra estado (fresca, atrasada, falta data) y, al expandir, tabla de datasets con status/alert_reason. No muestra nada de margen.
- **SystemHealthView / Diagnósticos:** integridad, MVs, ingestión; no hay card de “cobertura de margen”.
- **RealLOBView / RealLOBDrillView:** no muestran banner de calidad de margen ni cobertura incompleta.

**Conclusión B:** Reutilizar el **patrón** de freshness (script que escribe en tabla de auditoría + endpoint que lee + banner/card en UI). Para persistencia, o bien extender `data_integrity_audit` con un check y JSON en details, o crear **ops.real_margin_quality_audit** (recomendado para trazabilidad y consultas por dimensión/fecha).

---

## C. UI / Frontend

### Pestañas REAL y Diagnósticos

- **App.jsx:** Tab “Real” → `RealLOBView` (Drill, Diario). Banner superior: `GlobalFreshnessBanner` (siempre visible; con `activeTab === 'real'` se pasa group `operational`).
- **Diagnósticos:** `SystemHealthView`: integridad, pipeline (freshness), ingestión. No hay sección “Calidad de margen REAL”.

### Dónde mostrar alertas de calidad de fuente

- **Opción 1 (recomendada):** En la pestaña **Real**, debajo o junto al `GlobalFreshnessBanner`, una **card o segunda línea** “Calidad de margen” cuando `activeTab === 'real'`: estado OK / Warning / Critical, “Cobertura de margen en completados: XX.X%”, cantidad afectada, rango temporal; y si hay hueco, advertencia de que margen/WoW puede ser incompleto. Anomalía secundaria (cancelados con margen) en bloque aparte.
- **Opción 2:** Incluir el estado de margen **dentro** del mismo `GlobalFreshnessBanner` cuando la pestaña es Real (extender payload de `getDataFreshnessGlobal` o llamar un nuevo endpoint de margen y mostrar una línea extra). Menos invasivo pero el banner puede volverse denso.
- **Diagnósticos:** Añadir en **SystemHealthView** una fila o card “REAL – Cobertura de margen” que consuma el mismo endpoint y muestre resumen + enlace a detalle.

**Conclusión C:** Mejor lugar para **visibilidad inmediata** es la **pestaña Real**: card/banner de “Calidad de margen” (o extensión del banner existente). Diagnósticos como segundo lugar para detalle/auditoría.

---

## D. Resultado del scan – Resumen y propuesta mínima

### 1. Mejor punto de cálculo de la anomalía

- **Fuente de verdad para conteos:** `ops.v_trips_real_canon_120d` (ventana 120d) o `ops.v_trips_real_canon` para 60/90 días.
- **Reglas:**  
  - Completado: `condicion = 'Completado'`.  
  - Con margen: `comision_empresa_asociada IS NOT NULL` (y opcionalmente `!= 0` si se define así).  
  - Anomalía principal: completados con `comision_empresa_asociada IS NULL`.  
  - Anomalía secundaria: cancelados (`condicion = 'Cancelado'` o ILIKE '%cancel%') con `comision_empresa_asociada IS NOT NULL`.
- Para **dimensiones** (país, LOB, park, tipo_servicio): calcular sobre **v_real_trip_fact_v2** agregado por día (tiene país, LOB, park, tipo_servicio_norm) filtrando por `trip_outcome_norm` y por margen NULL/no NULL, o hacer join de v_trips_real_canon_120d con parks y con capa LOB. Recomendación: usar **v_real_trip_fact_v2** para consistencia con el resto del módulo REAL y para tener LOB/país/park sin duplicar lógica.

### 2. Mejor lugar para persistir

- **Nueva tabla** `ops.real_margin_quality_audit` (o `ops.data_quality_findings` con tipo de hallazgo) con: alert_code, severity, detected_at, grain_date o date_range, dimensions (país, LOB, park, tipo_servicio), affected_trips, denominator_trips, pct, message_humano_legible, metadata JSON. Permite deduplicación por (alert_code, grain_date, dimensiones) y consultas por severidad/fecha.
- **Alternativa:** usar `ops.data_integrity_audit` con check_name `real_margin_source_gap` / `real_cancelled_with_margin`, metric_value = pct, details = JSON con el resto. Más limitado para múltiples filas por dimensión.

### 3. Mejor punto para exponer en API

- **Nuevo endpoint** `GET /ops/real/margin-quality` (o extender `GET /ops/data-freshness/global` con un bloque `margin_quality` cuando group=operational) que devuelva: resumen (severidad vigente, completed_without_margin_pct, margin_coverage_pct, cancelled_with_margin_pct), flags (has_margin_source_gap, margin_coverage_incomplete, has_cancelled_with_margin_issue), métricas recientes y últimos hallazgos desde `ops.real_margin_quality_audit`. Mantener contrato estable y no romper consumers actuales de data-freshness.

### 4. Mejor punto para mostrar en UI

- **Pestaña Real:** Card o bloque “Calidad de margen” visible bajo el banner de frescura (o integrado en el mismo banner cuando activeTab === 'real'): estado OK / Warning / Critical, “Cobertura de margen en completados: XX.X%”, cantidad afectada, rango temporal, mensaje operativo. Si hay hueco: advertencia de que margen/WoW puede ser incompleto. Anomalía secundaria (cancelados con margen) en sección separada.
- **Diagnósticos (System Health):** Card o fila “REAL – Cobertura de margen” con el mismo resumen y enlace a detalle si se implementa una vista de detalle.

### 5. Propuesta mínima de implementación (sin romper nada)

1. **FASE 1:** Definir métricas y severidad de forma canónica (documento o constante en código).  
2. **FASE 2:** Crear queries SQL de diagnóstico (diario 60/90d, por dimensión, top combinaciones) y script `audit_real_margin_source_gaps` que ejecute las queries, imprima resumen y devuelva códigos/severidad; opcionalmente escribir en una tabla de auditoría (si ya existe una reutilizable, usarla; si no, crear `ops.real_margin_quality_audit` en FASE 3).  
3. **FASE 3:** Crear tabla de persistencia de hallazgos (o reutilizar data_integrity_audit con contrato definido); el script debe persistir hallazgos con deduplicación razonable.  
4. **FASE 4:** Endpoint `GET /ops/real/margin-quality` (o extensión de data-freshness/global para Real) con flags y métricas; sin romper contratos existentes.  
5. **FASE 5:** En la pestaña Real, mostrar card/banner de calidad de margen consumiendo el nuevo endpoint; no maquillar números ni inventar margen.  
6. **FASE 6–7:** Badges de cobertura incompleta en vistas REAL afectadas; integración en job de auditoría existente (run_pipeline_refresh_and_audit o run_data_freshness_audit).  
8. **FASE 8–9:** Tests y documentación técnica con checklist de validación manual.

**No implementar** hasta cerrar este scan y validar con stakeholders que el punto de cálculo (v_trips_real_canon_120d / v_real_trip_fact_v2) y la ubicación de la card en la pestaña Real son los acordados.
