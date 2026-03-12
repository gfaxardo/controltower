# Scan visual/técnico — Rediseño E2E Driver Segmentation UX y Migration UX

**Objetivo:** Eliminar caos visual, reducir carga cognitiva, armonía visual, drill/filtros por segmento.  
**Alcance:** Solo UX/frontend (y extensiones API mínimas si hace falta). No reabrir taxonomía ni lógica de BD.

---

## 1. Componentes frontend involucrados

| Área | Componente | Ubicación | Rol actual |
|------|------------|------------|------------|
| Migration | SupplyView.jsx (tab Migration) | `frontend/src/components/SupplyView.jsx` | Header, KPIs (5), insight 2 líneas, resumen por From, tabla transiciones (sin lateral), drill "Ver drivers" por fila |
| Composition | SupplyView.jsx (tab Composition) | Idem | Criterio segmentos, tabla por semana×segmento (agrupación mes→semana) |
| Segment glossary | DriverSupplyGlossary.jsx | `frontend/src/components/DriverSupplyGlossary.jsx` | Botón "Ver definiciones" → modal con TERMS + leyenda segmentos (SEGMENT_LEGEND_MINIMAL) |
| Drilldowns | SupplyView.jsx (modales) | Idem | Modal alertas: drivers por alert; Modal migración: drivers por from→to, semana, park |
| Filtros superiores | SupplyView.jsx | Idem | Cascada país → ciudad → park (obligatorio), granularidad, Desde/Hasta, "Refrescar MVs" |
| KPIs Supply/Lifecycle | SupplyView Overview, DriverLifecycleView, KPICards | SupplyView tabs; KPICards.jsx; DriverLifecycleView.jsx | Overview: grid de cards (activations, churned, reactivated, net growth, active drivers, etc.); Lifecycle: summary cards; KPICards: grid con border-l-4, título + valor + hint |

**Conclusión:** Migration, Composition, Glossary y drilldowns viven en SupplyView.jsx + DriverSupplyGlossary.jsx. No hay subcomponentes dedicados para Migration (todo inline en la pestaña).

---

## 2. Datos que recibe hoy la vista Migration

- **Fuente:** `getSupplyMigration({ park_id, from, to })` → `GET /ops/supply/migration?park_id=...&from=...&to=...`
- **Respuesta:** `{ data: [...], total: N, summary: { upgrades, downgrades, drops, revivals, stable } }`
- **Filas (data):** `week_start`, `park_id`, `from_segment`, `to_segment`, `segment_change_type`, `migration_type` (upgrade|downgrade|drop|revival|lateral), `drivers_migrated`, `drivers_in_from_segment_previous_week`, `migration_rate`, `week_display`
- **Contexto ya disponible en SupplyView:** `from`, `to`, `parkId`, `parkLabel` (park_name · city · country), `freshness` (last_week_available, last_refresh, status), `segmentConfig` (desde GET /ops/supply/segments/config), `definitions`
- **Filtros activos:** Solo los globales (país, ciudad, park, desde, hasta). No hay filtros específicos dentro de Migration (por segmento origen/destino, por tipo de transición).

---

## 3. Problemas visuales actuales detectados

| Problema | Evidencia |
|----------|-----------|
| Tabla principal muy plana | Agrupación solo por mes → semana; no por segmento origen. Lectura fila a fila para entender "desde qué segmento se cae". |
| FROM/TO poco diferenciados | From y To son texto plano en columnas adyacentes; no hay peso visual distinto (ej. From secundario, To destacado). |
| Sin filtros de drill natural | No se puede filtrar "solo salidas de FT" o "solo downgrades" o "solo revivals" sin perder contexto. |
| Resumen por segmento sin acción | La tabla "Resumen por segmento origen" no tiene enlace/botón para "ver solo este segmento" en la tabla principal. |
| Stable mezclado en resumen | Stable aparece en KPI y en columnas del resumen por From; no hay bloque aparte "retención/estable" compacto. |
| Insights limitados | Solo 2 frases (mayor degradación, revivals destacados). Falta: mayor upgrade, segmento con mayor salida negativa, mayor recuperación, movimiento crítico desde FT/Elite/Legend. |
| Sin agrupación por FROM en tabla | La tabla ordena por mes→semana→filas; no agrupa por from_segment para leer por bloque. |
| Leyenda con 6 segmentos en front | SEGMENT_LEGEND_MINIMAL tiene 6 ítems (falta OCCASIONAL); la BD tiene 7. Coherencia con API/BD a revisar. |
| Header algo recargado | Glosario incrustado en el mismo bloque que título y periodo; se puede compactar. |
| Badges tipo correctos pero mejorables | upgrade/downgrade/drop/revival con color; se puede dar más contraste y agrupar visualmente por tipo. |

---

## 4. Patrones visuales existentes en el sistema (reutilizables)

