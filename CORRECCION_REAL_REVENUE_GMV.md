# CORRECCIÓN: Revenue Real NO es GMV

## ✅ CAMBIOS APLICADOS

### PASO 1: Perfilamiento de Signos
- **Resultado**: Comisiones vienen **NEGATIVAS** (25% de registros)
- **Normalización**: Usar `ABS()` para convertir a positivo
  - `revenue_yego_trip = ABS(COALESCE(comision_empresa_asociada,0))`
  - `revenue_yango_trip = ABS(COALESCE(comision_servicio,0))`

### PASO 2: Componentes GMV Definidos
- **GMV Base (passenger_paid)**: `efectivo + tarjeta + pago_corporativo`
- **GMV Extras**: `propina + otros_pagos + bonificaciones + promocion`
- **GMV Total**: `passenger_paid + extras`

### PASO 3: Migración 010 Aplicada
- **Archivo**: `backend/alembic/versions/010_fix_real_revenue_gmv_take_rate.py`
- **Cambios en MV**:
  - ✅ `revenue_yego_real` = `ABS(comision_empresa_asociada)` (Revenue real de YEGO)
  - ✅ `revenue_yango_real` = `ABS(comision_servicio)` (Revenue de YANGO)
  - ✅ `gmv_passenger_paid` (GMV base)
  - ✅ `gmv_extras` (extras)
  - ✅ `gmv_total` (total)
  - ✅ `take_rate_yego` = `revenue_yego_real / gmv_passenger_paid`
  - ✅ `take_rate_total` = `(revenue_yego + revenue_yango) / gmv_passenger_paid`
  - ✅ `revenue_real_proxy` = `revenue_yego_real` (backward compatibility)

### PASO 4: Backward Compatibility
- ✅ `revenue_real_proxy` ahora mapea a `revenue_yego_real` (no rompe UI existente)
- ✅ Mantiene `avg_ticket_real` (precio_yango_pro) para compatibilidad

### PASO 5: Validación Exitosa

**Datos Real 2025:**
- GMV Base total: **8,048,618,195**
- Revenue YEGO total: **254,354,642**
- Ratio Revenue/GMV: **3.16%** ✅
- Take rate YEGO promedio: **0.0318** (3.18%) ✅
- Take rate YEGO rango: **0.00% - 9.62%**

**Validaciones:**
- ✅ Revenue YEGO < GMV Base (CORRECTO)
- ✅ Take rate YEGO razonable (3.18%)

## 📊 ESTRUCTURA DE CAMPOS EN MV

```sql
-- Dimensiones
month, country, city, city_norm, park_id, lob_base, segment

-- Métricas base
trips_real_completed
active_drivers_real
avg_ticket_real

-- GMV (trazable)
gmv_passenger_paid     -- efectivo + tarjeta + pago_corporativo
gmv_extras             -- propina + otros_pagos + bonificaciones + promocion
gmv_total              -- passenger_paid + extras

-- Revenue (real)
revenue_yego_real      -- ABS(comision_empresa_asociada) - NUESTRO REVENUE
revenue_yango_real     -- ABS(comision_servicio)
revenue_real_proxy     -- BACKWARD COMPAT: mapea a revenue_yego_real

-- Indicadores derivados
trips_per_driver
take_rate_yego         -- revenue_yego_real / gmv_passenger_paid
take_rate_total        -- (revenue_yego + revenue_yango) / gmv_passenger_paid

-- Proxies económicos (FASE 2A)
commission_rate_default
profit_proxy
profit_per_trip_proxy
```

## 🔧 TRAZABILIDAD

Todo viene de `public.trips_all`:
- Filtro: `condicion = 'Completado'`
- Agrupación: `(month, park_id, tipo_servicio, segment)`
- Join: `LEFT JOIN dim.dim_park` para country/city/lob

## 📝 NOTAS IMPORTANTES

1. **Revenue YEGO NO es GMV**: Ahora correctamente usa `comision_empresa_asociada`
2. **GMV es explícito**: Separado en `passenger_paid`, `extras`, y `total`
3. **Take rates calculados**: Contra GMV base (no incluye propinas por defecto)
4. **Backward compatible**: `revenue_real_proxy` sigue existiendo pero mapea correctamente

## ✅ ESTADO FINAL

- ✅ Migración 010 aplicada
- ✅ MV refrescada con datos correctos
- ✅ Validación numérica exitosa
- ✅ Backward compatibility mantenida
- ✅ Plan no afectado
- ✅ Trazabilidad completa desde trips_all
