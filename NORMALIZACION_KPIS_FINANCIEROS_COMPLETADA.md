# Normalización Definitiva de KPIs Financieros - COMPLETADA

**Fecha:** 2026-01-28  
**Estado:** ✅ COMPLETADO

## Objetivo

Normalizar DEFINITIVAMENTE los KPIs financieros del sistema usando SOLO datos reales cuando existan, y dejar proxy SOLO como fallback explícito en PLAN.

## Decisiones Canónicas Aplicadas

### REAL
1. ✅ **Revenue YEGO REAL** = `SUM(comision_empresa_asociada)` (normalizado con ABS)
2. ✅ **GMV** = `SUM(efectivo + tarjeta + pago_corporativo)`
3. ✅ **Take Rate REAL** = `revenue_yego_real / GMV`
4. ✅ **Margen unitario** = `revenue_yego_real / trips`
5. ✅ **PROHIBIDO proxy 3% en REAL**

### PLAN
1. ✅ **Revenue YEGO Plan**: usar `projected_revenue` explícito si existe, si no calcular con proxy 3%
2. ✅ **Take Rate Plan** = `revenue_yego_plan / GMV_estimado`
3. ✅ **Margen unitario Plan** = `revenue_yego_plan / projected_trips`
4. ✅ **is_estimated**: true si se usó proxy, false si viene del archivo
5. ✅ **JAMÁS inferir GMV como revenue**

## Cambios Implementados

### PASO 1: Vista Materializada REAL (Migración 011)

**Archivo:** `backend/alembic/versions/011_create_real_financials_monthly_view.py`

**Vista creada:** `ops.mv_real_financials_monthly`

**Campos canónicos:**
- `trips_real`
- `gmv_real`
- `revenue_yego_real`
- `take_rate_real`
- `margin_per_trip_real`

**Agrupación:**
- `(country, city, lob_base, segment, year, month)`

**Fuente:** `public.trips_all` con filtro `condicion = 'Completado'`

### PASO 2: Vista PLAN Ajustada (Migración 012)

**Archivo:** `backend/alembic/versions/012_add_plan_financials_canonical.py`

**Vista ajustada:** `ops.v_plan_trips_monthly_latest`

**Campos agregados:**
- `revenue_yego_plan`
- `take_rate_plan`
- `margin_per_trip_plan`
- `is_estimated`

**Lógica:**
- Si `projected_revenue` existe → usar directamente, `is_estimated = false`
- Si NO existe → calcular con proxy 3%, `is_estimated = true`

### PASO 3: Servicios de API Actualizados

**Archivos modificados:**
- `backend/app/services/plan_real_split_service.py`
  - `get_real_monthly()`: ahora usa `ops.mv_real_financials_monthly`
  - `get_plan_monthly()`: ahora expone `revenue_yego_plan`, `take_rate_plan`, `margin_per_trip_plan`, `is_estimated`

**Archivo nuevo:**
- `backend/app/services/financials_service.py`
  - `get_real_financials_monthly()`: servicio canónico para KPIs REAL
  - `get_plan_financials_monthly()`: servicio canónico para KPIs PLAN

### PASO 4: UI Actualizada

**Archivo modificado:**
- `frontend/src/components/KPICards.jsx`

**Cambios:**
- ✅ Eliminado: Profit Proxy 3% en Real (PROHIBIDO)
- ✅ Agregado: Revenue YEGO Real con badge "Real"
- ✅ Agregado: Revenue YEGO Plan con badge "Plan"
- ✅ Agregado: Margen por viaje (badge secundario)
- ✅ Agregado: Take Rate (badge secundario)
- ✅ Eliminado: Referencias a GMV como revenue
- ✅ Vista ALL: Revenue siempre por país (PE/CO)

### PASO 5: Validaciones Creadas

**Archivo:** `backend/scripts/sql/validate_financials_canonical.sql`

**Validaciones:**
- A) Enero 2026 PE: `SUM(revenue_yego_plan) ≈ 263,428.97`
- B) Real 2025: `revenue_yego_real = SUM(comision_empresa_asociada)`
- C) `take_rate_real` entre 2% y 6%
- D) No hay proxy 3% en REAL
- E) GMV no se usa como revenue
- F) Estructura de vista plan correcta

