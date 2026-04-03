# Auditoría de Fuentes REAL — Q2 2026

**Fecha:** 2026-04-02
**Objetivo:** Inventariar exactamente dónde se usa `trips_all`, `trips_2025` y `trips_2026` en el sistema, clasificar riesgo y prioridad de migración.

---

## Resumen ejecutivo

| Fuente | Archivos con referencia | Estado |
|--------|------------------------|--------|
| `trips_all` | **~150+ archivos** (migraciones, scripts, SQL, servicios, docs) | LEGACY — uso masivo pendiente de migración |
| `trips_2025` | **4 archivos** (migración 118, docs) | OFICIAL — adopción reciente |
| `trips_2026` | **~74 archivos** (migraciones, scripts, servicios, docs) | OFICIAL — uso extendido |

---

## 1. USO PRODUCTIVO REAL de trips_all (RIESGO ALTO)

Estos archivos ejecutan queries **en runtime o en scripts operativos** que leen directamente de `public.trips_all`.

| # | Archivo | Capa | Uso | Riesgo | Acción sugerida |
|---|---------|------|-----|--------|-----------------|
| 1 | `backend/app/services/territory_quality_service.py` | service | `get_unmapped_parks()`: `FROM public.trips_all t` | **ALTO** — Endpoint productivo lee legacy | Migrar a trips_2025 + trips_2026 |
| 2 | `backend/app/adapters/real_repo.py` | adapter | Docstrings mencionan trips_all; `get_ops_universe_data` referencia legacy | MEDIO — Docstring, no SQL directo | Actualizar docstrings |
| 3 | `backend/app/services/data_integrity_service.py` | service | Docstring menciona trips_all | BAJO — Solo docstring | Actualizar docstring |
| 4 | `backend/app/contracts/data_contract.py` | contract | Docstring menciona trips_all | BAJO — Solo docstring | Actualizar docstring |
| 5 | `backend/app/routers/ops.py` | router | Docstring endpoint menciona trips_all | BAJO — Solo docstring | Actualizar docstring |

### Vistas/funciones SQL en BD que dependen de trips_all (via migraciones)

| # | Vista/Objeto SQL | Migración donde se define | Fuente usada | Riesgo | Acción sugerida |
|---|-----------------|--------------------------|-------------|--------|-----------------|
| 1 | `ops.v_trips_real_canon` | 064 | trips_all UNION trips_2026 | **ALTO** — Base de cadena hourly-first | Migrar a trips_2025 + trips_2026 |
| 2 | `ops.v_trips_real_canon_120d` | 064/098 | trips_all UNION trips_2026 (ventana 120d) | **ALTO** — Base de v_real_trip_fact_v2 | Migrar a trips_2025 + trips_2026 |
| 3 | `public.trips_unified` | 054 | trips_all UNION trips_2026 | **ALTO** — Base de driver lifecycle | Migrar a trips_2025 + trips_2026 |
| 4 | `ops.mv_real_trips_monthly` | 005/008/013 | Basada en trips_all | **ALTO** — Usada por Resumen, Plan vs Real, Real vs Proyección | Migrar o deprecar |
| 5 | `ops.mv_real_trips_weekly` | 014 | Basada en trips_all | **ALTO** — Usada por Plan vs Real semanal | Migrar o deprecar |
| 6 | `ops.mv_real_tipo_servicio_fast` | paso3b | trips_all | MEDIO — LOB mapping | Migrar |
| 7 | Índices `idx_trips_all_*` | driver_lifecycle_indexes_and_analyze.sql | Sobre trips_all | BAJO — Performance indexes | Mantener mientras trips_all exista |

---

## 2. USO EN SCRIPTS OPERATIVOS/DIAGNÓSTICO

| # | Script | Propósito | Fuente usada | Riesgo | Acción sugerida |
|---|--------|-----------|-------------|--------|-----------------|
| 1 | `audit_trips_all_real_contract.py` | Auditoría de contrato trips_all | trips_all | BAJO — Script de auditoría | Marcar como legacy o crear versión v2 |
| 2 | `audit_trips_unified_and_driver_lifecycle.py` | Auditoría lifecycle | trips_all + trips_2026 | MEDIO — Diagnóstico | Migrar a trips_2025 |
| 3 | `driver_lifecycle_scan.py` | Scan de lifecycle | trips_all | MEDIO — Diagnóstico | Migrar |
| 4 | `audit_driver_lifecycle_freshness.py` | Freshness lifecycle | trips_all | BAJO — Audit | Migrar |
| 5 | `run_data_freshness_audit.py` | Audit freshness | trips_all + trips_2026 | BAJO — Audit | Migrar referencia |
| 6 | `validate_completed_trips_ticket.py` | Validación ticket | trips_all | MEDIO — Validación | Migrar a trips_2025 |
| 7 | `validate_phase2a_no_proxy.py` | Validación phase2a | trips_all | BAJO — Validación legacy | Mantener como referencia |
| 8 | `validate_phase2b_weekly.py` | Validación semanal | trips_all | BAJO — Validación legacy | Mantener como referencia |
| 9 | `refresh_mv_with_timeout.py` | Refresh MVs | trips_all | **ALTO** — Refresh productivo | Migrar |
| 10 | `investigate_real_rupture_2026.py` | Diagnóstico ruptura | trips_all + trips_2026 | BAJO — Diagnóstico histórico | Mantener como referencia |
| 11 | `explore_trips_structure.py` | Exploración schema | trips_all | BAJO — Exploración | Mantener |
| 12 | `explore_line_of_business_mapping.py` | Exploración LOB | trips_all | BAJO — Exploración | Mantener |
| 13 | `inspect_trips_all_columns.py` | Inspección | trips_all | BAJO — Inspección | Mantener |
| 14 | `inspect_trips_all_schema.py` | Inspección schema | trips_all | BAJO — Inspección | Mantener |
| 15 | `check_real_lob_quality.py` | Calidad LOB | trips_all | MEDIO — Diagnóstico | Migrar |
| 16 | `scan_trips_drivers_parks_schema.py` | Scan schema | trips_all + trips_2026 | BAJO — Scan | Mantener |
| 17 | `pasoA4_validate_and_fix_parks_join.py` | Fix parks | trips_all | MEDIO — Fix operativo | Migrar |
| 18 | `paso3d_fix_export_vacio_e2e.py` | Fix export | trips_all | BAJO — Fix legacy | Mantener |

