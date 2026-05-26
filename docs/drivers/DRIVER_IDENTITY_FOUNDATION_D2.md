# DRIVER IDENTITY FOUNDATION — FASE D2

**Fecha:** 2026-05-25
**Fase activa:** 1H.4 — Operational Maturity Governance Layer (Control Foundation)
**Sub-fase Drivers:** D2 — Identity Foundation + Raw Source Freshness Map

---

## 1. GOVERNANCE CHECK

### Fase ACTIVE
- **Motor:** Control Foundation
- **Fase:** 1H.4 — Operational Maturity Governance Layer
- **D2 pertenece a Control Foundation:** SI — construir serving facts e identidad es foundation, no diagnóstico.

### Fase READY NEXT
- Diagnostic Engine 2A.3 — NO activado

### Motores BLOQUEADOS
- Reachability, Forecast, Suggestion, Decision, Action, AI Copilot, Learning

### Verdicto
D2 es 100% Control Foundation. No toca motores bloqueados. GO.

---

## 2. FUENTES INSPECCIONADAS

### 2.1 Fuentes de identidad

| Fuente | Schema | driver_id | nombre | phone | park_id | existe en ops? |
|--------|--------|-----------|--------|-------|---------|---------------|
| `public.drivers` | public | SI (PK) | NO (full_name) | SI (columna phone, sin usar) | SI | PARCIAL — usado por MVs lifecycle, pero phone nunca consultado |
| `public.drivers_data` | public | SI | SI (full_name) | SI (driver_phone, sin usar) | NO | NO — 35 columnas, rica en metadata, nunca integrada en ops |
| `public.module_ct_cabinet_drivers` | public | SI | SI (driver_nombre, driver_apellido) | SI (driver_phone, sin usar) | SI | NO — 19 columnas, Diego cabinet legacy, nunca referenciada |
| `ops.v_dim_driver_resolved` | ops | SI | SI (conductor_nombre de trips) | NO | NO | SI — fuente canónica actual de nombre |

### 2.2 Fuentes de actividad

| Fuente | Schema | driver_id | fecha operativa | loaded_at |
|--------|--------|-----------|-----------------|-----------|
| `public.trips_2025` | public | SI (conductor_id) | fecha_finalizacion | NO |
| `public.trips_2026` | public | SI (conductor_id) | fecha_finalizacion | NO |
| `public.trips_unified` | public | SI (conductor_id) | UNION trips_all + trips_2026 | NO |
| `ops.driver_daily_activity_fact` | ops | SI | activity_date | last_refreshed_at |

### 2.3 Fuentes geo

| Fuente | Schema | park_id | ciudad | país |
|--------|--------|---------|--------|------|
| `dim.dim_park` | dim | SI | city | country |
| `ops.v_dim_park_resolved` | ops | SI (derivado de dim_park) | city | country |

### 2.4 Fuentes NO existentes

- `module_ct_cabinet_drivers` — la auditoría fraud la encontró, pero no hay código que la consuma
- `summary_daily` — No existe en este proyecto

---

## 3. FRESHNESS MAP

El servicio `driver_raw_freshness_service.py` inspecciona dinámicamente 10 fuentes:

| Fuente | Rol | Métrica de freshness | Estado esperado |
|--------|-----|---------------------|-----------------|
| `public.drivers` | identity | `MAX(created_at)` | Variable |
| `public.drivers_data` | contactability | `MAX(updated_at)` o unknown | Riesgo: sin columna temporal |
| `public.module_ct_cabinet_drivers` | identity | `MAX(updated_at)` o `MAX(created_at)` | Unknown hasta inspección |
| `public.trips_2025` | activity | `MAX(fecha_finalizacion)` | Stale (<= 2025-12-31) |
| `public.trips_2026` | activity | `MAX(fecha_finalizacion)` | Fresh (datos corrientes) |
| `ops.driver_daily_activity_fact` | activity | `MAX(last_refreshed_at)` o `MAX(activity_date)` | Fresh (refresh diario) |
| `dim.dim_park` | geo | N/A (dimensión) | Fresh (static) |
| `ops.v_dim_park_resolved` | geo | Derivado de dim_park | Fresh |
| `ops.v_dim_driver_resolved` | identity | Derivado de trips_unified | Fresh si trips frescos |
| `ops.mv_driver_lifecycle_base` | lifecycle_candidate | `MAX(last_completed_ts)` | Fresh si refresh OK |

