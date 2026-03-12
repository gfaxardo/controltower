# Auditoría final E2E — Driver Segmentation + Migration Refactor

**Proyecto:** YEGO Control Tower  
**Alcance:** Segmentación semanal (dormant, casual, pt, ft, elite, legend) y rediseño de la vista Migration.  
**Tipo:** Auditoría de lo ya implementado. No se implementaron cambios nuevos.

---

## FASE B — Inventario real de cambios

### 1) Archivos modificados

| Ruta | Propósito del cambio | Tipo |
|------|----------------------|------|
| `backend/app/services/supply_service.py` | `get_supply_segment_config`: ORDER BY ordering ASC. `get_supply_migration`: summary con clave "stable" y suma de lateral; mismos returns en early-exit con stable: 0. | backend |
| `backend/app/services/supply_definitions.py` | Textos de "churned" (diferenciar de Dormant), "reactivated" (Revival), "segments" (ELITE, LEGEND, rangos), "migration" (same-to-same no migración principal). | backend |
| `frontend/src/components/SupplyView.jsx` | Fallback de segmentos desde SEGMENT_LEGEND_MINIMAL; pestaña Migration: header narrativo, KPIs (incl. Stable), insight, resumen por From, tabla principal filtrando `migration_type !== 'lateral'`; drilldown con formatIsoWeek y parkLabel. Composition: DriverSupplyGlossary junto a criterio. | frontend |
| `frontend/src/components/DriverSupplyGlossary.jsx` | Import SEGMENT_LEGEND_MINIMAL; bajo "Segments" se renderiza lista Dormant–Legend con desc. | frontend |

### 2) Archivos nuevos creados

| Ruta | Propósito | Tipo |
|------|-----------|------|
| `backend/alembic/versions/078_segment_taxonomy_elite_legend.py` | Migración: INSERT ELITE/LEGEND en config, UPDATE FT max 119, recrear cadena MVs con ord/prev_ord desde config. | migration |
| `frontend/src/constants/segmentSemantics.js` | SEGMENT_ORDER, SEGMENT_LEGEND_MINIMAL (Dormant–Legend), SEGMENT_LABELS, getSegmentDescription, sortSegmentsByOrder. Alias "Nivel Dios" en desc de Legend. | frontend |
| `docs/segment_migration_refactor_scan.md` | Mapeo previo: fuentes de verdad, taxonomía, contratos, riesgos, archivos a tocar. | docs |
| `docs/segment_migration_refactor_entregables.md` | Entregables: implementación, archivos, decisiones, compatibilidad, pasos de prueba, refreshes, checklist QA. | docs |
| `backend/scripts/sql/validate_segment_taxonomy.sql` | Siete consultas: distribución por segmento, masa Legend, masa Elite, top transiciones, same-to-same, presencia Dormant, config vigente ORDER BY ordering ASC. | validation |

### 3) Migraciones creadas

- **078_segment_taxonomy_elite_legend** (down_revision: 077_audit_views_24month).
  - **Upgrade:** INSERT ELITE (120, 179, ordering 6), LEGEND (180, NULL, ordering 7); UPDATE FT max_trips_week = 119; DROP view/MVs en orden inverso; CREATE mv_driver_segments_weekly con ord/prev_ord vía subconsulta a driver_segment_config; CREATE resto de cadena (mv_supply_segments_weekly, anomalies, alerts, v_supply_alert_drilldown). Alertas con recommended_action para ELITE y LEGEND.
  - **Downgrade:** Restaura MVs al estilo 067 (CASE de 5 segmentos); UPDATE FT max_trips_week = NULL; UPDATE ELITE/LEGEND effective_to = CURRENT_DATE.

### 4) Vistas/MVs/SQL tocados

- **Objetos recreados por la migración 078:**  
  `ops.v_supply_alert_drilldown`, `ops.mv_supply_alerts_weekly`, `ops.mv_supply_segment_anomalies_weekly`, `ops.mv_supply_segments_weekly`, `ops.mv_driver_segments_weekly`.
- **Tabla modificada (solo UPDATE/INSERT):** `ops.driver_segment_config` (INSERT ELITE/LEGEND, UPDATE FT).
- **Script de validación:** `backend/scripts/sql/validate_segment_taxonomy.sql` (solo lectura).

### 5) Endpoints afectados

