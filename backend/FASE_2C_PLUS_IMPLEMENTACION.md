# FASE 2C+ - Universo & LOB Mapping (PLAN → REAL)

## ✅ Implementación Completada

### 1. Base de Datos

#### Migración Alembic: `019_create_phase2c_lob_universe_mapping.py`

**Tablas creadas:**
- `ops.lob_catalog`: Catálogo canónico de LOB del PLAN
  - `lob_id`, `lob_name`, `country`, `city`, `description`, `status`, `source`, `created_at`
  - Constraint único: `(lob_name, country, city)`
  - Solo LOB provenientes del PLAN (no se crean desde trips_all)

- `ops.lob_plan_real_mapping`: Reglas explícitas de mapping PLAN → REAL
  - `mapping_id`, `lob_id` (FK), `country`, `city`, `tipo_servicio`
  - Campos opcionales: `product_type`, `vehicle_type`, `fleet_flag`, `tariff_class`
  - `priority`, `confidence`, `valid_from`, `valid_to`, `notes`
  - NULL en cualquier campo = "cualquier valor"

**Vistas creadas:**
- `ops.v_real_lob_resolution`: Resuelve cada viaje real contra el PLAN
  - Usa LATERAL JOIN con prioridad
  - Status: 'OK' o 'UNMATCHED'
  - Solo viajes completados (`condicion = 'Completado'`)

- `ops.v_lob_universe_check`: Universo LOB - PLAN vs REAL
  - Muestra qué LOB del plan tienen viajes reales
  - Status: 'OK' o 'PLAN_ONLY'
  - Incluye conteo de viajes reales por LOB

- `ops.v_real_without_plan_lob`: Viajes reales sin mapeo
  - Agrupa por país, ciudad, tipo_servicio
  - Incluye fechas de primer y último viaje

- `ops.v_lob_mapping_quality_checks`: Métricas de calidad
  - % viajes UNMATCHED
  - Total LOB planificadas
  - LOB con/sin real
  - Reglas de mapping sin uso

- `ops.v_lob_unmatched_by_location`: Viajes unmatched por ubicación
  - Agrupa por país/ciudad
  - % del total de viajes de la ubicación

### 2. Scripts

**`backend/scripts/populate_lob_catalog_from_plan.py`**
- Extrae LOB únicas desde `plan.plan_long_valid`
- Pobla `ops.lob_catalog` automáticamente
- Maneja duplicados con `ON CONFLICT`
- ⚠️ Solo inserta LOB del PLAN, nunca desde trips_all

### 3. Backend

#### Repositorio: `backend/app/adapters/lob_universe_repo.py`
- `get_lob_universe_check()`: Obtiene universo LOB
- `get_real_without_plan_lob()`: Viajes sin mapeo
- `get_lob_mapping_quality_checks()`: Métricas de calidad
- `get_unmatched_by_location()`: Unmatched por ubicación
- `get_lob_catalog()`: Catálogo de LOB

#### Servicio: `backend/app/services/lob_universe_service.py`
- `get_universe_lob_summary()`: Resumen con KPIs
- `get_unmatched_trips_summary()`: Resumen de unmatched

#### Router: `backend/app/routers/phase2c.py` (endpoints agregados)
- `GET /phase2c/lob-universe`: Universo LOB con KPIs
- `GET /phase2c/lob-universe/unmatched`: Viajes sin mapeo

### 4. Frontend

#### Componente: `frontend/src/components/LobUniverseView.jsx`
- Dos secciones: "Universo LOB" y "Viajes sin Mapeo"
- KPIs en cards: Total LOB, LOB con/sin real, % UNMATCHED
- Tablas con filtros por país/ciudad/LOB
- Badges de status (OK / PLAN_ONLY)

#### Integración: `frontend/src/App.jsx`
- Nueva pestaña "Universo & LOB"
- Integrada con sistema de filtros existente