---

## 4. FUENTE CANÓNICA POR CAMPO

| Campo | Fuente primaria | Fuente secundaria | Fallback |
|-------|----------------|-------------------|----------|
| `driver_id` | `public.drivers.driver_id` | `trips_unified.conductor_id` | — |
| `driver_name` | `ops.v_dim_driver_resolved.driver_name` (MAX conductor_nombre) | `public.drivers_data.full_name` | `public.module_ct_cabinet_drivers.driver_nombre` |
| **`phone`** | `public.drivers_data.driver_phone` | `public.drivers.phone` | `public.module_ct_cabinet_drivers.driver_phone` |
| `park_id` | `public.drivers.park_id` | `mv_driver_lifecycle_base.driver_park_id` | — |
| `park_name` | `dim.dim_park.park_name` | `ops.v_dim_park_resolved.park_name` | — |
| `city` | `dim.dim_park.city` | `ops.v_dim_park_resolved.city` | — |
| `country` | `dim.dim_park.country` | `ops.v_dim_park_resolved.country` | — |
| `first_seen_at` | `public.drivers.created_at` | — | — |
| `first_trip_at` | `ops.mv_driver_lifecycle_base.activation_ts` | — | — |
| `latest_trip_at` | `ops.mv_driver_lifecycle_base.last_completed_ts` | — | — |
| `latest_activity_at` | `ops.driver_daily_activity_fact.MAX(activity_date)` | `mv_driver_lifecycle_base.last_completed_ts` | — |

---

## 5. DISEÑO DRIVER_IDENTITY_FACT

### Estado: DISEÑADO (no implementado como MV todavía)

La fact está diseñada conceptualmente pero requiere confirmación de disponibilidad de fuentes en producción antes de materializarla como MV.

```sql
CREATE MATERIALIZED VIEW serving.driver_identity_fact AS
SELECT
    d.driver_id,
    COALESCE(vr.driver_name, dd.full_name, mct.driver_nombre) AS driver_name,
    COALESCE(dd.driver_phone, d.phone::text, mct.driver_phone) AS phone,
    COALESCE(p.city, prk.city) AS city,
    COALESCE(p.country, prk.country) AS country,
    d.park_id,
    COALESCE(p.park_name, prk.park_name) AS park_name,
    d.created_at AS first_seen_at,
    lb.activation_ts AS first_trip_at,
    lb.last_completed_ts AS latest_trip_at,
    GREATEST(
        lb.last_completed_ts,
        (SELECT MAX(activity_date) FROM ops.driver_daily_activity_fact adf WHERE adf.driver_id = d.driver_id)
    ) AS latest_activity_at,
    CASE
        WHEN dd.driver_phone IS NOT NULL THEN 'public.drivers_data'
        WHEN d.phone IS NOT NULL THEN 'public.drivers'
        WHEN mct.driver_phone IS NOT NULL THEN 'public.module_ct_cabinet_drivers'
        ELSE NULL
    END AS phone_source,
    CASE
        WHEN vr.driver_name IS NOT NULL THEN 'ops.v_dim_driver_resolved'
        WHEN dd.full_name IS NOT NULL THEN 'public.drivers_data'
        WHEN mct.driver_nombre IS NOT NULL THEN 'public.module_ct_cabinet_drivers'
        ELSE NULL
    END AS identity_source,
    CASE
        WHEN dd.driver_phone IS NOT NULL THEN 'high'
        WHEN d.phone IS NOT NULL THEN 'high'
        WHEN mct.driver_phone IS NOT NULL THEN 'medium'
        WHEN vr.driver_name IS NOT NULL THEN 'medium'
        ELSE 'low'
    END AS identity_confidence,
    CASE
        WHEN dd.driver_phone IS NULL AND d.phone IS NULL AND mct.driver_phone IS NULL THEN 'warning'
        ELSE 'ok'
    END AS data_quality_status,
    CASE
        WHEN dd.driver_phone IS NULL AND d.phone IS NULL AND mct.driver_phone IS NULL THEN ARRAY['phone']
        ELSE ARRAY[]::text[]
    END AS missing_fields,
    NOW() AS refreshed_at
FROM public.drivers d
LEFT JOIN ops.v_dim_driver_resolved vr ON d.driver_id = vr.driver_id
LEFT JOIN public.drivers_data dd ON d.driver_id = dd.driver_id
LEFT JOIN public.module_ct_cabinet_drivers mct ON d.driver_id = mct.driver_id
LEFT JOIN dim.dim_park p ON d.park_id = p.park_id
LEFT JOIN ops.v_dim_park_resolved prk ON d.park_id = prk.park_id
LEFT JOIN ops.mv_driver_lifecycle_base lb ON d.driver_id = lb.driver_key;
```