| Patrón | Dónde | Uso en Migration |
|--------|------|-------------------|
| Cards KPI con label + valor + hint/tooltip | SupplyView Overview, KPICards (border-l-4, bg-*-50), DriverLifecycleView | Ya usado en Migration (5 cards); mantener estilo y añadir tooltip breve. |
| Tabla con agrupación por mes/semana | SupplyView Composition, Migration, Alerts | Mantener; añadir agrupación opcional por FROM. |
| Filtros en barra horizontal | SupplyView (country, city, park, from, to), RealLOBView, DriverLifecycleView | Añadir barra de filtros dentro de Migration: segmento origen, destino, tipo. |
| Bloques de insight / nota | SupplyView insight 2 líneas (bg-slate-50), KPICards nota vista ALL | Ampliar a 3–4 insights en bloque único, mismo estilo. |
| Badges por severidad/tipo | SupplyView Migration (upgrade/downgrade/drop/revival), Alerts (priority_label) | Reutilizar y reforzar (mismo esquema de color). |
| Modal drilldown | SupplyView (alert drilldown, migration drilldown) | Mantener; mejorar título del modal con from→to, periodo, park. |
| Leyenda de segmentos | DriverSupplyGlossary (SEGMENT_LEGEND_MINIMAL), Composition (criterio en línea) | Unificar: 7 segmentos si API los devuelve; rangos desde segmentConfig. |

---

## 5. Archivos a tocar

| Archivo | Cambios previstos |
|---------|-------------------|
| `frontend/src/components/SupplyView.jsx` | Reordenar Migration: header compacto, KPIs, bloque insights (3–4), resumen por segmento con drill por segmento, filtros (from segment, to segment, type), tabla agrupada por FROM (o por mes→FROM), bloques Stable aparte, refuerzo FROM/TO y badges. Modal drilldown con contexto claro. |
| `frontend/src/constants/segmentSemantics.js` | Incluir OCCASIONAL en SEGMENT_LEGEND_MINIMAL (y en orden) para alinear 7 segmentos con BD; mantener alias Legend. |
| `frontend/src/components/DriverSupplyGlossary.jsx` | Asegurar que la leyenda use segmentConfig cuando exista (7 segmentos + rangos); fallback a SEGMENT_LEGEND_MINIMAL con 7 ítems. |
| `docs/migration_visual_refactor_scan.md` | Este documento (scan + plan). |
| Opcional backend | Solo si hace falta endpoint o campo adicional para "resumen por segmento" ya agregado; hoy el resumen se calcula en front desde `data`. No previsto. |

---

## 6. Componentes reutilizables

- **Estilo de cards:** mismo que Overview/KPICards (bg-white, rounded, shadow, border-l-4 o sin borde).
- **Estilo de tabla:** min-w-full, divide-y, thead bg-gray-50, mismos th/td.
- **formatIsoWeek, formatNum, groupByMonthAndWeek, monthLabel:** ya en SupplyView; reutilizar.
- **Orden de segmentos:** usar `segmentConfig` ordenado por backend o SEGMENT_ORDER_BACKEND / SEGMENT_LEGEND_MINIMAL (7 ítems tras ajuste).

---

## 7. Propuesta de reordenamiento visual (Migration)

1. **Header de contexto:** Título "Migración de segmentos", periodo (Sx–Sy), alcance (park · ciudad · país), freshness en una línea; glosario en botón/link aparte (no incrustado).
2. **KPI strip:** 5 cards (Upgrades, Downgrades, Revivals, Drops, Stable) con valor grande y tooltip; opcional "Net quality" si se calcula (upgrades - downgrades).
3. **Bloque insights:** 3–4 frases: mayor degradación, mayor upgrade, segmento con mayor salida negativa, mayor recuperación o movimiento crítico desde FT/Elite/Legend.
4. **Filtros Migration:** Barra compacta: Segmento origen (dropdown), Segmento destino (dropdown), Tipo (upgrade/downgrade/drop/revival/todos). Aplicar a la tabla y al resumen por segmento (resumen siempre por segmento origen; filtro limita filas mostradas).
5. **Resumen por segmento origen:** Tabla From | Up | Down | Stable | To dormant | Revived | [Drill]. Botón/link "Ver solo este segmento" que aplica filtro "segmento origen = X".
6. **Tabla de transiciones:** Excluir lateral. Agrupar filas por `from_segment` (headers de grupo visibles), dentro de cada grupo ordenar por severidad o por to_segment. Destacar FROM (texto secundario) y TO (font-medium o badge suave). Badge de tipo más visible. "Ver drivers" por fila.
7. **Bloque Stable/Retención:** Sección compacta debajo o al lado: "Retención: X drivers se mantuvieron en el mismo segmento"; por segmento (opcional) "FT retuvo N, PT retuvo M...".
8. **Modal drilldown:** Título: "From → To · Sx-YYYY · Park". Cuerpo: tabla drivers con From, To, Tipo, periodo, park ya fijados.

---

## 8. Riesgos

- **Filtros en cliente:** Si el volumen de filas es muy alto, filtrar en front está bien; si en el futuro se paginan datos, habría que pasar filtros al backend.
- **Orden de segmentos:** Si en algún momento el backend no devuelve `ordering`, el front debe tener fallback (SEGMENT_ORDER_BACKEND / SEGMENT_LEGEND_MINIMAL con 7).
- **Estabilidad de contratos:** No cambiar estructura de `data` ni de `summary`; solo añadir filtros y presentación.