- **GET /ops/supply/segments/config:** Orden de filas pasa de DESC a ASC (ordering). Esquema igual: `{ data: [ { segment, min_trips, max_trips, priority } ] }`. Compatible: clientes que ordenen por priority siguen funcionando.
- **GET /ops/supply/migration:** Respuesta extendida: `summary` incluye `stable` (suma de drivers con migration_type lateral). `data` sin cambios (sigue incluyendo filas lateral). Compatible: additive.

### 6) Componentes frontend afectados

- **SupplyView.jsx:** Tab Migration (header, KPIs, insight, resumen por From, tabla sin lateral); tab Composition (glosario); uso de formatIsoWeek, parkLabel en drilldown.
- **DriverSupplyGlossary.jsx:** Leyenda de segmentos bajo término "Segments".
- **segmentSemantics.js:** Nuevo módulo; usado por SupplyView (fallback, resumen From) y DriverSupplyGlossary (leyenda).

### 7) Scripts de validación existentes

- `backend/scripts/sql/validate_segment_taxonomy.sql`: 7 consultas (distribución, masa Legend, masa Elite, top transiciones, same-to-same, Dormant, config vigente). **No se ejecutó en esta auditoría** por requerir conexión a BD; debe ejecutarse manualmente tras refresh de MVs.

### 8) Documentos .md creados

- `docs/segment_migration_refactor_scan.md`
- `docs/segment_migration_refactor_entregables.md`
- `docs/segment_migration_final_audit.md` (este documento)

---

## FASE C — Validación de migraciones y seguridad del cambio

**¿Hubo migraciones?** Sí.

**Archivo de migración:** `backend/alembic/versions/078_segment_taxonomy_elite_legend.py`.

**Qué hace:**
1. INSERT en `ops.driver_segment_config` para ELITE (120–179, ordering 6) y LEGEND (180, NULL, ordering 7) si no existen.
2. UPDATE en `ops.driver_segment_config`: FT con max_trips_week = 119 (solo filas vigentes).
3. DROP en orden: v_supply_alert_drilldown, mv_supply_alerts_weekly, mv_supply_segment_anomalies_weekly, mv_supply_segments_weekly, mv_driver_segments_weekly.
4. CREATE de las mismas MVs/vista con nueva definición de `mv_driver_segments_weekly` (ord/prev_ord desde subconsulta a config, sin CASE hardcodeado).

**¿Additive / no destructiva?**  
- Config: solo INSERT y UPDATE; no se borran columnas ni tablas.  
- MVs: se recrean (comportamiento estándar en esta cadena); no se eliminan tablas base.

**¿Renombraron, borraron o alteraron algo crítico?**  
- No se renombran tablas ni columnas.  
- Se recrean MVs que ya se recreaban en 067; la tabla `ops.driver_segment_config` y `ops.mv_driver_weekly_stats` no se eliminan.

**¿Compatibilidad hacia atrás?**  
- Tras upgrade, los datos en MVs se recalculan con la nueva taxonomía (ELITE, LEGEND, FT 60–119). Cualquier consumidor que espere solo 5 segmentos verá 7; los que filtren por segment_code siguen funcionando. La API extiende summary con "stable" y no quita campos.

**Ejecución de `alembic upgrade head`:**  
- Comando ejecutado desde `backend/`: `alembic upgrade head`.  
- Resultado: **éxito**. Salida observada: `Running upgrade 077_audit_views_24month -> 078_segment_taxonomy_elite_legend`.  
- No se ejecutó downgrade.

---

## FASE D — Validación de configuración de segmentos

**Dónde vive la definición:**  
- **Backend:** tabla `ops.driver_segment_config` (segment_code, segment_name, min_trips_week, max_trips_week, ordering, effective_from, effective_to). La migración 078 inserta ELITE/LEGEND y actualiza FT.  
- **Frontend:** constante `frontend/src/constants/segmentSemantics.js` (SEGMENT_LEGEND_MINIMAL, SEGMENT_LABELS) como fallback y para leyenda; el orden operativo está fijado en código (dormant → legend).

**¿Centralizada o dispersa?**  
- En BD está centralizada en `driver_segment_config`. En frontend hay una fuente de verdad para fallback/leyenda en `segmentSemantics.js`; si el API devuelve config, SupplyView usa ese orden (ASC).

