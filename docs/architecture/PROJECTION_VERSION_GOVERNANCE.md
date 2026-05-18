# PROJECTION VERSION GOVERNANCE

## Propósito

Gobernanza de versiones de proyección en YEGO Control Tower.
Cada upload de proyección genera o actualiza una versión identificada por un `plan_version_key` técnico.
Las versiones conviven sin pisarse. La UI puede seleccionar, renombrar y cambiar entre versiones.
Toda la UI recalcula en base a la versión seleccionada.

## Motor arquitectónico

**Control Foundation (ACTIVE)** — Fase 1

No pertenece a Suggestion Engine, Decision Engine, Action Engine ni Learning Engine.

## Qué es una versión de proyección

Una versión de proyección es un conjunto de filas plan cargadas desde un archivo (CSV o Excel) que establecen metas operativas para trips, revenue y active_drivers por país, ciudad, línea de negocio, segmento y periodo.

Cada versión tiene:
- **plan_version_key**: llave técnica usada en SQL joins (ej. `ruta27_2026_05_17`, `control_loop_20260517_153000`). **NUNCA se modifica.**
- **display_name**: nombre visible en la UI, editable por el usuario (ej. "Proyección base R27", "Escenario agresivo Q2").
- **metadata**: description, source_filename, uploaded_by, uploaded_at, status, row_count, valid_rows, invalid_rows, min_period, max_period.

## Diferencia entre plan_version_key y display_name

| Campo | Rol | Modificable | Dónde se usa |
|---|---|---|---|
| `plan_version_key` | Llave técnica | NO | Joins SQL en ops.plan_trips_monthly, staging.control_loop_plan_metric_long |
| `display_name` | Nombre visible | SÍ | Selector de versión en UI, reportes, export |

**Regla:** El rename solo cambia `display_name`. El `plan_version_key` es inmutable.

## Tabla de metadata

