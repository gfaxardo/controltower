# LG_GOV_1A_ORPHAN_WRITER_AUDIT — Orphan Writer Audit

**Generated:** 2026-06-12T20:45  
**Scope:** Identificar el writer exacto de `driver_movement_fact` y `yego_lima_driver_taxonomy_v2_daily`  
**Veredicto:** `ORPHAN_TABLE_CONFIRMED`

---

## 1. EVIDENCIA FORENSE

### 1.1 `growth.driver_movement_fact`

| Atributo | Valor |
|----------|-------|
| **Total rows** | 68,473 |
| **Fechas con datos** | SOLO 1 fecha: **2026-06-10** (68,473 rows) |
| **0 rows para** | 2026-06-11, 2026-06-12 |
| **Columnas** | id (uuid), driver_profile_id, movement_date, from_lifecycle, to_lifecycle, from_segment, to_segment, from_program, to_program, movement_class, movement_score, changed_layers_json, created_at |
| **Table comment** | Ninguno |
| **Creada por migración** | **NINGUNA.** Cero referencias en `alembic/versions/` |

**Búsqueda exhaustiva de writers:**

| Tipo de búsqueda | Alcance | Resultados |
|-----------------|--------|-----------|
| `INSERT INTO` | Todo el repo (.py, .sql, .sh, .ps1, .js) | **0 encontrados** |
| `DELETE FROM` | Todo el repo | **0 encontrados** |
| `UPDATE` | Todo el repo | **0 encontrados** |
| `MERGE` / `UPSERT` | Todo el repo | **0 encontrados** |
| `COPY` / `\copy` | Todo el repo | **0 encontrados** |
| `CREATE TABLE AS` | Todo el repo | **0 encontrados** |
| Referencia en scripts | `backend/scripts/` | Solo LECTURA (`imp_1b_stability.py`) |
| Referencia en servicios | `backend/app/services/` | Solo LECTURA (movement_analytics, effectiveness, rna_priority) |
| Referencia en scheduler | `yego_lima_scheduler_service.py` | **0 referencias** |
| Referencia en V2 pipeline | `yego_lima_v2_daily_pipeline_service.py` | Escribe a `yego_lima_v2_movement_fact` (tabla DIFERENTE) |
| Referencia en main.py | Líneas 280-423 (APScheduler) | **0 referencias** |
| Archivos .sql | Todo el repo | **0 archivos .sql encontrados** |
| Migraciones Alembic | `alembic/versions/` | **0 referencias** |

---

### 1.2 `growth.yego_lima_driver_taxonomy_v2_daily`

| Atributo | Valor |
|----------|-------|
| **Total rows** | 273,908 |
| **Fechas con datos** | 4 fechas: 2026-06-07 (68,479), 06-08 (68,479), 06-09 (68,477), **06-10 (68,473)** |
| **0 rows para** | 2026-06-11, 2026-06-12 |
| **Columnas** | id (uuid), snapshot_date, park_id, driver_profile_id, lifecycle_status, activity_status, value_tier, momentum_state, ... |
| **Table comment** | Ninguno |
| **Migración 202** | **PLACEHOLDER VACÍO.** `upgrade(): pass` — no crea nada. |

**Búsqueda exhaustiva de writers:**

| Tipo de búsqueda | Alcance | Resultados |
|-----------------|--------|-----------|
| `INSERT INTO` | Todo el repo | **0 encontrados** |
| `DELETE FROM` | Todo el repo | **0 encontrados** |
| `UPDATE` | Todo el repo | **0 encontrados** |
| `MERGE` / `UPSERT` | Todo el repo | **0 encontrados** |
| `COPY` / `\copy` | Todo el repo | **0 encontrados** |
| `CREATE TABLE AS` | Todo el repo | **0 encontrados** |
| Referencia en servicios | `backend/app/services/` | Solo LECTURA (explainability, export, rna_priority) |
| Referencia en V2 pipeline | `yego_lima_v2_daily_pipeline_service.py` | Escribe a `yego_lima_v2_taxonomy_daily` (tabla DIFERENTE) |
| Referencia en taxonomy service | `yego_lima_taxonomy_service.py` | Escribe a `yego_lima_driver_taxonomy_daily` (V1, tabla DIFERENTE) |
| Migraciones Alembic | 202 | `pass` — placeholder vacío |

---

## 2. QUIÉN POBLÓ LOS DATOS DEL 2026-06-10

### Hipótesis evaluadas:

| Hipótesis | Evidencia | Veredicto |
|-----------|-----------|-----------|
| **V2 Shadow Pipeline** (cron 04:45) | Escribe a `yego_lima_v2_*` (shadow), NO a `driver_movement_fact` ni `driver_taxonomy_v2_daily` | ❌ FALSO |
| **autonomous_tick** (cada 5 min) | No referencia ninguna de las dos tablas. Solo escribe snapshot, eligibility, opportunities, queue. | ❌ FALSO |
| **run_daily_refresh** | Solo 5 pasos: detect_date, validate, queue, opportunities, serving_facts. No incluye movement ni taxonomy. | ❌ FALSO |
| **Script Python del repo** | Ningún script hace INSERT. Solo READ. | ❌ FALSO |
| **Migración Alembic** | Migración 202 es placeholder vacío. `driver_movement_fact` no tiene migración asociada. | ❌ FALSO |
| **SQL file** | No hay archivos .sql en el repo. | ❌ FALSO |
| **ETL externo / script no versionado** | Datos existen en DB. Coinciden con el patrón del V2 pipeline (misma estructura de columnas, mismo conteo por fecha que `lifecycle_daily`). | ✅ **ÚNICA EXPLICACIÓN** |