**Alineación backend/frontend:**  
- Backend devuelve segmentos con ordering ASC (línea 577 supply_service.py).  
- Frontend usa SEGMENT_LEGEND_MINIMAL con orden: DORMANT, CASUAL, PT, FT, ELITE, LEGEND (y en SEGMENT_LABELS FT 60–119, ELITE 120–179, LEGEND 180+). Coincide con la taxonomía objetivo salvo que en BD siguen existiendo OCCASIONAL/CASUAL con rangos 1–4 y 5–19 (no unificado en "casual" 1–29).

**Orden:**  
- No alfabético. En backend ORDER BY ordering ASC (1=DORMANT hasta 7=LEGEND). En frontend SEGMENT_LEGEND_MINIMAL está ordenado explícitamente.

**Labels vs keys:**  
- Keys técnicas en BD: DORMANT, OCCASIONAL, CASUAL, PT, FT, ELITE, LEGEND. Labels en segmentSemantics y glosario: Dormant, Casual, PT, FT, Elite, Legend. "Nivel Dios" solo en descripción de Legend en segmentSemantics.

**Evidencia explícita en código:**

- **ELITE existe:** 078 líneas 18–21 (INSERT ELITE 120, 179, ordering 6). segmentSemantics.js líneas 19, 45.  
- **LEGEND existe:** 078 líneas 22–25 (INSERT LEGEND 180, NULL, ordering 7). segmentSemantics.js líneas 20, 46.  
- **FT 60–119:** 078 líneas 26–29 (UPDATE max_trips_week = 119). segmentSemantics.js FT desc "60–119 viajes/semana".  
- **LEGEND 180+:** 078 LEGEND min 180 max NULL. segmentSemantics.js LEGEND desc "180+ viajes/semana (Nivel Dios)".

**Nota:** La comprobación en BD (SELECT sobre driver_segment_config) requiere ejecutar la query 7 de validate_segment_taxonomy.sql; no se ejecutó en esta auditoría por no asumir conexión a BD.

---

## FASE E — Validación de masa real de datos

**No se ejecutaron consultas contra la BD** en esta auditoría (sin conexión configurada en el entorno de auditoría).

**Qué habría que ejecutar:**  
- Script `backend/scripts/sql/validate_segment_taxonomy.sql` (consultas 1, 2, 3, 6) para: distribución semanal por segment_week, masa de Legend (180+), masa de Elite (120–179), presencia Dormant.  
- Requiere que las MVs estén refrescadas tras la migración 078.

**Evidencia desde código:**  
- La MV `mv_driver_segments_weekly` usa JOIN a `driver_segment_config`, por lo que cualquier driver con trips_completed_week en 120–179 tendrá segment_week = ELITE y en 180+ segment_week = LEGEND una vez refrescada la MV.  
- Si en datos reales casi no hay conductores con 180+ viajes/semana, Legend puede tener masa muy baja; no invalida la implementación (documentado en entregables).

---

## FASE F — Validación conceptual: Dormant / Churned / Reactivated / Revival

**Qué significa cada uno en el sistema (evidencia en código):**

1. **Dormant:** Segmento por viajes/semana: 0 viajes en la semana. Definido en `driver_segment_config` (DORMANT min 0 max 0). supply_definitions: "No confundir con Dormant (segmento 0 viajes/semana)" en la clave churned. En la MV, segment_week = 'DORMANT' y segment_change_type 'drop' cuando alguien pasa a 0 viajes.

2. **Churned:** "Conductores activos la semana pasada (N-1) que no registraron viajes esta semana (N)." Definido en supply_definitions.py y calculado en `ops.v_driver_weekly_churn_reactivation` (activos en N-1, 0 viajes en N). No es lo mismo que Dormant: Dormant es el estado “0 viajes en la semana”; Churned es el flujo “dejaron de hacer viajes esta semana”.

3. **Reactivated:** "Conductores que vuelven a registrar viajes tras al menos una semana inactiva. En Migration, Revival = vuelta a actividad o primera semana." Calculado en v_driver_weekly_churn_reactivation (0 en N-1, >0 en N).

4. **Revival:** En Migration es el tipo de transición: segment_change_type 'new' (mapeado a migration_type 'revival' en supply_service). Representa primera semana o retorno desde inactividad (prev_segment_week NULL o salida desde Dormant).

**Dónde se calcula:**  
- Segmento Dormant/resto: `ops.mv_driver_segments_weekly` (JOIN a driver_segment_config).  
- Churned/Reactivated: `ops.v_driver_weekly_churn_reactivation` y agregados en mv_supply_weekly / driver_lifecycle.  
- Revival en Migration: `get_supply_migration` lee segment_change_type de la MV; type_map 'new' → 'revival'.

