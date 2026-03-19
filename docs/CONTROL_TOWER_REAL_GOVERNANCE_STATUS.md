# Control Tower — Estado de gobierno REAL

**Objetivo:** Dejar claro qué pantallas son canónicas, cuáles legacy/migrando y cuáles en revisión, y cómo se navega.  
**Insumo:** Auditoría `CONTROL_TOWER_SOURCE_OF_TRUTH_AUDIT.md`, plan `CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md`, informe Fase 1 `CONTROL_TOWER_REAL_CANONICALIZATION_PHASE1_REPORT.md`.

---

## 1. Pantallas canónicas (fuente hourly-first)

| Pantalla | Ruta | Estado UI | Notas |
|----------|------|-----------|--------|
| Performance > Real (diario) | Performance → Real (diario) | **canonical** (verde) | mv_real_lob_day_v2 / hour_v2 |
| Operación > Drill | Operación | **canonical** (verde) | real_drill_dim_fact, real_rollup_day_fact |
| Drivers > Supply | Drivers → Supply | Canonical para su dominio | No es cadena REAL de viajes; es supply. |
| Drivers > Ciclo de vida | Drivers → Ciclo de vida | Canonical para su dominio | Fuente propia lifecycle. |

---

## 2. Pantallas legacy / migrando

| Pantalla | Ruta | Estado UI | Notas |
|----------|------|-----------|--------|
| Performance > Resumen | Performance → Resumen | **migrating** (ámbar) | Lee legacy (mv_real_trips_monthly). Paridad Fase 1 bloqueada. |
| Performance > Plan vs Real | Performance → Plan vs Real | **migrating** (ámbar) | Legacy (v_plan_vs_real_*, mv_real_trips_*). Siguiente migración tras cerrar Fase 1. |

---

## 3. Pantallas en revisión o incompletas

| Pantalla | Ruta | Estado UI | Notas |
|----------|------|-----------|--------|
| Real vs Proyección | **En revisión** → Real vs Proyección | **source_incomplete** (rojo) | Vista limitada; puede depender de objetos faltantes. Sacada de navegación principal. |
| Alertas de conducta | **En revisión** → Alertas de conducta | **under_review** (rojo) | Tiempos de respuesta pueden ser elevados. Sacada de Riesgo principal. |
| Fuga de flota | **En revisión** → Fuga de flota | **under_review** (rojo) | Validar estabilidad en runtime. Sacada de Riesgo principal. |

---

## 4. Reglas de navegación principal

- **Flujo principal (confiable):** Performance (Resumen, Plan vs Real, Real diario), Drivers (Supply, Ciclo de vida), Riesgo (Desviación por ventanas, Acciones recomendadas), Operación (Drill), Plan.
- **En revisión:** Tab dedicado "En revisión" con Real vs Proyección, Alertas de conducta y Fuga de flota. No se eliminan; se exponen con aviso claro y fuera del flujo principal.
- **Proyección:** Ya no es tab principal; el contenido Real vs Proyección está solo bajo "En revisión".

---

## 5. Política de nuevos consumidores

- **NEW REAL CONSUMERS MUST USE CANONICAL HOURLY-FIRST ONLY.**
- No añadir nuevos consumidores a: `ops.mv_real_trips_monthly`, `ops.mv_real_trips_weekly`, `ops.mv_real_trips_by_lob_*`, `ops.v_real_metrics_monthly`, vistas plan-vs-real que lean de esas MVs.
- Nuevas features que necesiten datos REAL: usar `real_drill_dim_fact`, `real_rollup_day_fact`, `mv_real_lob_day_v2` / `hour_v2`, o APIs que lean de ellos. Ver `REAL_CANONICAL_CHAIN.md` y `CONTROL_TOWER_REAL_CANONICALIZATION_PLAN.md`.

---

## 6. Colores y estados (UI)

| Estado | Color | Uso |
|--------|--------|-----|
| canonical | Verde | Fuente canónica |
| legacy / migrating | Ámbar | Legacy o en migración |
| data_in_progress / data_missing | Gris | Datos en proceso o faltantes |
| source_incomplete / under_review | Rojo | Vista limitada o en revisión |

---

## 7. Endpoint de estado

`GET /ops/real-source-status` devuelve por pantalla: `screen_id`, `screen_name`, `source_status`, `message`.  
El frontend usa este endpoint (o valor fijo cuando aplica) para mostrar `DataStateBadge` en cada pantalla REAL relevante.

---

## 7.1 Registry y Confidence Engine (gobierno central)

- **Source of Truth Registry:** `app.config.source_of_truth_registry` — define qué fuente manda por dominio (real_lob, resumen, plan_vs_real, supply, driver_lifecycle, etc.). Ninguna vista nueva debe salir a UI sin estar registrada. Ver `docs/SOURCE_OF_TRUTH_REGISTRY.md`.
- **Confidence Engine:** `app.services.confidence_engine` — calcula freshness, completeness, consistency y confidence_score (0–100); Data Trust delega aquí. Observabilidad: `GET /ops/data-confidence?view=...`, `GET /ops/data-confidence/registry`, `GET /ops/data-confidence/summary`. Ver `docs/CONFIDENCE_ENGINE.md`.

---

## 8. Checklist visual por pantalla

| Pantalla | Badge/estado | Color |
|----------|----------------|--------|
| Performance > Resumen | Migrando a fuente canónica | Ámbar |
| Performance > Real (diario) | Fuente canónica | Verde |
| Operación > Drill | Fuente canónica | Verde |
| Performance > Plan vs Real | Migrando a fuente canónica | Ámbar |
| En revisión > Real vs Proyección | Vista temporalmente limitada | Rojo |
| En revisión > Alertas de conducta | En revisión | Rojo |
| En revisión > Fuga de flota | En revisión | Rojo |

Ninguna pantalla REAL queda sin estado explícito. Las pantallas source_incomplete / under_review muestran mensaje corto y no aparentan 0 como dato real.

---

## 9. Veredicto

**REAL_GOVERNANCE_APPLIED**

- Estado visual obligatorio aplicado en las pantallas indicadas.
- Navegación principal limpiada: Real vs Proyección, Alertas de conducta y Fuga de flota bajo "En revisión".
- Política de nuevos consumidores documentada (NEW REAL CONSUMERS MUST USE CANONICAL ONLY).
- Badges y fallbacks endurecidos; no se ha tocado batch ni legacy físico.

---

## 10. Última actualización

Aplicado en el marco de gobernanza REAL y contención de legacy. Paridad Fase 1 sigue bloqueada; no se ha borrado legacy físico. Navegación principal ajustada para no exponer como confiables las pantallas en revisión.
