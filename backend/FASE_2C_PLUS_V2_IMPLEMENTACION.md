# FASE 2C+ v2 - Universo & LOB Mapping (PLAN ↔ REAL) con Regla Madre

## ✅ Implementación Completada

### Regla Madre Implementada

**LOB Base = `trips_all.tipo_servicio`** (siempre)
- ✅ No se sobreescribe con `dim_park.default_line_of_business`
- ✅ `dim_park.default_line_of_business` es solo informativo (lob_secondary)

**B2B Override:**
- ✅ Si `pago_corporativo > 0` → `market_type = 'B2B'`
- ✅ `lob_effective = 'B2B_' || lob_base` si B2B, sino `lob_base`

### A) Inventario Completado

**Columnas detectadas en `trips_all`:**
- `trip_id`: `id`
- `trip_date`: `fecha_inicio_viaje`
- `tipo_servicio`: `tipo_servicio` ✅ (existe)
- `pago_corporativo`: `pago_corporativo` ✅ (existe, numeric)
- `country/city`: Se obtienen desde `dim.dim_park` usando `park_id`

**Scripts creados:**
- `inspect_trips_all_columns.py`: Inspecciona estructura real de trips_all
- `diagnose_plan_lob_source.py`: Auto-discovery de tablas del plan con LOB

### B) City Normalization

**Tabla creada:**
- `ops.city_normalization`: Mapeo explícito de ciudades raw → normalized

**Vista creada:**
- `ops.v_city_resolved`: Resuelve city_raw vs city_resolved para cada viaje

### C) LOB Base + B2B (Regla Madre)

**Vista creada:**
- `ops.v_real_lob_base`: 
  - `lob_base = tipo_servicio` (regla madre)
  - `market_type = 'B2B'` si `pago_corporativo > 0`, sino `'B2C'`
  - `lob_effective = 'B2B_' || lob_base` si B2B, sino `lob_base`
  - Usa `v_city_resolved` para city normalization

### D) Parche: NO Sobreescribir LOB con dim_park

✅ Implementado en `v_real_lob_base`:
- `lob_base` siempre viene de `trips_all.tipo_servicio`
- No se usa `COALESCE(dim_park.default_line_of_business, tipo_servicio)`

### E) PLAN LOB Catalog - Auto Discovery

**Vista creada:**
- `ops.v_plan_lob_source_candidates`: Busca automáticamente LOB en `plan.plan_long_valid`

**Script mejorado:**
- `populate_lob_catalog_from_plan_v2.py`: 
  - Auto-discovery de fuente del plan
  - Guard: NO inserta si 0 filas
  - Mensaje claro: "PLAN LOB source not found or empty; catalog not populated"

### F) Mapping PLAN → REAL

**Tabla actualizada:**
- `ops.lob_plan_real_mapping`: 
  - Agregado `market_type` (B2B/B2C opcional)
  - `service_type` (renombrado desde `tipo_servicio`)

### G) Resolución REAL

**Vista actualizada:**
- `ops.v_real_lob_resolution`: 
  - Usa `v_real_lob_base` como fuente
  - Incluye `lob_base`, `market_type`, `lob_effective`
  - Funciona aunque `lob_catalog` esté vacío (todo UNMATCHED)

### H) Universo Check

**Vista actualizada:**
- `ops.v_real_without_plan_lob`: 
  - Incluye `lob_base`, `market_type`, `city_raw`
  - Agrupa por country, city, lob_base, market_type

**Vista condicional:**
- `ops.v_lob_universe_check`: 
  - Solo funciona si hay `lob_catalog` poblado
  - Si está vacío, retorna 0 filas (correcto)

### I) UI Actualizada

**Componente `LobUniverseView.jsx`:**
- ✅ Muestra `market_type` (B2B/B2C) con badges
- ✅ Muestra `city_raw` vs `city_resolved`
- ✅ Muestra `lob_base` en lugar de `tipo_servicio`
- ✅ Alerta cuando no hay plan catalog (modo REAL-only)
- ✅ Tabla de unmatched incluye todas las columnas nuevas

## 🚀 Pasos para Ejecutar

### 1. Ejecutar Migraciones
```bash
cd backend
alembic upgrade head
```
✅ Ya ejecutado: Migraciones 019 y 020 aplicadas