### Evidencia del patrón:

Ambas tablas comparten el mismo patrón de fechas que `yego_lima_driver_lifecycle_daily`:

```
Tabla                           06-07    06-08    06-09    06-10    Total
──────────────────────────────  ──────   ──────   ──────   ──────   ──────
yego_lima_driver_lifecycle_daily  68,479  68,479   68,477   68,473   273,908
yego_lima_driver_taxonomy_v2_daily 68,479 68,479   68,477   68,473   273,908
driver_movement_fact                  —       —        —    68,473    68,473
```

**Conclusión:** Un proceso externo (script SQL directo, ETL no versionado, o intervención manual DBA) pobló estas tablas el o antes del 2026-06-11, usando como fuente `yego_lima_driver_lifecycle_daily` (que a su vez fue poblada por `POST /lifecycle/build`). El proceso generó:
- 4 fechas de taxonomy_v2 (06-07 a 06-10), 68,479 ± 2 rows/día
- 1 fecha de movement_fact (06-10), 68,473 rows

Este proceso NO está versionado en el repositorio.

---

## 3. CLASIFICACIÓN FINAL

| Tabla | Clasificación | Definición |
|-------|--------------|-----------|
| `growth.driver_movement_fact` | **ORPHAN_TABLE** | Tabla existe con datos. Tiene readers (3 servicios). Pero NO tiene writer conocido en el código, NO tiene scheduler, NO fue creada por migración, NO tiene archivo SQL de población. |
| `growth.yego_lima_driver_taxonomy_v2_daily` | **ORPHAN_TABLE** | Tabla existe con datos (273K rows). Tiene readers (3 servicios). Pero NO tiene writer conocido en el código, NO tiene scheduler, la migración 202 es un placeholder vacío. |

**Ambas son `ORPHAN_TABLE`.**

---

## 4. CONSECUENCIAS

### Sin writer conocido:

1. **Nadie regenera los datos automáticamente.** Cuando `lifecycle_daily` se actualice, taxonomy_v2 y movement_fact NO se actualizarán porque su writer está fuera del repo.

2. **El V2 pipeline cron 04:45 escribe a shadow tables diferentes** (`yego_lima_v2_taxonomy_daily`, `yego_lima_v2_movement_fact`). Estas shadow tables NO son consumidas por UI1A. El pipeline gasta recursos produciendo datos huérfanos.

3. **UI1A lee de las tablas huérfanas**, no de las shadow:
   - Segments tab → lee `yego_lima_driver_taxonomy_daily` (V1, 18K)
   - Movement stats/matrix → lee `driver_movement_fact` (orphan, 68K)
   - Movement winners/losers → lee `yego_lima_v2_movement_fact` (V2 shadow, 0 rows)
   - RNA priority → lee `yego_lima_driver_taxonomy_v2_daily` (orphan) + `rna_priority_fact` (no existe)

4. **El gap de 06-11/12 es permanente hasta que se ejecute el writer externo.** No hay nada en el scheduler que pueda cerrarlo.

---

## 5. DIAGRAMA DE ORFANDAD

```
PROCESS EXTERNO (no versionado)
  │
  ├──► growth.yego_lima_driver_taxonomy_v2_daily  ←── UI1A (explainability, export, rna)
  │      └─ readers: explainability_service, export_service, rna_priority_service
  │      └─ writer: DESCONOCIDO
  │      └─ scheduler: NINGUNO
  │
  └──► growth.driver_movement_fact               ←── UI1A (movement stats, matrix)
         └─ readers: movement_analytics_service, effectiveness_service, rna_priority_service
         └─ writer: DESCONOCIDO
         └─ scheduler: NINGUNO

V2 SHADOW PIPELINE (04:45 cron)
  │
  ├──► growth.yego_lima_v2_taxonomy_daily        ←── SIN CONSUMIDOR UI1A
  └──► growth.yego_lima_v2_movement_fact         ←── UI1A winners/losers (0 rows → 500)

TAXONOMY SERVICE (manual API)
  │
  └──► growth.yego_lima_driver_taxonomy_daily    ←── UI1A Segments tab (V1 legacy, 18K)
```

---

## 6. VEREDICTO

```
ORPHAN_TABLE_CONFIRMED
```

**Ambas tablas son huérfanas.** No tienen writer en el código Python del repositorio, ni en migraciones Alembic, ni en scripts, ni en schedulers, ni en archivos SQL. Fueron pobladas por un proceso externo no versionado.

**Evidencia irrefutable:**
1. Cero INSERT/DELETE/UPDATE/MERGE/COPY en todo el código para ambas tablas
2. Migración 202 (`yego_lima_driver_taxonomy_v2_daily`) es un `pass` vacío
3. `driver_movement_fact` no tiene migración de creación en absoluto
4. El scheduler `autonomous_tick` y `run_daily_refresh` no referencian ninguna de las dos tablas
5. El V2 shadow pipeline escribe a tablas diferentes (con prefijo `v2_`)
6. Los scripts solo leen, nunca escriben

**Recomendación para LG-FIX-1B.2:** Si estas tablas son las fuentes canónicas, se debe crear un writer versionado en el código Python del backend, integrarlo al `autonomous_tick` o al `run_daily_refresh`, y eliminar la dependencia del proceso externo no versionado. Alternativamente, migrar los readers de UI1A a consumir las tablas V2 shadow que SÍ tienen writer versionado (V2 pipeline).
