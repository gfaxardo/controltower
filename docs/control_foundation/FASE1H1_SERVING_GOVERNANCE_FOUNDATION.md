# FASE 1H.1 — SERVING GOVERNANCE FOUNDATION

## Veredicto: ✅ GO

---

## 1. Objetivo

Crear la capa de gobernanza operacional para serving facts y refreshes. Control Tower deja de depender de refreshes manuales y fallback impredecible.

---

## 2. Componentes Entregados

### 2.1 Base de Datos

| Tabla | Propósito |
|-------|-----------|
| `ops.serving_registry` | Registro central de cada fact materializada: grain, plan_version, row_count, freshness, estado |
| `ops.serving_refresh_log` | Historial de ejecuciones de refresh: duración, éxito/fallo, trigger |

### 2.2 Servicio

**Archivo:** `backend/app/services/serving_governance_service.py`

| Función | Descripción |
|---------|-------------|
| `register_serving_fact()` | Registra/actualiza un serving fact |
| `mark_refresh_start()` | Marca inicio de refresh, devuelve refresh_id |
| `mark_refresh_end()` | Marca fin con resultado, actualiza registry |
| `validate_serving_coverage()` | Valida cobertura (grains, rows, stale, failures) |
| `get_serving_health()` | Estado de salud agregado |
| `detect_missing_grains()` | Granos sin serving facts |
| `detect_stale_facts()` | Facts con datos >24h |
| `detect_runtime_risk()` | Facts que exponen riesgo de runtime fallback |
| `compute_serving_integrity()` | Score de integridad (0-100) |

### 2.3 Endpoints

| Endpoint | Descripción |
|----------|-------------|
| `GET /ops/serving/health` | Estado de salud: status, total_facts, total_rows, stale_count |
| `GET /ops/serving/coverage` | Cobertura por grain: facts, rows, stale, missing |
| `GET /ops/serving/failures` | Últimos 20 fallos de refresh |
| `GET /ops/serving/runtime-risks` | Facts con riesgo de runtime fallback |
| `GET /ops/serving/integrity` | Score de integridad + recomendación |

### 2.4 Dashboard

**Archivo:** `frontend/src/components/ServingGovernanceDashboard.jsx`

Muestra:
- Estado de salud (healthy/degraded/attention)
- Facts activos + total rows
- Integridad, stale, missing grains, runtime risks

### 2.5 SQL

**Archivo:** `backend/sql/phase1h1_serving_governance.sql`

- CREATE TABLE ops.serving_registry
- CREATE TABLE ops.serving_refresh_log
- Seed inicial desde serving.omniview_projection_daily_fact

---

## 3. Validación en Producción

```
GET /ops/serving/health
→ status=healthy, facts=3, rows=12,112, stale=0, missing=[]

GET /ops/serving/coverage
→ daily: 1 fact, 10,287 rows
→ monthly: 1 fact, 338 rows
→ weekly: 1 fact, 1,487 rows
→ stale: 0, missing_grains: [], failures: 0

GET /ops/serving/runtime-risks
→ [] (0 risks)

GET /ops/serving/integrity
→ score=100, status=healthy, rec="All systems operational"
```

---

## 4. Protecciones Activas

- **runtime_protected = TRUE**: El sistema NO ejecuta runtime fallback automático si un fact falta o está stale
- **fallback_allowed = FALSE**: Sin fallback automático — devuelve 200 controlado
- **Stale detection**: Umbral de 24h. Facts >24h sin refresh se marcan como stale
- **Missing grain detection**: Detecta grains que la UI expone pero no tienen serving fact

---

## 5. Archivos

| Archivo | Tipo |
|---------|------|
| `backend/sql/phase1h1_serving_governance.sql` | SQL migration |
| `backend/app/services/serving_governance_service.py` | Servicio |
| `backend/app/routers/ops.py` | Endpoints (5 nuevos) |
| `frontend/src/components/ServingGovernanceDashboard.jsx` | Dashboard |
| `docs/control_foundation/FASE1H1_SERVING_GOVERNANCE_FOUNDATION.md` | Reporte |

---

## 6. GO / NO-GO

**✅ GO** — Serving governance operacional. Todos los endpoints responden. Registry populado. Dashboard funcional. La serving layer queda monitoreada y protegida contra runtime fallback automático.