---

## 3. USO EN SQL OPERATIVO

| # | Archivo SQL | Propósito | Fuente | Riesgo | Acción |
|---|-------------|-----------|--------|--------|--------|
| 1 | `scripts/sql/audit_driver_lifecycle_freshness.sql` | Audit lifecycle | trips_all | BAJO | Migrar |
| 2 | `scripts/sql/validate_data_freshness.sql` | Validación freshness | trips_all + trips_2026 | BAJO | Migrar |
| 3 | `scripts/sql/validate_financials_canonical.sql` | Validación financiera | trips_all | MEDIO | Migrar |
| 4 | `scripts/sql/diagnostic_parks_trips_phase1.sql` | Diagnóstico parks | trips_all | BAJO | Migrar |
| 5 | `scripts/sql/reconcile_real_cancellations.sql` | Reconciliación cancel. | trips_all + trips_2026 | MEDIO | Migrar |
| 6 | `scripts/sql/trips_unified_indexes_concurrent.sql` | Índices trips_all | trips_all + trips_2026 | BAJO | Mantener |
| 7 | `sql/driver_lifecycle_build.sql` | Build lifecycle | trips_all (ref) | MEDIO | Migrar |
| 8 | `sql/driver_lifecycle_validations.sql` | Validación lifecycle | trips_all | BAJO | Migrar |
| 9 | `sql/driver_lifecycle_indexes_and_analyze.sql` | Índices trips_all | trips_all | BAJO | Mantener mientras exista |
| 10 | `sql/paso3b_mv_real_tipo_servicio_fast.sql` | MV tipo servicio | trips_all | MEDIO | Migrar |
| 11 | `sql/phase2b_weekly_checks.sql` | Checks semanales | trips_all | BAJO | Migrar |
| 12 | `exports/fix_real_drill_views.sql` | Fix vistas drill | trips_all | BAJO | Legacy |
| 13 | `scripts/sql/validate_territory_mapping.sql` | Territory mapping | trips_all | MEDIO | Migrar |

---

## 4. USO EN MIGRACIONES ALEMBIC

Las migraciones definen la estructura SQL productiva. Las que crean vistas/MVs basadas en `trips_all`:

| Migración | Objeto creado | Fuente | Estado |
|-----------|--------------|--------|--------|
| 005 | mv_real_trips_monthly_aggregate | trips_all | Legacy activa |
| 008 | consolidate_real_monthly_phase2a | trips_all | Legacy activa |
| 013 | mv_real_trips_monthly_v2_no_proxy | trips_all | Legacy activa |
| 014 | phase2b_weekly_views | trips_all | Legacy activa |
| 054 | trips_unified_view_and_indexes | trips_all + trips_2026 | Legacy activa (lifecycle) |
| 058 | fix_driver_lifecycle_trips_completed | trips_all | Legacy activa |
| 064 | real_lob_trips_canon_and_freshness | trips_all + trips_2026 | Legacy activa (canon) |
| 072 | data_freshness_audit | trips_all | Legacy referencia |
| 075 | control_tower_data_observability | trips_all + trips_2026 | Legacy activa |
| 098 | real_lob_root_cause_120d_views | trips_all + trips_2026 | Legacy activa |
| 099 | real_hourly_first_architecture | trips_all + trips_2026 | Legacy activa |
| 107 | real_monthly_canonical_hist_mv | trips_all + trips_2026 | Legacy activa |
| 111 | business_slice_phase1 | trips_all + trips_2026 | **MIGRADA en 118** |
| 113 | business_slice_enriched_pipeline | trips_all + trips_2026 | **MIGRADA en 118** |
| 116 | business_slice_incremental_facts | trips_all + trips_2026 | **MIGRADA en 118** |
| **118** | **enriched_base_trips_2025_2026** | **trips_2025 + trips_2026** | **OFICIAL** |