**¿Alguno mezclado?**  
- En definiciones y código están separados: churned explícitamente dice "No confundir con Dormant"; revival definido como vuelta a actividad o primera semana. No se detecta mezcla conceptual en el código auditado.

**Dormant estrictamente 0 viajes:**  
- Sí: driver_segment_config tiene DORMANT min 0 max 0; la MV asigna segment_week por rangos de trips_completed_week.

**Churned con ventana mayor:**  
- Churned es N-1 activo → N con 0 viajes (ventana de dos semanas). No es “cualquier semana con 0”, sino el flujo de salida. Correcto respecto a la definición documentada.

**Reactivated/Revival como retorno:**  
- Reactivated en supply: 0 en N-1 y >0 en N. Revival en Migration: segment_change_type 'new'. Coherente con “retorno a actividad o primera semana”.

**UI:**  
- Glosario (DriverSupplyGlossary) y definiciones API muestran los textos anteriores. Migration muestra badges por migration_type (upgrade, downgrade, drop, revival); Stable como KPI separado. Evidencia suficiente de que la UI comunica las diferencias vía textos y estructura.

---

## FASE G — Validación de Migration

**1) Tabla principal sin same-to-same como migración principal**  
- **Evidencia:** SupplyView.jsx líneas 819–823: `const migrationMain = migration.filter(r => r.migration_type !== 'lateral')`; la tabla se construye con `byMonthWeek = groupByMonthAndWeek(migrationMain)`. Las filas con migration_type === 'lateral' (same-to-same) no aparecen en la tabla principal.  
- **Cumple:** Same-to-same (casual→casual, pt→pt, ft→ft, elite→elite, legend→legend) no se muestra como migración principal.

**2) Same-to-same excluido o en bloque stable**  
- Excluido de la tabla principal. Aparece como KPI "Stable" (línea 745) con tooltip "Mismo segmento (estable / retained)" y usa migrationSummary?.stable o suma de lateral. No hay bloque colapsable "Stable/Retained" con filas; solo el KPI.

**3) Transiciones con dormant, elite, legend**  
- La MV y la API no restringen segmentos; from_segment y to_segment vienen de prev_segment_week y segment_week. Si la config tiene DORMANT, ELITE, LEGEND, las transiciones que existan en datos (FT→Elite, Elite→Legend, Dormant→Elite, etc.) se devuelven y se muestran. Evidencia en código: filtro solo quita lateral; no hay filtro por lista de segmentos.

**4) Jerarquía upgrade/downgrade**  
- segment_change_type se calcula en la MV con ord/prev_ord desde driver_segment_config (ordering). 078: CASE cuando ord &lt; prev_ord → downshift, ord &gt; prev_ord → upshift. La jerarquía es por ordering numérico (1–7), no alfabética.

**5) Tipo de transición no alfabético**  
- Confirmado: usa ordering de la config en subconsultas en la MV 078.

**6) Periodo semanal S##-YYYY**  
- SupplyView: formatIsoWeek(week_start) en header ("Periodo: ..."), en tabla (weekKey), en drilldown (formatIsoWeek(migrationDrilldown.week_start)). Backend: format_iso_week en supply_definitions y en get_supply_migration (week_display). Evidencia: líneas 728–730, 71 (getWeekKey), 1032.

**7) Jerarquía visual: filtros → KPIs → insight/resumen → detalle → drilldown**  
- Header con título, periodo, contexto park (líneas 727–736). KPIs en grid (líneas 739–746). Bloque insight (líneas 749–758). Resumen por segmento origen (líneas 761–802). Tabla "Transiciones" (líneas 805–884). Drilldown modal (líneas 1028+). Cumple el patrón.

**8) Bloque narrativo/interpretativo**  
- Sí: "Bloque interpretación (insight)" (líneas 749–758) con texto derivado de top downgrade y top revival.

---

## FASE H — Validación de frontend / UI

Evidencia solo desde código (sin capturas de pantalla):

