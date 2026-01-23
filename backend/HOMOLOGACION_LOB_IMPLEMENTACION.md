# Homologación LOB (REAL tipo_servicio ↔ PLAN CSV) - Implementación

## ✅ Implementación Completada

### A) REAL UNIVERSE (tipo_servicio)

**Vista creada:**
- `ops.v_real_tipo_servicio_universe`: Agrupa viajes reales por country, city, tipo_servicio
  - Muestra: trips_count, first_seen_date, last_seen_date

### B) PLAN STAGING (CSV)

**Schema y tabla creados:**
- `staging.plan_projection_raw`: Tabla para cargar CSV tal cual (sin transformar)
  - Columnas: country, city, lob_name, period_date, trips_plan, revenue_plan, raw_row (JSONB), loaded_at
  - `raw_row` guarda la fila completa para auditoría

**Vista creada:**
- `ops.v_plan_lob_universe_raw`: Agrega datos desde staging.plan_projection_raw
  - Agrupa por country, city, plan_lob_name (normalizado: TRIM(LOWER))
  - Muestra: trips_plan, revenue_plan, first_period, last_period

**Loader actualizado:**
- `save_plan_projection_raw()`: Nueva función en `plan_repo.py`
  - Mapea columnas del CSV a staging.plan_projection_raw
  - `period` (YYYY-MM) → `period_date`
  - `line_of_business` → `lob_name`
  - `metric` → `trips_plan` o `revenue_plan` según metric
  - Guarda fila completa en `raw_row` (JSONB)

**Router actualizado:**
- `upload_plan_simple`: Ahora también guarda en `staging.plan_projection_raw` automáticamente

### C) HOMOLOGATION TABLE (PUENTE)

**Tabla creada:**
- `ops.lob_homologation`: Diccionario auditable
  - `real_tipo_servicio` → `plan_lob_name`
  - Campos: country, city, confidence, notes, created_at, created_by
  - UNIQUE constraint en (country, city, real_tipo_servicio, plan_lob_name)

### D) SUGERENCIA AUTOMÁTICA (SIN AUTODECISIÓN)

**Vista creada:**
- `ops.v_lob_homologation_suggestions`: Sugerencias por similitud
  - Match exacto → confidence 'high'
  - Match por contains → confidence 'low'
  - Excluye ya homologadas
  - Ordena por confidence y trips_count

### E) REPORTES

**Vistas creadas:**
- `ops.v_real_lob_without_homologation`: LOB del REAL sin homologación
- `ops.v_plan_lob_without_homologation`: LOB del PLAN sin homologación

**Script creado:**
- `generate_lob_homologation_reports.py`: Genera reportes en consola
  - Muestra top 50 LOB REAL sin homologación
  - Muestra top 50 LOB PLAN sin homologación
  - Muestra top 30 sugerencias de homologación
  - Resumen con totales

### F) USO EN 2C+

**Script actualizado:**
- `populate_lob_catalog_from_plan_v3.py`: Pobla catálogo desde `ops.v_plan_lob_universe_raw`
  - NO desde real, solo desde plan CSV
  - Guard robusto: no inserta si 0 filas

**Vista actualizada:**
- `ops.v_real_lob_resolution`: Ahora usa homologación
  - Flujo: `real_tipo_servicio` → `lob_homologation` → `plan_lob_name` → `lob_catalog`
  - Nuevos campos: `homologated_plan_lob`, `homologation_id`, `homologation_confidence`
  - Nuevo status: `HOMOLOGATED_NO_MAPPING` (homologado pero sin mapping a catalog)

**Vista actualizada:**
- `ops.v_real_without_plan_lob`: Incluye información de homologación
  - `has_homologation_count`: Viajes con homologación
  - `no_homologation_count`: Viajes sin homologación

## 🚀 Flujo de Trabajo

### 1. Cargar Plan CSV
```bash
# Subir CSV desde UI o API
POST /plan/upload_simple
```
Esto automáticamente:
- Guarda en `plan.plan_long_raw` (formato long)
- Guarda en `staging.plan_projection_raw` (formato para homologación)
- Valida y guarda en `plan.plan_long_valid`

### 2. Poblar Catálogo desde Plan
```bash
cd backend
python scripts/populate_lob_catalog_from_plan_v3.py
```
Esto:
- Lee desde `ops.v_plan_lob_universe_raw`
- Inserta en `ops.lob_catalog` con source='plan_csv'

### 3. Generar Reportes de Homologación
```bash
python scripts/generate_lob_homologation_reports.py
```
Muestra:
- LOB REAL sin homologación
- LOB PLAN sin homologación
- Sugerencias automáticas

### 4. Crear Homologaciones (Manual)
```sql
-- Insertar homologación manual
INSERT INTO ops.lob_homologation (country, city, real_tipo_servicio, plan_lob_name, confidence, notes, created_by)
VALUES ('Peru', 'Lima', 'Taxi', 'taxi', 'high', 'Match exacto', 'gonzalo');

-- O desde sugerencias (revisar primero)
SELECT * FROM ops.v_lob_homologation_suggestions 
WHERE suggested_confidence = 'high' 
AND NOT already_homologated
LIMIT 10;
```

### 5. Verificar Resolución
```sql
-- Ver viajes resueltos
SELECT 
    resolution_status,
    COUNT(*) as trips,
    COUNT(DISTINCT trip_id) as distinct_trips
FROM ops.v_real_lob_resolution
GROUP BY resolution_status;

-- Ver viajes sin homologación
SELECT * FROM ops.v_real_lob_without_homologation
ORDER BY trips_count DESC
LIMIT 20;
```

## 📊 Estructura de Datos

### Flujo de Homologación

```
trips_all.tipo_servicio (REAL)
    ↓
ops.lob_homologation (PUENTE)
    ↓
plan_lob_name (PLAN)
    ↓
ops.lob_catalog.lob_name (CANON)
    ↓
ops.lob_plan_real_mapping (REGLAS)
    ↓
ops.v_real_lob_resolution (RESOLUCIÓN FINAL)
```

### Estados de Resolución

- `OK`: Homologado y mapeado correctamente
- `HOMOLOGATED_NO_MAPPING`: Homologado pero sin mapping a catalog
- `UNMATCHED`: Sin homologación

## 🎯 Reglas de Negocio

✅ **Plan Catalog**: Se puebla desde `ops.v_plan_lob_universe_raw` (CSV), NO desde real
✅ **Homologación**: Explícita y auditable en `ops.lob_homologation`
✅ **Sugerencias**: Solo sugerencias, NO auto-decisión (excepto matches exactos si se decide)
✅ **Casamiento Plan vs Real**: Vía homologación: `real_tipo_servicio` → `plan_lob_name` → `lob_catalog`

## ⚠️ Notas Importantes

1. **No Auto-Decisión**: Las sugerencias NO se insertan automáticamente (excepto matches exactos si se decide explícitamente)
2. **Auditoría**: `raw_row` en `staging.plan_projection_raw` guarda la fila completa del CSV
3. **Normalización**: `plan_lob_name` se normaliza con `TRIM(LOWER())` en la vista
4. **Confidence**: Homologaciones tienen confidence (high/medium/low) para tracking

## 📝 Estado de Cierre

La fase se considera cerrada cuando:
- ✅ Sistema de staging creado para CSV raw
- ✅ Homologación explícita y auditable
- ✅ Reportes para decisión manual
- ✅ Integración con Plan vs Real vía homologación
- ✅ Scripts de población y reportes funcionando

**Estado actual:** ✅ Implementación completa, lista para usar.
