# Source of Truth — REAL Audit V2

**Fecha de congelamiento:** 2026-04-02
**Estado:** VIGENTE — Esta es la definición operativa oficial para auditoría y reconstrucción del universo REAL.
**Sustituye:** Cualquier referencia previa que designe `public.trips_all` como fuente canónica para auditoría o reconstrucción.

---

## 1. Fuentes raw oficiales para REAL

| Tabla | Schema | Rango temporal | Estado | Uso permitido |
|-------|--------|---------------|--------|---------------|
| `public.trips_2025` | public | 2025-01-01 a 2025-12-31 | **OFICIAL** | Auditoría, reconstrucción, facts, MVs |
| `public.trips_2026` | public | >= 2026-01-01 | **OFICIAL** | Auditoría, reconstrucción, facts, MVs |
| `public.trips_all` | public | Histórico (legacy) | **LEGACY / COMPATIBILIDAD TEMPORAL** | Solo backward compatibility; NO usar para auditoría ni reconstrucción |

### Regla operativa

> Las fuentes raw oficiales para auditar y reconstruir el sistema REAL son **`public.trips_2025`** y **`public.trips_2026`**.
> `public.trips_all` pasa a estado **legacy / compatibilidad temporal** y NO debe ser la base de auditoría ni de reconstrucción futura.

### Excepción documentada

`public.trips_all` puede mantenerse temporalmente como fuente en vistas/MVs legacy que aún no han sido migradas, siempre que:
1. El uso esté inventariado en `docs/REAL_SOURCE_USAGE_AUDIT_2026Q2.md`
2. Tenga fecha de migración planificada
3. No sea la fuente para nuevos consumidores

---

## 2. Semántica del universo REAL

### 2.1 Completados

**Criterio SQL:** `condicion = 'Completado'`

**Métricas que se calculan SOLO sobre completados:**
- `revenue` (SUM de comision_empresa_asociada)
- `avg_ticket` (AVG de precio_yango_pro)
- `active_drivers` (COUNT DISTINCT conductor_id)
- `trips_per_driver` (trips / active_drivers)
- `comision_empresa_asociada` (cobertura y validez)
- `margen`
- `GMV` / `total_fare`
- `distancia_km`
- `duración del viaje`

### 2.2 Cancelados

**Criterio SQL:** `condicion = 'Cancelado' OR condicion ILIKE '%cancel%'`

**Métricas que se calculan SOLO sobre cancelados:**
- `trips_cancelled`
- `cancel_rate` (cancelled / requested)
- `motivo_cancelacion` (normalizado)
- `cancel_reason_group` (agrupación de negocio)

### 2.3 Otros

**Criterio SQL:** Cualquier valor de `condicion` que no sea completado ni cancelado.

**Tratamiento:** Se contabiliza como `other` en `trip_outcome_norm`. No entra en métricas de revenue ni de cancelación.

### 2.4 Regla de exclusividad

Completado y cancelado son **mutuamente excluyentes** por viaje. En agregados se usan `FILTER` separados.

---

## 3. Viajes no mapeados (unmapped)

### Regla

> Un viaje que no mapea a country/city/park/LOB **NO debe desaparecer** del universo.
> Debe quedar visibilizado como **unmapped/fallback** explícito en auditoría y, eventualmente, en las capas de resolución.

### Categorías de unmapped

| Categoría | Definición |
|-----------|-----------|
| `fully_mapped` | park_id mapea a dim.dim_park con country y city |
| `park_unmapped` | park_id NO existe en dim.dim_park |
| `city_unmapped` | park_id existe pero city es NULL/vacío |
| `country_unmapped` | park_id existe pero country es NULL/vacío |
| `lob_unmapped` | tipo_servicio no resuelve a LOB |
| `partially_mapped` | Alguna dimensión resuelta, otra no |

### Acción inmediata

En esta fase: **diagnosticar y documentar** cuánto universo cae en cada categoría.
En fase posterior: exponer unmapped sin romper facts actuales.

---

## 4. Restricciones operativas de esta fase

1. **NO** se ejecutan rebuilds masivos de facts ni MVs
2. **NO** se borran tablas/vistas legacy
3. **NO** se mezcla Plan con Real en esta auditoría
4. **NO** se cambia frontend
5. **NO** se inventan columnas ni campos que no existan en las fuentes
6. Los cambios son estrictamente: documentación, scripts de auditoría read-only, y corrección documental mínima

---

## 5. Vista enriquecida actual (migración 118)

La vista `ops.v_real_trips_enriched_base` (migración `118_enriched_base_trips_2025_2026`) ya consume `trips_2025 + trips_2026` en lugar de `trips_all`. Esto confirma que la cadena Business Slice ya opera sobre las fuentes oficiales.

### Cadenas alineadas con esta decisión

| Cadena | Fuente raw | Estado |
|--------|-----------|--------|
| Business Slice (enriched → resolved → facts) | trips_2025 + trips_2026 | ALINEADA (mig 118) |
| Hourly-first (v_trips_real_canon_120d → fact_v2 → hour → day) | trips_all + trips_2026 | PENDIENTE MIGRACIÓN |
| Legacy mensual (mv_real_trips_monthly) | trips_all | PENDIENTE MIGRACIÓN |
| Legacy semanal (mv_real_trips_weekly) | trips_all | PENDIENTE MIGRACIÓN |
| Driver lifecycle (trips_unified) | trips_all + trips_2026 | PENDIENTE MIGRACIÓN |

---

## 6. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| `docs/SOURCE_OF_TRUTH_REGISTRY.md` | Registry de dominios/vistas — no afectado directamente |
| `docs/source_dataset_policy.md` | Ya marca trips_base como legacy — **alineado** |
| `docs/real_trip_source_contract.md` | Lista trips_all como fuente — **DESACTUALIZADO, pendiente actualización** |
| `docs/REAL_CANCELACIONES_ESTRUCTURAL.md` | Semántica de cancelaciones — **alineado** |
| `docs/real_trip_outcome_and_cancellation_semantics.md` | Semántica outcome — **alineado** |
| `docs/REAL_SOURCE_USAGE_AUDIT_2026Q2.md` | Inventario de uso — **creado en FASE 1** |

---

## 7. Aprobación y vigencia

- **Vigente desde:** 2026-04-02
- **Revisión:** Al completar migración de todas las cadenas a trips_2025 + trips_2026
- **Criterio de cierre:** Cuando `trips_all` no aparezca en ninguna cadena productiva activa
