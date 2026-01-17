# FASE 2A - CIERRE: Consolidación REAL Operativo

**Fecha de cierre:** 2026-01-27  
**Estado:** ✅ COMPLETADO

## Objetivo

Consolidar el agregado REAL mensual a partir de `public.trips_all`, dejando listo (pero no activado) el marco para economía avanzada en FASE 2B.

## Principios Aplicados

1. ✅ No romper nada existente
2. ✅ No introducir lógica económica compleja
3. ✅ Todo trazable, auditable y tolerante
4. ✅ Warnings nunca bloquean
5. ✅ Plan y Real NO se mezclan
6. ✅ Append-only y versionado se respetan

---

## Contrato Operativo REAL (Congelado)

### Fuente Canónica
- **Tabla:** `public.trips_all`
- **Filtro:** `condicion = 'Completado'`

### Campos Canónicos
- `trip_datetime`: `fecha_inicio_viaje`
- `driver_id`: `conductor_id`
- `trip_amount`: `precio_yango_pro`

### Segmentación
- **lob_base**: Resuelto desde `tipo_servicio` (mapeo vía `dim.dim_park.default_line_of_business`)
- **segment**: 
  - `b2b` si `pago_corporativo IS NOT NULL AND pago_corporativo > 0`
  - `b2c` en caso contrario

---

## Agregado REAL Mensual (ops.mv_real_trips_monthly)

### Grano
`(country, city, city_norm, lob_base, segment, month)`

### Clasificación de Métricas

#### 1. MÉTRICAS REAL (Canónicas)
Directamente desde `public.trips_all`:

- **`trips_real_completed`**: `COUNT(*)` de viajes completados
- **`active_drivers_real`**: `COUNT(DISTINCT conductor_id)` de conductores activos
- **`avg_ticket_real`**: `AVG(precio_yango_pro)` promedio de ticket
- **`revenue_real_proxy`**: `SUM(precio_yango_pro)` suma de revenue (proxy, no incluye comisiones reales)

> **Nota:** `revenue_real_proxy` es un proxy porque no incluye reglas de comisión reales. En FASE 2B se calculará `revenue_real` con reglas dinámicas.

#### 2. MÉTRICAS DERIVADAS (Calculadas)
Indicadores básicos derivados de métricas REAL:

- **`trips_per_driver`**: `trips_real_completed / NULLIF(active_drivers_real, 0)`
  - Productividad: viajes por conductor
  - **Validación:** Nunca genera división por cero (usa `NULLIF`)

#### 3. MÉTRICAS PROXY (Temporales - Placeholder FASE 2B)
Ganancia estimada simple con comisión fija:

- **`commission_rate_default`**: `0.03` (3% fijo)
  - **Temporal:** Será reemplazado por reglas dinámicas en FASE 2B
  - **Documentación:** Ver comentarios en MV indicando que es placeholder

- **`profit_proxy`**: `revenue_real_proxy * commission_rate_default`
  - Ganancia estimada simple
  - **Validación:** Puede ser `NULL` solo si `revenue_real_proxy` es `NULL`

- **`profit_per_trip_proxy`**: `profit_proxy / NULLIF(trips_real_completed, 0)`
  - Ganancia por viaje estimada
  - **Validación:** Nunca genera división por cero (usa `NULLIF`)

> **⚠️ IMPORTANTE:** Estas métricas PROXY son temporales y serán reemplazadas en FASE 2B con reglas reales de comisión desde `canon.commission_rules`.

---

## Validaciones Implementadas

### 1. División por Cero
- ✅ `trips_per_driver`: Usa `NULLIF(active_drivers_real, 0)`
- ✅ `profit_per_trip_proxy`: Usa `NULLIF(trips_real_completed, 0)`

### 2. NULL Safety
- ✅ `profit_proxy` puede ser `NULL` solo si `revenue_real_proxy` es `NULL`
- ✅ `avg_ticket_real` usa `FILTER (WHERE precio_yango_pro IS NOT NULL)`
- ✅ `revenue_real_proxy` usa `FILTER (WHERE precio_yango_pro IS NOT NULL)`

### 3. Tolerancia a Faltantes
- ✅ Warnings nunca bloquean
- ✅ Si falta plan → warning/info, no error
- ✅ Si falta real → warning/info, no error

---

## Función de Refresh

```sql
SELECT ops.refresh_real_trips_monthly();
```

**Comportamiento:**
- Intenta `REFRESH MATERIALIZED VIEW CONCURRENTLY` (requiere índice único)
- Si falla, usa `REFRESH MATERIALIZED VIEW` normal
- Tolerante a errores (no bloquea)

---

## Preparación para FASE 2B (NO ACTIVADA)

### Estructura Preparada (Comentada)

La migración `008_consolidate_real_monthly_phase2a` incluye DDL comentado para:

```sql
-- canon.commission_rules (estructura esperada)
-- - rule_id, country, city_norm, lob_base, segment
-- - effective_from, effective_to, commission_rate
-- - rule_type, created_at, updated_at
```

**Estado:** Solo documentación. NO se crea la tabla. NO se usa. NO afecta resultados actuales.

### Plan de Migración FASE 2B

1. Crear `canon.commission_rules` con reglas dinámicas
2. Modificar `ops.mv_real_trips_monthly` para JOIN con `canon.commission_rules`
3. Calcular `profit_real` usando reglas dinámicas
4. Deprecar `profit_proxy` y `commission_rate_default`
5. Mantener compatibilidad hacia atrás durante transición

---

## Migración Alembic

**Archivo:** `backend/alembic/versions/008_consolidate_real_monthly_phase2a.py`

**Ejecutar:**
```bash
cd backend
alembic upgrade head
```

**Verificar:**
```bash
alembic current
# Debe mostrar: 008_consolidate_real_monthly_phase2a
```

---

## Archivos Modificados

1. ✅ `backend/alembic/versions/008_consolidate_real_monthly_phase2a.py` (NUEVO)
   - Migración para consolidar REAL mensual con extensiones FASE 2A

2. ✅ `backend/FASE_2A_CIERRE.md` (NUEVO)
   - Documentación de cierre FASE 2A

3. ✅ `README.md` (ACTUALIZADO)
   - Sección FASE 2A con clasificación de métricas

---

## Estado del Sistema

**READY_WITH_WARNINGS** ✅

- ✅ Sistema funcional
- ✅ Métricas REAL consolidadas
- ✅ Métricas DERIVADAS calculadas
- ✅ Métricas PROXY temporales documentadas
- ✅ Preparación FASE 2B (sin activar)
- ✅ Validaciones implementadas
- ✅ Función refresh mejorada

---

## Próximos Pasos (FASE 2B)

1. Crear `canon.commission_rules` con reglas dinámicas
2. Migrar cálculo de profit de PROXY a REAL
3. Deprecar `commission_rate_default` y `profit_proxy`
4. Implementar lógica económica avanzada

---

**FASE 2A CERRADA** ✅
