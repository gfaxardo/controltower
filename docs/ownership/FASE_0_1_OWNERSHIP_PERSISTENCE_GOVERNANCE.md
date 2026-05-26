# Fase 0.1 — Ownership Persistence Governance

**Fecha:** 2026-05-25
**Estado:** Implementado
**Fase anterior:** Fase 0.0 — Projection Upload Compatibility
**Siguiente fase recomendada:** Fase 0.2 — Ownership Serving Facts (pre-Omniview)

======================================================================
RESUMEN EJECUTIVO
======================================================================

Se formalizó la persistencia de ownership de proyecciones en una capa
gobernada (`ops.projection_ownership`), separada de staging y de la
tabla canónica de plan.

El flujo completo ahora es:

    RAW CSV → STAGING → CANONICAL PLAN → OWNERSHIP GOVERNANCE

La capa de ownership NO afecta Omniview, Plan vs Real, MVs ni serving facts.

======================================================================
QUÉ SE IMPLEMENTÓ
======================================================================

1. **Tabla `ops.projection_ownership`** (migración 155)
   - plan_version_key, country, city, city_norm, linea_negocio_canonica
   - jefe_producto, producto, estado (nullable)
   - source_upload_id, source_period_first, source_row_hash (trazabilidad)
   - conflict_detected, conflict_detail (detección de conflictos)
   - UNIQUE (plan_version_key, country, city, linea_negocio_canonica)

2. **Sync automático post-upload**
   - `control_loop_upload_service.py` invoca `sync_ownership_from_staging()`
   - Deduplica filas de staging por dimensiones (ignora métricas/períodos)
   - Si falla, NO bloquea el upload (ownership es metadata, no core)
   - Resultado incluido en la respuesta del upload como `ownership_sync`

3. **Repo gobernado** (`projection_ownership_repo.py`)
   - `sync_ownership_from_staging(plan_version)` → extrae de staging, inserta en ownership
   - `get_ownership_summary(plan_version_key)` → resumen para endpoint

4. **Endpoint técnico** `GET /plan/ownership/summary`
   - Solo lectura, acceso técnico
   - Devuelve: total_ownership_rows, owners_detected, conflicts_count,
     missing_owner_count, rows_by_owner, conflicts_sample

======================================================================
QUÉ NO SE IMPLEMENTÓ
======================================================================

- Omniview Ownership View
- Perspective Engine / selector
- Scoreboard / rankings / gamificación
- Momentum por owner
- Reachability ownership
- Forecast ownership
- UI de ownership (salvo endpoint técnico de verificación)
- Lógica de ownership en frontend

======================================================================
MODELO DE DATOS
======================================================================

```sql
CREATE TABLE ops.projection_ownership (
    id                    BIGSERIAL PRIMARY KEY,
    plan_version_key      TEXT NOT NULL,
    country               TEXT,
    city                  TEXT,
    city_norm             TEXT,
    linea_negocio_canonica TEXT NOT NULL,
    jefe_producto         TEXT,
    producto              TEXT,
    estado                TEXT,
    source_upload_id      TEXT,
    source_period_first   DATE,
    source_row_hash       TEXT,
    conflict_detected     BOOLEAN DEFAULT FALSE,
    conflict_detail       JSONB,
    created_at            TIMESTAMPTZ DEFAULT NOW(),
    updated_at            TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (plan_version_key,
            COALESCE(country, ''),
            COALESCE(city, ''),
            linea_negocio_canonica)
);
```

======================================================================
REGLAS DE CONFLICTO
======================================================================

**Unicidad:** Un ownership por combinación (plan_version + country + city + LOB canónica).

**Detección de conflictos:** Durante el sync, si un key ya tiene jefe_producto
y el nuevo registro tiene uno distinto, se registra como conflicto.

**Resolución actual:** El sync usa ON CONFLICT DO UPDATE SET updated_at = NOW().
Esto preserva el primer valor insertado.

**Futuro:** Se podría implementar DO UPDATE con registro de historial de cambios.

======================================================================
ENDPOINT TÉCNICO
======================================================================

```
GET /plan/ownership/summary?plan_version_key=ruta27_2026_05_25
```

Response:
```json
{
  "plan_version_key": "ruta27_2026_05_25",
  "total_ownership_rows": 63,
  "owners_detected": ["Ariana", "Eduardo", "Stacy"],
  "conflicts_count": 0,
  "missing_owner_count": 0,
  "rows_by_owner": {
    "Ariana": 28,
    "Eduardo": 14,
    "Stacy": 21
  },
  "conflicts_sample": []
}
```

======================================================================
ARCHIVOS MODIFICADOS / CREADOS
======================================================================

| Archivo | Acción |
|---|---|
| `alembic/versions/155_projection_ownership_governance.py` | Nueva migración |
| `app/adapters/projection_ownership_repo.py` | Nuevo repo de ownership |
| `app/services/control_loop_upload_service.py` | Integrado sync post-upload |
| `app/routers/plan.py` | Agregado GET /plan/ownership/summary |
| `scripts/validate_projection_ownership_governance.py` | Nuevo script QA |
| `docs/ownership/FASE_0_1_OWNERSHIP_PERSISTENCE_GOVERNANCE.md` | Esta documentación |

======================================================================
RIESGOS
======================================================================

1. **Conflictos silenciosos:** Si dos uploads asignan distinto jefe al mismo
   LOB, el primero gana. El conflicto se detecta pero no se resuelve
   automáticamente. Requiere intervención humana.

2. **Dependencia de staging:** El sync lee de staging. Si staging se limpia
   sin migrar ownership, se pierde trazabilidad.

3. **No hay FK formal:** No hay foreign key entre ownership y plan_trips_monthly
   por diseño (ownership es capa separada). Si se borra un plan_version de
   plan_trips_monthly, ownership queda huérfano.

======================================================================
SIGUIENTE FASE RECOMENDADA (0.2)
======================================================================

- Crear vista `ops.v_ownership_serving_fact` materializada por plan_version
- Integrar jefe_producto como dimensión de filtro en Omniview (modo técnico)
- Agregar endpoint `GET /ops/business-slice/omniview-projection?owner=Ariana`
- NO implementar todavía: scoreboard, rankings, perspective selector
