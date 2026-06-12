# LG_GOV_1B_HISTORICAL_OWNERSHIP_AUDIT — Historical Ownership Audit

**Generated:** 2026-06-12T21:00  
**Scope:** Determinar el origen histórico real de `driver_movement_fact` y `yego_lima_driver_taxonomy_v2_daily`  
**Veredicto:** `EXTERNAL_ETL_CONFIRMED`

---

## 1. METODOLOGÍA

Búsqueda forense completa en el historial de git:

| Método | Alcance | Resultado |
|--------|---------|-----------|
| `git log --all --grep` | Commits que mencionan las tablas | **0 commits** |
| `git log --all --diff-filter=A` | Archivos creados con esos nombres | **0 archivos** |
| `git log --all -p -- "*"` | Contenido completo de todos los commits | Solo lecturas |
| `git branch -a` | Todas las ramas (local + remoto) | Solo `master` y `main` (son la misma) |
| `git log --all --oneline` | Commits totales en el repo | ~100 commits desde 2025-11-11 |
| `git diff` entre commits clave | Cambios entre versiones | Sin INSERTs eliminados |
| Búsqueda en docs históricas | `docs/lima_growth/` y certificaciones | Solo referencias de lectura |

---

## 2. TIMELINE HISTÓRICO

```
2025-11-11  d84f9e5   Primer commit del repositorio
                       └─ Omniview V1, Business Slice, Drivers, Plan vs Real
                       └─ Sin Lima Growth. Sin taxonomy. Sin movement.

2026-01 ~ 2026-05      Commits de hardening y features de Drivers, Performance,
                       Yango Loyalty, Omniview V1. Sin Lima Growth.

2026-06-04  1c05ad5   feat(yego-lima-growth): Fase 0 + Fase 1
                       └─ Yango Orders API discovery + raw orders capture
                       └─ Primer commit de Lima Growth. Sin taxonomy ni movement.

2026-06-05  20a5345   Fases 2B-2D: Lima Growth Engine completo
                       └─ Loyalty Sub-50, Bootstrap, Segmentation, Control Loop
                       └─ Impact Attribution, Pipeline Orchestrator
                       └─ Sin taxonomy_v2_daily, sin movement_fact.

2026-06-09  8302e81   LG-R2 series: Queue, Action Plan, UX, Scheduler
                       └─ autonomous_tick implementado (cada 5 min)
                       └─ run_daily_refresh implementado (queue + opportunities)
                       └─ Sin taxonomy_v2_daily, sin movement_fact en código.

2026-06-10  9e8aece   OV2-CLOSE.5: Lima Growth + governance + services
            ~         └─ Fecha del último dato en las tablas huérfanas.
            ~         └─ Proceso externo puebla lifecycle_daily, taxonomy_v2_daily,
            ~            movement_fact con datos para fechas 06-07 a 06-10.

2026-06-11  2303185   Control Foundation: CF-H2 phases E through H
  19:50               └─ PRIMERA APARICIÓN en código de:
                         • migration 202 (placeholder vacío para taxonomy_v2)
                         • yego_lima_v2_daily_pipeline_service.py (V2 shadow pipeline)
                         • yego_lima_taxonomy_service.py (lector de V1 taxonomy)
                         • yego_lima_lifecycle_service.py (API manual para lifecycle)
                         • yego_lima_export_service.py (lector de taxonomy_v2_daily)
                         • yego_lima_explainability_service.py (lector de taxonomy_v2_daily)
                      └─ TODOS son LECTORES. Ninguno escribe a las tablas huérfanas.
                      └─ V2 pipeline escribe a yego_lima_v2_* (SHADOW), no a producción.

2026-06-11  POST-COMMIT: V2 pipeline ejecutado MANUALMENTE 12 veces
  19:50-20:56          └─ triggered_by="certification", "multi-day-replay"
                       └─ target_dates: 06-07 a 06-10
                       └─ Pobló tablas V2 SHADOW (yego_lima_v2_*)
                       └─ NO tocó driver_movement_fact ni taxonomy_v2_daily

2026-06-12  c8dc41d   CF-H2E + OV2-MVP
  09:21               └─ PRIMERA APARICIÓN en código de:
                         • yego_lima_movement_analytics_service.py (lector)
                         • yego_lima_effectiveness_service.py (lector)
                         • yego_lima_rna_priority_service.py (lector)
                      └─ movement_analytics: TABLE_MOV = "growth.driver_movement_fact"
                      └─ effectiveness: TABLE_EFF = "growth.program_effectiveness_fact"
                      └─ rna_priority: TABLE_TAX = "growth.yego_lima_driver_taxonomy_v2_daily"
                      └─ TODOS SON LECTORES.

2026-06-12  04:45     V2 shadow pipeline NO CORRIÓ (sin logs)
  19:36               └─ Auditoría LG-FIX-1A detecta el problema
```