---

## 9. Cambios que NO se tocarán

- Endpoints existentes: `GET /ops/supply/migration`, `GET /ops/supply/migration/drilldown`, `GET /ops/supply/segments/config`, definiciones, freshness.
- Estructura de respuesta (data, summary).
- Lógica de BD, migraciones, MVs.
- Tabs Overview, Composition, Alerts (solo retoques mínimos de estilo si se unifica spacing/typography).
- Driver Lifecycle (solo referencia de consistencia visual).

---

## 10. Plan de implementación (resumen)

| Fase | Acción |
|------|--------|
| B | Aplicar principios: jerarquía (filtros → KPIs → insight → resumen → tabla → stable), menos ruido, agrupación por FROM, progressive disclosure, consistencia de labels y badges. |
| C | Header compacto; KPI strip con tooltips; bloque 3–4 insights; resumen por segmento con drill "ver solo este segmento"; tabla agrupada por FROM, FROM/TO diferenciados, badges fuertes; bloque Stable aparte. |
| D | Filtros: segmento origen, segmento destino, tipo; drill por segmento desde resumen; modal drilldown con contexto claro. |
| E | Glosario/leyenda: 7 segmentos (incl. OCCASIONAL), rangos desde API; reutilizable en Migration/Composition. |
| F | Revisar spacing, títulos, cards y badges para alineación con Supply/Overview y resto Control Tower. |
| G | Reducir columnas innecesarias, mejorar whitespace, resumen más prominente que tabla. |
| H | Todo en frontend salvo extensión mínima API si se necesitara (no prevista). |
| I–J | QA y entregables (checklist, archivos tocados, guía de pruebas). |

---

**Documento generado como salida del scan (FASE A). Implementación en fases B–J sin tocar BD ni contratos existentes.**

---

## 11. Entregables post-implementación (FASE J)

### Archivos tocados
- `frontend/src/components/SupplyView.jsx` — Rediseño pestaña Migration: header compacto, KPI strip con Net quality, insights 3–4, filtros (origen/destino/tipo), resumen por segmento con drill "Ver solo este segmento", tabla agrupada por FROM con filtros aplicados, bloque Retención (Stable) aparte.
- `frontend/src/constants/segmentSemantics.js` — Inclusión de OCCASIONAL en SEGMENT_ORDER y SEGMENT_LEGEND_MINIMAL (7 segmentos); descripción Casual ajustada a 5–29.
- `frontend/src/components/DriverSupplyGlossary.jsx` — Leyenda de segmentos desde API (getSupplySegmentConfig) cuando existe; fallback a SEGMENT_LEGEND_MINIMAL (7 ítems).
- `docs/migration_visual_refactor_scan.md` — Este documento (scan + plan + entregables).

### Cambios API
Ninguno. Contratos existentes mantenidos.

### Guía breve para probar manualmente
1. Ir a Driver Supply Dynamics, elegir país → ciudad → park.
2. Abrir pestaña **Migration**.
3. Comprobar: header con periodo y alcance; 5 KPIs + línea Net quality; bloque "Resumen interpretativo" con hasta 4 frases; filtros (segmento origen, destino, tipo) y "Limpiar filtros".
4. En "Resumen por segmento origen", pulsar "Ver solo este segmento" en una fila y comprobar que la tabla inferior se filtra por ese FROM; pulsar "Quitar filtro" y que se muestren de nuevo todas las transiciones.
5. Aplicar filtros por tipo (ej. solo Downgrade) y comprobar que la tabla y el mensaje "No hay transiciones con los filtros aplicados" cuando corresponda.
6. Comprobar que la tabla de transiciones está agrupada por "Desde {segmento}" y que same-to-same no aparece.
7. Comprobar bloque "Retención (mismo segmento)" al final con total y desglose por segmento.
8. Abrir "Ver definiciones" y comprobar que la leyenda de segmentos muestra 7 segmentos (Dormant, Occasional, Casual, PT, FT, Elite, Legend) cuando la API devuelve config, o el fallback local.
9. En una fila de transición, pulsar "Ver drivers" y comprobar que el modal muestra "From → To · Sx-YYYY · Park" y la tabla de conductores.

### Checklist QA final
- [ ] Ya no se siente caos visual en Migration.
- [ ] Jerarquía clara: filtros → KPIs → insight → resumen por segmento → tabla → retención.
- [ ] Armonía con Overview/Composition (mismo estilo de cards, bordes, espaciado).
- [ ] Resumen por segmento existe y tiene drill "Ver solo este segmento".
- [ ] Filtros por segmento origen, destino y tipo son operativos.
- [ ] Tabla principal agrupada por FROM; same-to-same no aparece.
- [ ] Bloque Stable/Retención visible y separado.
- [ ] Leyenda con 7 segmentos (Dormant, Occasional, Casual, PT, FT, Elite, Legend).
- [ ] FROM y TO diferenciados visualmente (From en gris, To en negrita).
- [ ] Modal drilldown muestra contexto claro (From → To · semana · park).
- [ ] No se han roto endpoints ni respuestas de API.