#### API: `frontend/src/services/api.js`
- `getLobUniverse()`: Obtiene universo LOB
- `getUnmatchedTrips()`: Obtiene viajes unmatched

## 🚀 Pasos para Ejecutar

### 1. Ejecutar Migración
```bash
cd backend
alembic upgrade head
```

### 2. Poblar Catálogo de LOB
```bash
cd backend
python scripts/populate_lob_catalog_from_plan.py
```

### 3. (Opcional) Crear Reglas de Mapping
Por ahora, el sistema funciona sin reglas explícitas (solo con el catálogo).
Para crear reglas de mapping, insertar manualmente en `ops.lob_plan_real_mapping`:

```sql
INSERT INTO ops.lob_plan_real_mapping (lob_id, country, city, tipo_servicio, priority, confidence)
SELECT 
    lc.lob_id,
    lc.country,
    lc.city,
    NULL,  -- NULL = cualquier tipo_servicio
    100,   -- Prioridad (menor = mayor prioridad)
    'high' -- Confianza
FROM ops.lob_catalog lc
WHERE lc.status = 'active';
```

### 4. Verificar en UI
1. Iniciar backend: `uvicorn app.main:app --reload`
2. Iniciar frontend: `npm run dev`
3. Ir a pestaña "Universo & LOB"
4. Revisar KPIs y tablas

## 📊 Qué Responde el Sistema

### ✅ Preguntas Respondidas

1. **Qué LOB del PLAN existen**
   - Vista: `ops.lob_catalog`
   - UI: Tabla "Universo LOB"

2. **Qué LOB del PLAN generan viajes reales**
   - Vista: `ops.v_lob_universe_check` (coverage_status = 'OK')
   - UI: Columna "Status" = OK

3. **Qué viajes reales NO encajan en ninguna LOB del plan**
   - Vista: `ops.v_real_without_plan_lob`
   - UI: Sección "Viajes sin Mapeo"

4. **Dónde hay mismatch estructural**
   - Vista: `ops.v_lob_unmatched_by_location`
   - UI: Tabla "Viajes UNMATCHED por Ubicación"

### 📈 KPIs Disponibles

- Total LOB planificadas
- LOB con real (y %)
- LOB sin real
- % viajes UNMATCHED
- Total viajes unmatched
- Reglas de mapping sin uso

## ⚠️ Principios Respetados

✅ **No crear nuevas LOB desde el real**
- El catálogo solo se puebla desde `plan.plan_long_valid`

✅ **No inferir LOB implícitas**
- Todo mapping es explícito en `ops.lob_plan_real_mapping`

✅ **Reglas versionables y auditable**
- Tabla de mapping con `valid_from`, `valid_to`, `created_at`

✅ **Mismatch visible**
- Vistas dedicadas para unmatched
- KPIs de calidad siempre visibles

✅ **No alimenta weekly, alertas ni forecast**
- Sistema independiente, solo visibilidad

## 🔍 Controles de Calidad

Las vistas de calidad responden:
- % de viajes UNMATCHED
- Viajes UNMATCHED por país/ciudad
- LOB del plan con 0 viajes
- Reglas de mapping que nunca matchean

Todo visible en la UI y accesible vía API.

## 📝 Notas Técnicas

- La vista `ops.v_real_lob_resolution` usa `LATERAL JOIN` para aplicar reglas con prioridad
- Si no hay match → `UNMATCHED` (nada se fuerza)
- Solo viajes completados se consideran (`condicion = 'Completado'`)
- El mapping usa columnas reales de `trips_all`: `tipo_servicio`, `park_id` (para country/city desde `dim_park`)

## 🎯 Estado de Cierre

La fase se considera cerrada cuando:
- ✅ Cada LOB del PLAN tiene visibilidad clara vs REAL
- ✅ Todo viaje real está mapeado o explícitamente marcado como UNMATCHED
- ✅ El mismatch es visible y discutible
- ✅ No hay lógica implícita

**Estado actual:** ✅ Implementación completa, lista para ejecutar migración y poblar catálogo.