---

## 3. ¿QUIÉN CREÓ LAS TABLAS?

### `growth.driver_movement_fact`

- **NO fue creada por migración Alembic.** Cero referencias en `alembic/versions/`.
- **NO fue creada por ningún commit.** El archivo no aparece en `git log --diff-filter=A`.
- **Aparece por primera vez en código** el 2026-06-12 (commit `c8dc41d`) como `TABLE_MOV = "growth.driver_movement_fact"` en `yego_lima_movement_analytics_service.py`.
- **Ya tenía 68,473 rows** cuando el código la referenció por primera vez.
- **Fue creada externamente**, probablemente con un `CREATE TABLE` directo en PostgreSQL y poblada con un script SQL no versionado.

### `growth.yego_lima_driver_taxonomy_v2_daily`

- **Migración 202** (`alembic/versions/202_yego_lima_taxonomy_v2.py`) es un **placeholder vacío**:
  ```python
  def upgrade():
      pass  # No crea nada.
  ```
- **La tabla fue creada externamente**, ya sea por:
  - Un `CREATE TABLE` directo en la DB antes de escribir la migración
  - Un script SQL no versionado
  - Un ORM o herramienta de migración externa

---

## 4. ¿CUÁL ERA EL WRITER ORIGINAL?

**No hubo writer original en este repositorio.**

El código NUNCA contuvo INSERT, UPDATE, DELETE, MERGE, COPY, o CREATE TABLE AS para ninguna de las dos tablas. La búsqueda exhaustiva en TODO el historial de git (100+ commits, desde 2025-11-11) no encontró ningún writer.

### Hipótesis sobre cómo se poblaron:

Los datos comparten el **mismo patrón de fechas y row counts** que `yego_lima_driver_lifecycle_daily`:

```
Tabla                                 06-07    06-08    06-09    06-10
yego_lima_driver_lifecycle_daily      68,479   68,479   68,477   68,473
yego_lima_driver_taxonomy_v2_daily    68,479   68,479   68,477   68,473
driver_movement_fact                     —        —        —     68,473
```

**Explicación más probable:** Un script SQL externo (ejecutado directamente contra la DB, no versionado en git) realizó:

```sql
-- Paso 1: Clasificar drivers (taxonomy)
INSERT INTO growth.yego_lima_driver_taxonomy_v2_daily
SELECT ... FROM growth.yego_lima_driver_lifecycle_daily lc
WHERE lc.snapshot_date IN ('2026-06-07','2026-06-08','2026-06-09','2026-06-10');

-- Paso 2: Calcular movimientos entre fechas
INSERT INTO growth.driver_movement_fact
SELECT ... FROM growth.yego_lima_driver_taxonomy_v2_daily t1
JOIN growth.yego_lima_driver_taxonomy_v2_daily t2 ON ...
WHERE t1.snapshot_date = '2026-06-09' AND t2.snapshot_date = '2026-06-10';
```

Este script se ejecutó una sola vez (para fechas 06-07 a 06-10) y nunca se volvió a ejecutar, ni se versionó en el repositorio.

---

## 5. ¿CUÁNDO DESAPARECIÓ EL WRITER?

**Nunca desapareció — nunca existió en este repositorio.**

No hay evidencia de:
- Commits que eliminen INSERTs
- Archivos borrados que contuvieran writers
- Ramas alternativas con código diferente
- Migraciones revertidas

El writer fue un proceso externo (SQL directo, ETL, DBA manual) que nunca se integró al código versionado.

---

## 6. ¿POR QUÉ DESAPARECIÓ?

**No desapareció — nunca se integró.**

La secuencia de eventos sugiere:

