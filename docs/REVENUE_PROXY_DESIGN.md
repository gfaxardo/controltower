# Revenue Proxy YEGO — Diseño, Resolución y Trazabilidad

**Fecha:** 2026-04-02
**Estado:** IMPLEMENTADO — migración 120, integración business slice, endpoints de cobertura
**Prerequisito:** `docs/SOURCE_OF_TRUTH_REAL_AUDIT_V2.md`

---

## 1. Problema que resuelve

`comision_empresa_asociada` (fuente de `revenue_yego_net`) está incompleta:
- trips_2025: 0% cobertura en completados
- trips_2026 enero: 94.45%
- trips_2026 febrero: 49.91%
- trips_2026 marzo+: 0%

Sin proxy, el sistema muestra revenue = NULL/0 para la mayoría del histórico.

## 2. Principio de diseño

- **NO sobreescribir** `comision_empresa_asociada` ni `revenue_yego_net`
- **Convivencia**: revenue real y proxy coexisten de forma explícita
- **Trazabilidad**: cada viaje lleva `revenue_source` = real | proxy | missing
- **Configuración versionada**: sin hardcode 3% disperso; tabla SQL con resolución determinística
- **Reversibilidad**: cuando la ingestión real se repare, el proxy se reduce automáticamente

---

## 3. Tabla de configuración

### `ops.yego_commission_proxy_config`

| Columna | Tipo | Descripción |
|---------|------|-------------|
| id | SERIAL PK | Auto-increment |
| country | TEXT | NULL = aplica a todos |
| city | TEXT | NULL = aplica a todos |
| park_id | TEXT | NULL = aplica a todos |
| tipo_servicio | TEXT | NULL = aplica a todos |
| commission_pct | NUMERIC NOT NULL | Porcentaje de comisión (ej: 0.03 = 3%) |
| valid_from | DATE | Inicio de vigencia |
| valid_to | DATE | Fin de vigencia |
| priority | INT | Desempate: mayor priority gana |
| is_active | BOOLEAN | Solo reglas activas se evalúan |
| notes | TEXT | Documentación |
| created_at | TIMESTAMPTZ | Auto |
| updated_at | TIMESTAMPTZ | Auto |

### Seed inicial

```sql
-- Default global 3%
INSERT INTO ops.yego_commission_proxy_config
    (country, city, park_id, tipo_servicio, commission_pct, valid_from, valid_to, priority, is_active, notes)
VALUES
    (NULL, NULL, NULL, NULL, 0.03, '2020-01-01', '2099-12-31', 0, TRUE,
     'Default global 3%. Fallback cuando no hay regla más específica.');
```

### Cómo agregar reglas más específicas

```sql
-- Ejemplo: comisión 5% para Cali
INSERT INTO ops.yego_commission_proxy_config
    (country, city, park_id, tipo_servicio, commission_pct, valid_from, valid_to, priority, is_active, notes)
VALUES
    ('colombia', 'cali', NULL, NULL, 0.05, '2025-01-01', '2099-12-31', 10, TRUE,
     'Comisión 5% para Cali');

-- Ejemplo: comisión 4% para un park específico en Lima
INSERT INTO ops.yego_commission_proxy_config
    (country, city, park_id, tipo_servicio, commission_pct, valid_from, valid_to, priority, is_active, notes)
VALUES
    ('peru', 'lima', 'park_id_xyz', NULL, 0.04, '2025-01-01', '2099-12-31', 20, TRUE,
     'Comisión 4% para park XYZ en Lima');
```

---

## 4. Lógica de resolución

### Función: `ops.resolve_commission_pct(country, city, park_id, tipo_servicio, trip_date)`

**Algoritmo:**
1. Filtra reglas activas cuya vigencia incluya `trip_date`
2. Filtra reglas que matcheen el contexto del viaje:
   - `country IS NULL` en la regla = aplica a cualquier país
   - `country = p_country` = aplica solo a ese país
   - (igual para city, park_id, tipo_servicio)
3. Ordena por **especificidad** (más campos no-NULL = más específico):
   - park_id + tipo_servicio + city + country = 4 (máxima especificidad)
   - Solo country = 1
   - Todo NULL = 0 (default global)
4. Desempate: `priority DESC`
5. Segundo desempate: `valid_from DESC` (regla más reciente)
6. Toma el primer resultado (`LIMIT 1`)

**Garantía:** Siempre retorna un valor si existe al menos una regla default activa.

---

## 5. Campos de revenue

### Por viaje (vista `ops.v_real_revenue_proxy_audit`)

| Campo | Definición |
|-------|-----------|
| `revenue_yego_real` | `ABS(comision_empresa_asociada)` si completado y no-null. NULL en otro caso. |
| `revenue_yego_proxy` | `precio_yango_pro * commission_pct_config` si completado y ticket disponible. NULL en otro caso. |
| `revenue_yego_final` | `COALESCE(revenue_yego_real, revenue_yego_proxy)`. Real tiene prioridad absoluta. |
| `revenue_source` | `'real'` si usó dato real, `'proxy'` si usó proxy, `'missing'` si no hay ninguno, NULL si no es completado. |
| `commission_pct_applied` | El porcentaje usado para el proxy. NULL si revenue_source = 'real'. |
| `revenue_yego_net_original` | Valor original sin modificar (preserva verdad histórica). |

### Agregado (fact tables de Business Slice)

