# FASE 3A.1 — YANGO LOYALTY OPERATING LAYER

**Versión:** 1.0.0  
**Fecha:** 2026-05-22  
**Estado:** Implementado  
**Dependencia:** Fase 3A (Reachability Engine)

---

## 1. Objetivo

Convertir la Fase 3A (Loyalty Reachability Engine) en una capa operable día a día por operaciones, KAM, supply y lealtad. Sin recomendaciones automáticas ni IA.

---

## 2. Features Nuevas

### 2.1 Goal Management UI
- **Componente:** `GoalManagementTable`
- **Funcionalidad:** Tabla editable de metas por KPI × Ciudad
- **Incluye:** Copiar metas de mes anterior, thresholds Oro/Plata/Bronce, validación de inputs

### 2.2 Manual KPI Input UI
- **Componente:** `ManualKpiInputForm`
- **Funcionalidad:** Formulario de ingreso para los 8 KPIs manuales
- **Incluye:** Freshness panel, validación de rango (0-100 para %, scores), unidad por KPI

### 2.3 Data Completeness Tracking
- **Endpoint:** `GET /yango-loyalty/completeness`
- **Estados:** AVAILABLE, COMPLETE, PARTIAL, MANUAL_PENDING, STALE
- **Métricas:** % global, por ciudad, desglose por estado

### 2.4 KPI Freshness Layer
- **Endpoint:** `GET /yango-loyalty/freshness`
- **Estados:** FRESH (<48h), WARNING (48-96h), STALE (>96h), MISSING
- **Columna:** `updated_by` agregada a `monthly_goals` y `manual_results`

### 2.5 Daily Progress Snapshot
- **Endpoint:** `GET /yango-loyalty/daily-snapshot`
- **Métricas:** Expected value today, real value, gap, daily delta, semaphore colors (green/amber/red)
- **Agrupación:** on_track, ahead, behind, at_risk

### 2.6 Historical Monthly Tracking
- **Endpoint:** `GET /yango-loyalty/historical?months_back=6`
- **Visualización:** Tabla pivot mes × (ciudad + KPI) con categoría histórica
- **Filtros:** por KPI, por ciudad, por cantidad de meses

### 2.7 Bulk Input Support
- **Endpoint:** `POST /yango-loyalty/manual-results/bulk`
- **Validación:** KPI válido, ciudad válida, mes válido, rango numérico, sin duplicados
- **Endpoint:** `POST /yango-loyalty/goals/copy` — Copiar metas entre meses

### 2.8 Validation Rules
Implementadas en `validate_kpi_input()` y `validate_bulk_input()`:
- KPI debe estar en el registry
- Ciudad debe ser Lima, Trujillo o Arequipa
- Mes formato YYYY-MM válido
- Valores no negativos
- Porcentajes (CONV_NEW, CONV_REA, UFC) entre 0-100
- Scores (COMMS, SUPPORT, SOCIAL) entre 0-100
- Detección de duplicados

---

## 3. Workflow Operativo Diario

1. **Inicio de mes:** Copiar metas del mes anterior vía Goal Management > Copiar
2. **Diario:** Ingresar KPIs manuales vía Manual KPI Input
3. **Monitoreo:** Ver Reachability y Daily Snapshot para gaps
4. **Freshness:** Revisar que KPIs manuales estén FRESH (<48h)
5. **Completitud:** Verificar % de datos completos en pestaña Completitud
6. **Histórico:** Revisar evolución de categorías en meses anteriores

---

## 4. Endpoints Nuevos (3A.1)

| Método | Ruta | Descripción |
|--------|------|-------------|
| `GET` | `/yango-loyalty/completeness` | Data completeness por ciudad y global |
| `GET` | `/yango-loyalty/freshness` | Freshness de KPIs manuales |
| `GET` | `/yango-loyalty/daily-snapshot` | Snapshot diario con semáforo |
| `GET` | `/yango-loyalty/historical` | Tracking histórico mensual |
| `POST` | `/yango-loyalty/goals/copy` | Copiar metas entre meses |
| `POST` | `/yango-loyalty/manual-results/bulk` | Bulk input con validación |

---

## 5. Migración

Archivo: `alembic/versions/153_yango_loyalty_operating_layer.py`

Agrega columnas `updated_by` a las 3 tablas existentes.

---

## 6. Frontend

- **Dashboard:** `YangoLoyaltyReachabilityDashboard.jsx` (refactorizado con tabs)
- **Sub-componentes:** `YangoLoyaltyOperatingLayer.jsx`
  - `GoalManagementTable`
  - `ManualKpiInputForm`
  - `DailySnapshotCard`
  - `HistoricalTable`
  - `CompletenessPanel`
- **API functions:** 6 nuevas en `api.js`
- **Navegación:** Performance > Yango Loyalty (sin cambios, tabs internos añadidos)

---

## 7. Limitaciones

1. Freshness se calcula desde `updated_at` del servidor. Si el servidor está en UTC y el usuario en UTC-5, las horas de freshness pueden parecer desfasadas. El cálculo usa UTC consistentemente.
2. No hay notificaciones automáticas de STALE.
3. No hay gráficos de tendencia (charts) — solo tablas.
4. La copia de metas copia todas las metas del mes origen al destino. No permite seleccionar KPIs individuales.
5. Bulk input valida pero no hace rollback parcial — si un ítem falla, ningún ítem se ingresa en la misma request.
6. Solo 3 ciudades soportadas (mismo hardcode que Fase 3A).

---

## 8. Qué NO hace todavía

- NO envía alertas por STALE o WARNING
- NO genera recomendaciones automáticas
- NO crea gráficos de evolución
- NO soporta más de 3 ciudades
- NO tiene integración con fuentes externas (CRM, IVR, Fleetroom)
- NO es un Suggestion Engine

---

## 9. QA

Script: `backend/scripts/validate_phase3a1_loyalty_operating_layer.py`

13 secciones de validación cubriendo tablas, endpoints, completeness, freshness, goals, manual inputs, bulk, snapshot, historical, recomendaciones, Omniview, Plan vs Real, Fase 2.