1. **2026-06-10 o antes:** Un DBA o data engineer ejecuta un script SQL para poblar lifecycle_daily, taxonomy_v2_daily, y movement_fact con datos históricos (06-07 a 06-10). Esto es típico en fases de "bootstrap" o "certificación" donde se necesita datos para validar el sistema.

2. **2026-06-11:** El equipo de desarrollo escribe los servicios lectores (movement_analytics, effectiveness, rna_priority, explainability, export) que consumen estas tablas. Asumen que los datos se seguirán generando.

3. **2026-06-11 ~19:50:** El equipo ejecuta el V2 shadow pipeline manualmente 12 veces para certificar que funciona (triggered_by="certification", "multi-day-replay"). Este pipeline escribe a las tablas SHADOW (`yego_lima_v2_*`), NO a las tablas de producción.

4. **2026-06-12:** El equipo hace deploy del código. El scheduler automático (`autonomous_tick`) corre cada 5 minutos pero solo construye la capa operacional (snapshot, eligibility, queue). **Nadie programa el paso de poblar las tablas de inteligencia (lifecycle, taxonomy, movement).**

5. **El writer externo nunca se integró al scheduler.** El `autonomous_tick` y `run_daily_refresh` no incluyen builders de lifecycle/taxonomy/movement. Las tablas quedan congeladas en 2026-06-10.

---

## 7. CLASIFICACIÓN

```
EXTERNAL_ETL_CONFIRMED
```

| Criterio | Evidencia |
|----------|-----------|
| **Writer encontrado en código** | NO — cero INSERTs en todo el historial |
| **Writer encontrado en migraciones** | NO — migración 202 es placeholder vacío |
| **Writer encontrado en scripts** | NO — scripts solo leen |
| **Writer encontrado en branches** | NO — solo master/main |
| **Writer encontrado en archivos borrados** | NO — git log no muestra eliminaciones relevantes |
| **Tablas ya existían antes del código** | SÍ — datos de 06-10 vs código de 06-11 |
| **Patrón de datos coincide con ETL externo** | SÍ — mismas fechas y row counts que lifecycle_daily |
| **Proceso de población fue one-time** | SÍ — solo 4 fechas (06-07 a 06-10), nunca más |

**Las tablas fueron pobladas por un proceso ETL externo (script SQL directo contra la DB) que nunca se versionó ni se integró al scheduler automático.**

---

## 8. CONSECUENCIAS

1. **Sin writer versionado, estas tablas nunca se actualizarán automáticamente.** Cada día que pasa sin intervención manual, el gap de datos crece.

2. **El V2 shadow pipeline escribe a tablas diferentes** (`yego_lima_v2_*`) que no son las que la UI1A consume. Hay un desacople entre productor (V2 pipeline → shadow) y consumidor (UI1A → production).

3. **El bootstrap inicial fue incompleto.** Se poblaron las tablas de producción con datos de prueba/certificación (06-07 a 06-10), se escribió el código lector, pero nunca se escribió el código escritor.

4. **La documentación (`LG_SERV_2A_WRITER_GOVERNANCE.md`) es incorrecta.** Afirma que `autonomous_tick` escribe estas tablas, lo cual es falso. El documento fue escrito asumiendo una integración que nunca ocurrió.

---

## 9. RECOMENDACIÓN

Para cerrar el gap de ownership, se debe:

1. **Escribir el writer versionado** para `yego_lima_driver_taxonomy_v2_daily` y `driver_movement_fact` dentro del código Python del backend.

2. **Integrar al `autonomous_tick`** los pasos:
   - `build_lifecycle_daily()` → escribe `yego_lima_driver_lifecycle_daily`
   - `build_taxonomy_v2_daily()` → escribe `yego_lima_driver_taxonomy_v2_daily`
   - `build_movement_fact()` → escribe `driver_movement_fact`

3. **O alternativamente:** migrar los consumidores de UI1A a leer de las tablas V2 shadow (`yego_lima_v2_*`) que SÍ tienen writer versionado (V2 pipeline 04:45).

4. **Ejecutar backfill** para 2026-06-11 y 2026-06-12 una vez el writer esté integrado.

5. **Corregir `LG_SERV_2A_WRITER_GOVERNANCE.md`** para reflejar el estado real.