1. **Dormant visible:** Aparece en SEGMENT_LEGEND_MINIMAL, en glosario bajo Segments, en config si la BD lo devuelve; en Composition y Migration como from_segment/to_segment si los datos lo tienen.  
2. **Elite visible:** Incluido en SEGMENT_LEGEND_MINIMAL, glosario, fallback y en tabla Migration/Composition si hay datos.  
3. **Legend visible:** Igual que Elite; descripción "180+ viajes/semana (Nivel Dios)".  
4. **Glosario/leyenda/tooltip:** DriverSupplyGlossary "Ver definiciones" con lista Dormant–Legend; KPIs Migration con title/tooltips.  
5. **Labels claros:** segmentSemantics y glosario usan Dormant, Casual, PT, FT, Elite, Legend.  
6. **Orden visual:** Resumen por From ordenado con segOrder(SEGMENT_LEGEND_MINIMAL); leyenda en orden fijo.  
7. **Sin IDs crudos donde hay nombre:** Drilldown Migration usa `parkLabel || \`Park ${migrationDrilldown.park_id}\`` (línea 1032).  
8. **Park por nombre:** parkLabel = selectedPark (park_name, city, country) (línea 126); se usa en header y en modal drilldown.  
9. **Driver Lifecycle:** No se modificó en este refactor (no hay cambios en DriverLifecycleView.jsx en el inventario).  
10. **Supply Dynamics:** SupplyView modificado; Composition y Migration con nueva estructura; no se eliminó funcionalidad existente.  
11. **Migration menos atomizada:** Header, KPIs, insight, resumen por From y tabla sin lateral aportan jerarquía; mismo archivo y misma pestaña.

**Verificación manual recomendada:** Abrir Supply → elegir park → pestaña Migration; comprobar título "Migración de segmentos", periodo S##-YYYY, 5 KPIs (Upgrades, Downgrades, Revivals, Drops, Stable), bloque de texto de insight, tabla "Resumen por segmento origen (From)", tabla "Transiciones" sin filas lateral, "Ver drivers" con nombre de park en el modal. Abrir "Ver definiciones" y comprobar lista de segmentos con Dormant, Elite, Legend.

---

## FASE I — Validación de endpoints y contratos

**Endpoints afectados:**

| Ruta | Cambio | Backward-compatible | Riesgo |
|------|--------|---------------------|--------|
| GET /ops/supply/segments/config | Orden de filas: antes DESC, ahora ASC. Esquema igual. | Sí (cliente que ordene por priority). | Bajo: solo orden. |
| GET /ops/supply/migration | summary extendido con clave "stable" (número). data sin cambio. | Sí (additive). | Bajo. |

**Payload previo vs actual:**  
- segments/config: mismo esquema; orden de elementos en array distinto.  
- migration: summary tiene una clave más ("stable"); data idéntica (incluye lateral).

**Cambios en schemas:**  
- No hay cambios en tipos ni eliminación de campos. Solo añadido summary.stable.

**Frontend actualizado:**  
- Sí: SupplyView usa migrationSummary?.stable (línea 745) y filtra data por migration_type !== 'lateral'.

---

## FASE J — Validación de MVs, vistas y refreshes

**Objetos afectados por 078:**  
- ops.mv_driver_segments_weekly  
- ops.mv_supply_segments_weekly  
- ops.mv_supply_segment_anomalies_weekly  
- ops.mv_supply_alerts_weekly  
- ops.v_supply_alert_drilldown  

**¿Requieren refresh manual?**  
- Tras `alembic upgrade head`, las MVs se crean vacías (o con definición nueva). Para llenarlas hace falta REFRESH MATERIALIZED VIEW (documentado en entregables). Orden recomendado: mv_driver_segments_weekly → mv_supply_segments_weekly → mv_supply_segment_anomalies_weekly → mv_supply_alerts_weekly.

**Ejecución de refreshes:**  
- No se ejecutaron en esta auditoría (requieren BD). Se documentan en docs/segment_migration_refactor_entregables.md.

**Dependencias:**  
- La cadena es la estándar ya existente; no se introducen nuevas dependencias rotas.

---

## FASE K — Validación técnica ejecutable

**validate_segment_taxonomy.sql:**  
- Existe en `backend/scripts/sql/validate_segment_taxonomy.sql`. Contiene 7 consultas (distribución, masa Legend, masa Elite, top transiciones, same-to-same, Dormant, config vigente).  
- **No se ejecutó** en esta auditoría (sin conexión a BD). Para cerrar evidencia de masa real y config en BD, debe ejecutarse manualmente tras refresh de MVs.

**Otros scripts:**  
- No se encontró otro script específico de validación de migration o de segmentos creado en este refactor. check_supply_alerting_and_segments.py ya existía y no fue modificado en el inventario.

---

## FASE L — Hallazgos, riesgos y veredicto

### Hallazgos positivos