```sql
CREATE TABLE plan.plan_versions_metadata (
    id                  BIGSERIAL PRIMARY KEY,
    plan_version_key    TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    description         TEXT,
    source_filename     TEXT,
    uploaded_by         TEXT,
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status              TEXT NOT NULL DEFAULT 'active',
    row_count           INTEGER,
    valid_rows          INTEGER,
    invalid_rows        INTEGER,
    min_period          DATE,
    max_period          DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Migración: `backend/alembic/versions/138_plan_versions_metadata.py`

## Cómo conviven las versiones

- **Append-only**: Cada upload inserta filas con su `plan_version_key`. Las versiones anteriores no se borran ni se pisan.
- **Unicidad**: `ops.plan_trips_monthly` y `staging.control_loop_plan_metric_long` filtran por `plan_version = %s`. Dos versiones distintas pueden tener datos para la misma ciudad/slice/periodo sin conflicto.
- **Latest vs seleccionada**: La UI nunca usa "latest" por defecto si el usuario seleccionó una versión explícita. El parámetro `plan_version` se propaga a todos los queries.

## Cómo se selecciona una versión

1. `GET /plan/versions` — lista versiones con metadata desde `plan.plan_versions_metadata`.
2. `GET /ops/control-loop/plan-versions` — lista versiones desde staging Control Loop enriquecidas con metadata.
3. La UI combina ambas fuentes y muestra un selector `<select>`.
4. Cada opción muestra `display_name` (o `plan_version_key` como fallback).
5. Al cambiar versión, se resetean los datos y se recargan proyección, YTD, oportunidades y export.

## Cómo se renombra una versión

**Desde la UI (Omniview Matrix):**
1. Botón ✏️ junto al selector de versión abre el modal `RenameProjectionVersionModal`.
2. El modal muestra `plan_version_key` como solo lectura.
3. `display_name` es editable (requerido).
4. `description` es editable (opcional).
5. Guardar llama `PATCH /plan/versions/{plan_version_key}`.
6. Al guardar exitosamente, la lista de versiones se refresca desde backend.
7. El `plan_version_key` permanece inmutable — los joins SQL no se afectan.

**Desde la API:**
`PATCH /plan/versions/{plan_version_key}` con body `display_name` (y `description` opcional).

Solo modifica `plan.plan_versions_metadata.display_name`. No toca datos de plan ni la llave técnica.

## Qué recalcula al cambiar versión

- Omniview Matrix (modo Vs Proyección)
- Proyección esperada (expected progress)
- YTD summary
- YTD alerts
- Oportunidades compactas
- Control Loop Plan vs Real
- Export Omniview

## Qué exporta Omniview

El export (`exportOmniviewFull`) incluye `planVersion` en la metadata y usa la versión seleccionada para los datos de proyección. Si el usuario selecciona versión A, el CSV exporta datos de versión A.

## Flujo de upload

1. Usuario sube archivo (CSV/Excel) desde la UI o desde Omniview Matrix.
2. `POST /plan/upload_ruta27_ui` detecta formato (plantilla CT o Ruta27).
3. `POST /plan/upload_control_loop_projection` para formato Control Loop.
4. El sistema valida estructura, genera `plan_version_key` con timestamp.
5. Inserta filas en `ops.plan_trips_monthly` o `staging.control_loop_plan_metric_long`.
6. Registra metadata en `plan.plan_versions_metadata` (display_name = plan_version_key por defecto).
7. La nueva versión aparece en `GET /plan/versions` y en el selector UI.
8. Usuario puede seleccionarla y renombrarla.

## Lo que NO se debe hacer

- **NO pisar versiones**: Los datos de versiones anteriores son inmutables.
- **NO cambiar plan_version_key**: Es la llave de join en todas las tablas.
- **NO usar latest por defecto si hay versión seleccionada**: Todos los queries deben respetar `plan_version` explícita.
- **NO renombrar borrando datos**: El rename es solo metadata.
- **NO mezclar Plan y Real incorrectamente**: Plan y Real se mantienen en columnas separadas.

## Archivos del sistema de versionado

| Archivo | Rol |
|---|---|
| `backend/alembic/versions/138_plan_versions_metadata.py` | Migración: tabla de metadata |
| `backend/app/adapters/plan_repo.py` | Funciones: upsert, get, update metadata |
| `backend/app/routers/plan.py` | Endpoints: GET/PATCH /plan/versions, upload con metadata |
| `backend/app/routers/ops.py` | Control Loop versions enriquecidas |
| `backend/app/services/control_loop_upload_service.py` | Registro metadata en upload CL |
| `backend/scripts/audit_projection_versions.py` | Script de auditoría |
| `frontend/src/services/api.js` | `getPlanVersions`, `patchPlanVersion`, `getControlLoopPlanVersions` |
| `frontend/src/components/projections/ProjectionVersionSelector.jsx` | Selector reutilizable con rename button |
| `frontend/src/components/projections/RenameProjectionVersionModal.jsx` | Modal compacto de rename (display_name + description) |
| `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Selector de versión, normalización, export |
| `frontend/src/components/ControlLoopPlanVsRealView.jsx` | Selector de versión CL |
| `frontend/src/components/operacion/OperationalOpportunitiesView.jsx` | Selector de versión |
| `frontend/src/utils/omniviewExport.js` | Export respeta versión seleccionada |
| `docs/architecture/PROJECTION_VERSION_GOVERNANCE.md` | Este documento |

## Checklist de cierre

- [x] Tabla `plan.plan_versions_metadata` creada (migración 138)
- [x] `GET /plan/versions` devuelve metadata enriquecida
- [x] `PATCH /plan/versions/{key}` permite rename
- [x] `GET /ops/control-loop/plan-versions` devuelve objetos con metadata
- [x] UI muestra `display_name` en selector
- [x] Normalización de versiones (strings → objetos con key/label)
- [x] Upload registra metadata automáticamente
- [x] Propagación de versión seleccionada verificada en código
- [x] Export respeta versión seleccionada
- [x] Convivencia de versiones confirmada (append-only, no pisado)
- [x] script `audit_projection_versions.py` creado
- [x] Build frontend pasa

---

*Documento generado para Fase 1 — Control Foundation. YEGO Control Tower.*