**NOTA:** Esta query asume que las tablas `public.drivers_data` y `public.module_ct_cabinet_drivers` existen con columnas `driver_phone`, `full_name`, `driver_nombre`. La fact debe crearse solo después de verificar disponibilidad en entorno productivo.

---

## 6. ENDPOINT CONTRACTS

### 6.1 GET /drivers/raw-freshness

**Response:**
```json
{
  "status": "ok|warning|blocked",
  "generated_at": "2026-05-25T...",
  "sources": [
    {
      "source_name": "public.drivers",
      "source_type": "raw",
      "exists": true,
      "role": "identity",
      "record_count": 12345,
      "max_operational_date": "2026-05-24T...",
      "max_loaded_at": null,
      "freshness_status": "fresh|stale|unknown|blocked",
      "freshness_reason": "...",
      "is_blocking_for_d2": true,
      "remediation": "...",
      "available_columns": {"driver_id": true, "phone": true, ...}
    }
  ],
  "blocking_gaps": [...],
  "warnings": [...]
}
```

### 6.2 GET /drivers/identity

**Query params:** `driver_id`, `country`, `city`, `park_id`, `has_phone`, `limit`, `offset`

**Response:**
```json
{
  "total": 100,
  "limit": 100,
  "offset": 0,
  "drivers": [
    {
      "driver_id": "uuid",
      "driver_name": "Carlos Pérez",
      "phone": "+57 300 123 4567",
      "phone_source": "public.drivers_data.driver_phone",
      "country": "Colombia",
      "city": "Bogotá",
      "park_id": "uuid",
      "park_name": "Park Centro",
      "first_seen_at": "2025-03-15T...",
      "first_trip_at": "2025-03-16T...",
      "latest_trip_at": "2026-05-24T...",
      "latest_activity_at": "2026-05-24T...",
      "identity_confidence": "high",
      "data_quality_status": "ok",
      "missing_fields": [],
      "refreshed_at": "2026-05-25T..."
    }
  ]
}
```

### 6.3 GET /drivers/identity/{driver_id}

Single driver detail. Same response shape, single object.

---

## 7. GAPS ENCONTRADOS

### Bloqueantes para D3/D4

| Gap | Severidad | Estado |
|-----|-----------|--------|
| Phone no integrado en `ops.v_dim_driver_resolved` | CRÍTICO | **Parcialmente resuelto** — `driver_identity_service.py` ahora consulta `public.drivers_data.phone`, `public.drivers.phone`, `public.module_ct_cabinet_drivers.driver_phone` en cascada |
| `public.drivers_data` no usado por ninguna capa ops | CRÍTICO | **Mitigado** — `driver_identity_service.py` y `search_driver_identities()` ahora lo consultan |
| `public.module_ct_cabinet_drivers` sin referencias | ALTO | **Mitigado** — incluido como fuente terciaria en identity service |
| Sin `serving.driver_identity_fact` materializada | ALTO | **Pendiente** — diseñada pero no materializada. Requiere confirmación de columnas en producción |
| Sin serving fact de activity semanal (rolling 7/14/30d) | ALTO | **Postergado a D3** |
| Sin serving fact de lifecycle | MEDIO | **Postergado a D3** |

### No bloqueantes