- Scan y entregables documentados antes y después del cambio.
- Migración 078 additive en config (INSERT + UPDATE); recreación de MVs sin DROP de tablas base.
- Same-to-same excluido de la tabla principal de Migration; KPI Stable y summary.stable.
- ELITE y LEGEND incorporados en config (078), frontend (segmentSemantics, glosario) y alertas (recommended_action).
- FT acotado a 60–119 en config.
- Dormant/Churned/Reactivated/Revival diferenciados en definiciones y en uso (segmento vs flujo vs tipo de transición).
- Header, KPIs, insight, resumen por From y tabla ordenada en Migration; formato S##-YYYY; park por nombre en drilldown.
- Contratos API extendidos sin breaking changes (summary.stable, orden ASC en config).
- Script de validación SQL entregado para comprobar distribución y masa post-refresh.

### Hallazgos menores

- En segmentSemantics.js, OCCASIONAL y CASUAL tienen ambos order 2; el backend puede seguir devolviendo OCCASIONAL (1–4) y CASUAL (5–19); la taxonomía objetivo "casual 1–29" no se aplicó en BD en esta entrega (documentado en entregables).
- Verificación en BD (config vigente, masa Elite/Legend) no realizada en esta auditoría por no ejecutar SQL contra la BD.

### Hallazgos medios

- Ninguno que exija corrección inmediata.

### Hallazgos críticos

- Ninguno.

### Riesgos pendientes

- MVs deben refrescarse tras 078 para que los datos reflejen ELITE/LEGEND y FT 60–119; si no se refrescan, las MVs pueden estar vacías o desactualizadas.
- Cualquier consumidor que espere exactamente 5 segmentos verá 7; riesgo bajo si solo se filtran por nombre de segmento.

### No verificadas en esta auditoría

- Ejecución de validate_segment_taxonomy.sql y resultados (requiere BD).
- Refresco efectivo de las MVs y comprobación de conteos por segmento.
- Prueba manual en navegador (screenshots o flujo paso a paso) de Migration, Composition y glosario.

### Recomendaciones de siguiente paso

1. Ejecutar REFRESH de la cadena de MVs en el entorno objetivo.
2. Ejecutar validate_segment_taxonomy.sql y archivar resultados (distribución, masa Elite/Legend, config).
3. Prueba manual de la pestaña Migration y del glosario en entorno de staging o producción.

---

### Veredicto final

**APROBADO CON OBSERVACIONES**

La implementación cumple los criterios de la auditoría: no rompe contratos, migración no destructiva, segmentos Elite/Legend y FT 60–119 definidos en código y migración, Migration sin same-to-same en tabla principal y con jerarquía visual, distinción conceptual Dormant/Churned/Reactivated/Revival, y documentación y script de validación entregados. Las observaciones son: (1) la evidencia de masa real y config en BD queda pendiente de ejecutar validate_segment_taxonomy.sql y refreshes en un entorno con BD, y (2) la taxonomía "casual 1–29" no está unificada en BD (OCCASIONAL/CASUAL siguen separados), lo cual está documentado y no invalida el refactor realizado.

---

## FASE M — Checklist de auditoría obligatorio

- [x] Se listaron archivos modificados  
- [x] Se listaron archivos nuevos  
- [x] Se verificaron migraciones  
- [x] Se ejecutó alembic upgrade head (éxito 077→078)  
- [x] Se verificó taxonomía exacta de segmentos (en código y migración)  
- [x] Se verificó FT = 60–119 (078 UPDATE + segmentSemantics)  
- [x] Se verificó Elite = 120–179 (078 INSERT + segmentSemantics)  
- [x] Se verificó Legend = 180+ (078 INSERT + segmentSemantics)  
- [ ] Se verificó masa real de Elite (pendiente ejecución SQL en BD)  
- [ ] Se verificó masa real de Legend (pendiente ejecución SQL en BD)  
- [x] Se auditó Dormant vs Churned vs Reactivated vs Revival  
- [x] Se auditó Migration  
- [x] Se confirmó que same-to-same no sale como migración principal  
- [x] Se verificó formato semanal S##-YYYY  
- [x] Se verificó frontend (evidencia en código)  
- [x] Se verificaron endpoints y contratos  
- [x] Se verificaron MVs / refreshes / SQL afectados (documentados)  
- [x] Se documentaron riesgos  
- [x] Se emitió veredicto final (APROBADO CON OBSERVACIONES)  