---

## 5. USO EN DOCUMENTACIÓN

~48 archivos `.md` en `docs/` mencionan `trips_all`. Estos son documentales y no afectan runtime. Los más relevantes:

| Documento | Tipo | Estado |
|-----------|------|--------|
| `SOURCE_OF_TRUTH_REAL_AUDIT_V2.md` | Definición oficial | **CREADO — alineado** |
| `source_dataset_policy.md` | Política datasets | **ACTUALIZADO — alineado** |
| `real_trip_source_contract.md` | Contrato fuente | **ACTUALIZADO — alineado** |
| `REAL_CANCELACIONES_ESTRUCTURAL.md` | Semántica cancelaciones | Menciona trips_all como fuente histórica — aceptable |
| `CONTROL_TOWER_SOURCE_OF_TRUTH_AUDIT.md` | Auditoría SOT | Referencia trips_all vía cadenas — documentación de estado |
| `BUSINESS_SLICE_DAILY_WEEKLY_OPS.md` | Guía Business Slice | Ya documenta trips_2025 + trips_2026 — **alineado** |
| Otros ~42 docs | Varios | Referencia histórica/contextual — no requieren actualización urgente |

---

## 6. Cadenas contaminadas por trips_all (resumen de riesgo)

| Cadena | Último eslabón que toca trips_all | Pantallas afectadas | Prioridad migración |
|--------|----------------------------------|--------------------|--------------------|
| Hourly-first (v_trips_real_canon_120d) | Vista canon_120d (mig 064/098) | Performance > Real, Operación > Drill | **P1 — CRÍTICA** |
| Legacy mensual (mv_real_trips_monthly) | MV refresh desde trips_all (mig 005/008/013) | Resumen, Plan vs Real, Real vs Proyección | **P1 — CRÍTICA** |
| Legacy semanal (mv_real_trips_weekly) | MV refresh desde trips_all (mig 014) | Plan vs Real semanal | **P2 — ALTA** |
| Driver lifecycle (trips_unified) | Vista trips_unified (mig 054) | Drivers > Ciclo de vida | **P2 — ALTA** |
| Territory quality | Query directa en service | Endpoint /ops/territory/* | **P1 — SIMPLE** (1 archivo) |
| Business Slice | **YA MIGRADA** (mig 118) | Business Slice views | **CERRADA** |

---

## 7. Hallazgo explícito

**¿Qué parte del sistema seguiría contaminada si no hacemos migración posterior?**

1. **Todas las pantallas que consumen cadena hourly-first** (Performance > Real diario, Operación > Drill) seguirán leyendo de `v_trips_real_canon_120d` que une `trips_all + trips_2026`. Si `trips_all` se deja de actualizar o tiene datos inconsistentes, estas pantallas podrían mostrar datos incorrectos para el período histórico.

2. **Resumen, Plan vs Real y Real vs Proyección** dependen de `mv_real_trips_monthly` que se construyó históricamente desde `trips_all`. Si no se migran, el revenue, avg_ticket y active_drivers de 2025 podrían ser incorrectos o incompletos.

3. **Driver Lifecycle** usa `trips_unified` (trips_all ∪ trips_2026). Métricas de lifecycle para 2025 dependen de trips_all.

4. **Territory quality service** hace una query directa a `trips_all` para encontrar parks unmapped. Es el caso más simple de migrar (1 archivo, 1 query).

---

## 8. Puntos que pueden quedar como compatibilidad temporal

| Punto | Justificación |
|-------|--------------|
| Scripts de inspección/exploración (`inspect_*.py`, `explore_*.py`) | No afectan producción; útiles como referencia histórica |
| Migraciones Alembic históricas | No se deben modificar migraciones pasadas; la corrección se hace con nuevas migraciones |
| Índices sobre trips_all | Necesarios mientras la tabla exista; se eliminan cuando se deprece |
| Documentación histórica que menciona trips_all como contexto | No confunde si la definición oficial está clara en SOURCE_OF_TRUTH_REAL_AUDIT_V2.md |

---

## 9. Lista priorizada de migración posterior

| Prioridad | Acción | Complejidad | Impacto |
|-----------|--------|-------------|---------|
| P1 | Migrar `territory_quality_service.py` a trips_2025 + trips_2026 | BAJA | Endpoint productivo |
| P1 | Nueva migración: recrear `v_trips_real_canon_120d` con trips_2025 + trips_2026 | MEDIA | Base de cadena hourly-first |
| P1 | Nueva migración: recrear `mv_real_trips_monthly` con trips_2025 + trips_2026 | MEDIA-ALTA | Resumen, Plan vs Real |
| P2 | Nueva migración: recrear `trips_unified` con trips_2025 + trips_2026 | MEDIA | Driver lifecycle |
| P2 | Nueva migración: recrear `mv_real_trips_weekly` con trips_2025 + trips_2026 | MEDIA | Plan vs Real semanal |
| P3 | Actualizar docstrings en adapters/services/contracts | BAJA | Claridad |
| P3 | Actualizar scripts de diagnóstico a trips_2025 + trips_2026 | BAJA | Herramientas internas |