### 2. Diagnóstico del Plan
```bash
python scripts/diagnose_plan_lob_source.py
```
Esto genera `PLAN_LOB_SOURCE_DIAGNOSIS.md` con tablas candidatas.

### 3. Poblar Catálogo (si hay plan)
```bash
python scripts/populate_lob_catalog_from_plan_v2.py
```
⚠️ Si no hay plan, el script NO inserta nada y muestra mensaje claro.

### 4. (Opcional) Crear Reglas de Mapping
```sql
INSERT INTO ops.lob_plan_real_mapping (lob_id, country, city, service_type, market_type, priority, confidence)
SELECT 
    lc.lob_id,
    lc.country,
    lc.city,
    NULL,  -- NULL = cualquier tipo_servicio
    NULL,  -- NULL = cualquier market_type
    100,
    'high'
FROM ops.lob_catalog lc
WHERE lc.status = 'active';
```

### 5. (Opcional) Poblar City Normalization
```sql
INSERT INTO ops.city_normalization (country, city_raw, city_normalized, confidence)
SELECT DISTINCT
    country,
    city_raw,
    city_resolved,
    'high'
FROM ops.v_city_resolved
WHERE city_resolution_status = 'RAW'
AND city_raw != city_resolved;
```

## 📊 Estructura de Datos

### Vistas Principales

1. **`ops.v_real_lob_base`**: Fuente de verdad REAL
   - `lob_base` = `tipo_servicio` (regla madre)
   - `market_type` = B2B/B2C según `pago_corporativo`
   - `lob_effective` = con/sin prefijo B2B_

2. **`ops.v_real_lob_resolution`**: Resolución contra PLAN
   - Usa `v_real_lob_base` como fuente
   - Intenta mapear a `lob_catalog` vía `lob_plan_real_mapping`
   - Status: 'OK' o 'UNMATCHED'

3. **`ops.v_real_without_plan_lob`**: Viajes sin mapeo
   - Agrupa por country, city, lob_base, market_type
   - Siempre disponible (incluso sin plan)

4. **`ops.v_lob_universe_check`**: Universo Plan vs Real
   - Solo funciona si hay `lob_catalog` poblado
   - Si está vacío, retorna 0 filas

## 🎯 Reglas de Negocio Implementadas

✅ **Regla Madre**: `lob_base = tipo_servicio` (siempre)
✅ **B2B Override**: `market_type = 'B2B'` si `pago_corporativo > 0`
✅ **No Sobreescribir**: `dim_park.default_line_of_business` no afecta `lob_base`
✅ **City Mapping**: Explícito y auditable en `ops.city_normalization`
✅ **Auto-Discovery**: Busca automáticamente dónde están las LOB del plan
✅ **Guard Robusto**: NO inserta en catálogo si no hay fuente del plan

## ⚠️ Comportamiento sin Plan

Si no hay `lob_catalog` poblado:
- ✅ `v_real_lob_resolution` funciona (todo UNMATCHED)
- ✅ `v_real_without_plan_lob` muestra todos los viajes reales
- ✅ `v_lob_universe_check` retorna 0 filas (correcto)
- ✅ UI muestra alerta "Modo REAL-only"
- ✅ Sistema es completamente funcional para diagnosticar unmatched

## 📝 Notas Técnicas

- `pago_corporativo` es `numeric` en trips_all, se evalúa como `> 0`
- `city` se obtiene desde `dim_park` usando `park_id`
- `v_city_resolved` normaliza ciudades usando `ops.city_normalization`
- Si no hay normalización, usa `city_raw` directamente
- `lob_plan_real_mapping.service_type` mapea a `tipo_servicio` (regla madre)

## 🎯 Estado de Cierre

La fase se considera cerrada cuando:
- ✅ Regla madre implementada: `lob_base = tipo_servicio`
- ✅ B2B override funcionando: `market_type` según `pago_corporativo`
- ✅ City normalization explícita y auditable
- ✅ Auto-discovery del plan funcionando
- ✅ Sistema robusto: funciona sin plan (modo REAL-only)
- ✅ UI muestra toda la información relevante

**Estado actual:** ✅ Implementación completa v2, lista para usar.