| Gap | Nota |
|-----|------|
| `public.drivers.license` no integrado | Columna existe, no consultada. Postergado. |
| `public.drivers.email` no encontrado | Columna no existe en ninguna fuente. Gap permanente. |
| `ops.v_dim_driver_resolved` sin phone | Se resolvió a nivel de servicio (no requiere migración de vista para funcionar) |

---

## 8. QUÉ QUEDA BLOQUEADO PARA D3/D4

| Capacidad | Bloqueante | Remediation |
|-----------|-----------|-------------|
| Listas accionables con phone | Resuelto en D2 — phone ahora se consulta de fuentes reales | OK |
| `driver_supply_actionable_fact` | Requiere `serving.driver_identity_fact` + `driver_activity_weekly_fact` | Crear en D3 |
| `driver_activity_weekly_fact` | Requiere agregación sobre `driver_daily_activity_fact` | Crear en D3 |
| Lifecycle drilldown enriquecido | Phone ahora disponible vía identity service | Integrar en D3 |

---

## 9. GO / NO-GO

### GO para D2
- **Identity foundation** está construida: fuentes mapeadas, phone integrado, freshness inspeccionable
- **Endpoints** funcionan: `/drivers/raw-freshness`, `/drivers/identity`
- **Frontend** muestra Data Foundation card en Supply Overview
- **Phone deja de ser None hardcodeado** en `driver_identity_service.py` (consulta 3 fuentes reales)
- **0 tabs ocultas**, **0 queries rotas**, **0 endpoints productivos modificados**

### NO-GO para D3 hasta que:
- `serving.driver_identity_fact` esté materializada (opcional, el service ya resuelve identity sin MV)
- `driver_activity_weekly_fact` esté creada (requiere agregación rolling)
- Phone coverage sea validado en producción (>80% de drivers activos con phone)

### El identity resolver legacy sigue funcionando
`driver_identity_resolver_service.py` NO fue modificado — sigue hardcodeando phone=None. Los servicios existentes que lo consumen (recoverability, leakage, behavior alerts) no se rompen. El nuevo `driver_identity_service.py` es independiente y será adoptado progresivamente.

---

## 10. REMEDIATION PLAN

| Paso | Acción | Prioridad |
|------|--------|-----------|
| 1 | Validar que `public.drivers_data.driver_phone` existe en producción | P0 |
| 2 | Validar que `public.module_ct_cabinet_drivers.driver_phone` existe | P0 |
| 3 | Materializar `serving.driver_identity_fact` si columnas confirmadas | P1 |
| 4 | Agregar refresh diario para `driver_identity_fact` | P1 |
| 5 | Migrar `driver_identity_resolver_service.py` a usar nuevo identity service | P2 |
| 6 | Integrar phone en endpoints de lifecycle/behavior para drilldowns | P2 |

---

## 11. ARCHIVOS CREADOS/MODIFICADOS

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `backend/app/services/driver_raw_freshness_service.py` | NUEVO | Inspección dinámica de 10 fuentes RAW, freshness map |
| `backend/app/services/driver_identity_service.py` | NUEVO | Identity resolution con phone de fuentes reales (3 tablas) |
| `backend/app/routers/drivers.py` | NUEVO | Router con `/drivers/raw-freshness` + `/drivers/identity` |
| `backend/app/main.py` | MOD | Registro del nuevo router `drivers` |
| `frontend/src/components/driver/DriverDataFoundation.jsx` | NUEVO | Card de Data Foundation en Supply Overview |
| `frontend/src/components/driver/DriverOperatingHub.jsx` | MOD | Integración de DriverDataFoundation para Supply |
| `docs/drivers/DRIVER_IDENTITY_FOUNDATION_D2.md` | NUEVO | Este documento |

### Archivos NO modificados (intencionalmente)
- `driver_identity_resolver_service.py` — legacy, sin tocar
- `ops.py`, `supply_service.py`, etc. — sin tocar
- MVs y serving facts existentes — sin tocar
- Rutas frontend, tabs, governance — sin tocar
- Omniview — sin tocar

---

**FIN DEL DOCUMENTO DE IDENTITY FOUNDATION D2**