## Estructura de Datos Final

### REAL (ops.mv_real_financials_monthly)
```sql
SELECT 
    country,
    city,
    lob_base,
    segment,
    year,
    month,
    trips_real,
    gmv_real,
    revenue_yego_real,      -- SUM(comision_empresa_asociada)
    take_rate_real,          -- revenue_yego_real / gmv_real
    margin_per_trip_real     -- revenue_yego_real / trips_real
FROM ops.mv_real_financials_monthly
```

### PLAN (ops.v_plan_trips_monthly_latest)
```sql
SELECT 
    plan_version,
    country,
    city,
    lob_base,
    segment,
    month,
    projected_trips,
    projected_drivers,
    projected_ticket,
    projected_revenue,
    revenue_yego_plan,       -- projected_revenue o trips*ticket*0.03
    take_rate_plan,          -- revenue_yego_plan / GMV_estimado
    margin_per_trip_plan,    -- revenue_yego_plan / projected_trips
    is_estimated             -- true si proxy, false si explícito
FROM ops.v_plan_trips_monthly_latest
```

## Endpoints API Actualizados

### REAL
- `GET /ops/real/monthly`
  - Retorna: `trips_real_completed`, `revenue_real_proxy` (ahora = revenue_yego_real), `take_rate_real`, `margin_per_trip_real`

### PLAN
- `GET /ops/plan/monthly`
  - Retorna: `projected_trips`, `projected_revenue` (ahora = revenue_yego_plan), `take_rate_plan`, `margin_per_trip_plan`, `is_estimated`

## Ejecución

### 1. Aplicar Migraciones
```bash
cd backend
alembic upgrade head
```

### 2. Refrescar Vistas
```sql
REFRESH MATERIALIZED VIEW ops.mv_real_financials_monthly;
```

### 3. Ejecutar Validaciones
```bash
cd backend/scripts
psql -d yego_integral -f sql/validate_financials_canonical.sql
```

### 4. Verificar UI
- Abrir `http://localhost:5173`
- Verificar que los KPIs muestren:
  - Revenue YEGO Real (badge "Real")
  - Revenue YEGO Plan (badge "Plan")
  - Margen por viaje
  - Take Rate
  - NO hay Profit Proxy en Real

## Reglas Aplicadas

### ✅ PROHIBIDO en REAL
- ❌ Proxy 3%
- ❌ GMV como revenue
- ❌ Cálculos estimados

### ✅ PERMITIDO en PLAN
- ✅ Proxy 3% cuando no hay revenue explícito
- ✅ Siempre etiquetado como "estimado" (`is_estimated = true`)

### ✅ UI
- ✅ Revenue siempre por país cuando `country = ALL`
- ✅ Etiquetas claras: "Real" vs "Plan"
- ✅ Badges secundarios: Margen/viaje, Take Rate
- ✅ Eliminado: Ticket promedio monetizado, Revenue basado en GMV

## Estado Final

- ✅ Vista `ops.mv_real_financials_monthly` creada y refrescada
- ✅ Vista `ops.v_plan_trips_monthly_latest` ajustada
- ✅ API alineada con campos canónicos
- ✅ UI sin GMV fantasma
- ✅ Proxy confinado a PLAN con flag explícito
- ✅ Validaciones creadas y ejecutables

## Próximos Pasos

1. Ejecutar migraciones en producción
2. Refrescar vistas materializadas
3. Ejecutar validaciones
4. Verificar que los datos coincidan con expectativas
5. Monitorear que no haya regresiones

## Notas Importantes

- **Backward Compatibility**: `revenue_real_proxy` sigue existiendo pero ahora mapea a `revenue_yego_real`
- **Trazabilidad**: Todo viene de `public.trips_all` con filtro `condicion = 'Completado'`
- **Performance**: Vistas materializadas con índices optimizados
- **Validación**: Queries de validación ejecutables en cualquier momento