| Campo | Definición |
|-------|-----------|
| `revenue_yego_net` | **SIN CAMBIO** — suma de comision_empresa_asociada original |
| `revenue_yego_final` | Suma de COALESCE(real, proxy) por viaje completado |
| `revenue_real_coverage_pct` | % de viajes completados con revenue real (0-100) |
| `revenue_proxy_trips` | Conteo de viajes completados cuyo revenue vino de proxy |
| `revenue_real_trips` | Conteo de viajes completados cuyo revenue vino de dato real |

---

## 6. Cadenas integradas

| Cadena | Integración | Tipo |
|--------|------------|------|
| Business Slice (month_fact) | `revenue_yego_final`, coverage en INSERT | Inline en temp table |
| Business Slice (day_fact) | `revenue_yego_final`, coverage en INSERT | Inline en temp table |
| Business Slice (week_fact) | Rollup desde day_fact | Automático |
| Vista de auditoría | `ops.v_real_revenue_proxy_audit` | Vista standalone |
| Vista de cobertura | `ops.v_real_revenue_proxy_coverage` | Vista agregada |

### Cadenas NO tocadas (para fase posterior)

| Cadena | Motivo |
|--------|--------|
| Hourly-first (v_real_trip_fact_v2 → hour → day) | Depende de v_trips_real_canon_120d; requiere migración de canon primero |
| Legacy mensual (mv_real_trips_monthly) | Requiere rebuild de MV |
| Canonical monthly hist | Usa margin_total, no comision_empresa_asociada directamente |
| Real operational (gross_revenue) | Depende de cadena hourly-first |

---

## 7. Trazabilidad

### Endpoints

| Endpoint | Qué expone |
|----------|-----------|
| `GET /ops/revenue-proxy/coverage` | Cobertura real vs proxy por mes/país/ciudad |
| `GET /ops/revenue-proxy/config` | Configuración activa de comisión proxy |

### Data Trust

Dominio `revenue_proxy` registrado en `source_of_truth_registry.py`:
- primary: `ops.v_real_revenue_proxy_audit`
- secondary: `ops.v_real_revenue_proxy_coverage`
- source_mode: canonical

### Cómo distinguir real vs proxy

1. **Por viaje**: `revenue_source` en `v_real_revenue_proxy_audit`
2. **Por mes/país**: `pct_real` y `pct_proxy` en `v_real_revenue_proxy_coverage`
3. **En fact tables**: `revenue_real_coverage_pct`, `revenue_proxy_trips`, `revenue_real_trips`

---

## 8. Cutover / Corte temporal

### Enfoque

El proxy NO tiene una fecha de corte fija. La lógica valida **por fila**:
- Si `comision_empresa_asociada` existe y no es null/0 → usa real
- Si no → usa proxy

Esto significa:
1. Cuando la ingestión real se repare y `comision_empresa_asociada` se llene, el proxy se reduce automáticamente
2. No hay necesidad de "apagar" el proxy; simplemente deja de usarse cuando el dato real está disponible
3. Si febrero 2026 tiene 50% real y 50% proxy, ambos conviven correctamente

### Versionado temporal via config

La tabla `yego_commission_proxy_config` soporta `valid_from`/`valid_to`:
- Si en el futuro el porcentaje de comisión cambia, se crea una nueva regla con `valid_from` posterior
- Las reglas viejas no se borran; se dejan con `valid_to` anterior
- El sistema resuelve la regla correcta según la fecha del viaje

### Cuándo retirar el proxy

1. Cuando `pct_real` en `v_real_revenue_proxy_coverage` sea > 95% para todos los meses activos
2. Cuando el equipo de ingestión confirme que `comision_empresa_asociada` está completa
3. El proxy puede dejarse como safety net permanente sin costo (solo se activa si real falta)

---

## 9. Advertencia funcional

### Qué significa "proxy"

Revenue proxy es una **estimación** de la comisión YEGO calculada como:
```
revenue_proxy = precio_yango_pro × commission_pct_configurado
```

### Cuándo se usa

Se usa automáticamente cuando `comision_empresa_asociada` (dato real de comisión) no está disponible o es 0 para un viaje completado.

### Por qué existe

La fuente upstream que alimenta `comision_empresa_asociada` tuvo una interrupción/incompletitud:
- 2025: nunca se pobló
- 2026 enero: 94.45% poblado
- 2026 febrero: 49.91% poblado
- 2026 marzo+: 0% poblado

Sin proxy, el revenue del sistema sería NULL/0 para la mayoría del histórico.

### Limitaciones

1. El porcentaje de comisión proxy (default 3%) es una aproximación. Puede diferir del real.
2. No captura variaciones de comisión por viaje individual.
3. El proxy es determinístico y reproducible, pero no es dato real.

### Cómo se retirará

Cuando la ingestión real esté sana:
1. `comision_empresa_asociada` se llenará para nuevos viajes
2. Si se hace backfill de histórico, el proxy se desplaza automáticamente (real tiene prioridad)
3. No hay necesidad de "apagar" el proxy; la lógica COALESCE(real, proxy) lo maneja

---

## 10. Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `backend/alembic/versions/120_revenue_proxy_config_and_layer.py` | Migración: tabla, función, vistas, columnas en facts |
| `backend/app/services/business_slice_incremental_load.py` | Proxy columns en temp table + agregación |
| `backend/app/routers/ops.py` | Endpoints /revenue-proxy/coverage y /config |
| `backend/app/config/source_of_truth_registry.py` | Dominio revenue_proxy registrado |
| `docs/REVENUE_PROXY_DESIGN.md` | Este documento |
