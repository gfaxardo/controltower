# Auditoría y estándar del sistema de grillas — YEGO Control Tower

**Fecha:** 2025-03-09  
**Objetivo:** Estandarización total de grillas + corrección estructural de Real LOB (alineación header/breakdown).

---

## FASE A — AUDITORÍA GLOBAL DE GRILLAS

### Tabla comparativa por vista

| view_name | component | layout_pattern | issues_found | alignment_status | style_status |
|-----------|-----------|----------------|--------------|------------------|--------------|
| Real LOB (Drill) | RealLOBDrillView.jsx | Tabla principal + **subtabla anidada** en `<td colSpan>` al expandir (LOB/Park/Tipo servicio) | **Columnas del desglose no alinean con cabecera**; colSpan=14 con 13 columnas reales | **ROTO** (subtabla distinta) | Parcial: colores comparativo inline, estados inline |
| Real LOB (Daily) | RealLOBDailyView.jsx | Una tabla por grupo (lob), sin filas expandidas | Sin desglose expandido | OK | Sin tokens compartidos |
| Real LOB (Legacy) | RealLOBView.jsx | Múltiples tablas (monthly/weekly), sin expand | N/A | OK | Estilos propios |
| Driver Lifecycle | DriverLifecycleView.jsx | Varias tablas (Serie por periodo, Desglose por park, Cohortes); drill en **modal** | No hay filas expandidas en tabla | OK | Badges/estilos ad hoc |
| Driver Supply Dynamics | SupplyView.jsx | Tablas por pestaña (Overview, Composition, Migration, Alerts); filas de agrupación mes/semana con colspan | Misma tabla, mismo header; agrupación con `<tr><td colSpan>` | OK | Trend: green/red/gray; migración: green/amber/red/blue |
| Snapshot | ExecutiveSnapshotView.jsx | KPICards (no grilla de filas) | N/A | N/A | N/A |
| Plan Válido / Legacy | MonthlySplitView, WeeklyPlanVsRealView | Tablas plan vs real | Sin expand | OK | Varios |
| CORE | CoreTable.jsx | Una tabla, 9 columnas, sin expand | N/A | OK | Badges: yellow/gray/green, REAL PARCIAL blue |
| Plan Tabs (Expansión/Huecos) | PlanTabs.jsx | Tablas out_of_universe, missing | N/A | OK | Badges por razón (red/orange/yellow/purple/gray) |

### Detalle por grilla

#### 1. Real LOB Drill (RealLOBDrillView.jsx)
- **Estructura:** `<table>` con `<thead>` (13 columnas) y `<tbody>`. Al expandir: `<tr><td colSpan={14}><div><table>...</table></div></td></tr>`.
- **Problema:** La subtabla interna tiene columnas propias (Dimensión | Viajes | Margen total | Margen/trip | Km prom | B2B), **no** las 13 del header. Resultado: desalineación visual.
- **table-layout:** No fijo (`min-w-full`).
- **Comparativos:** `viajes_trend` / `margen_total_trend` etc. → `bg-green-50`/`text-green-700` (up), `bg-red-50`/`text-red-700` (down), `bg-gray-50`/`text-gray-600` (neutro).
- **Estados:** CERRADO (green), ABIERTO (blue), FALTA_DATA (red), VACIO (gray). Badge + title.
- **Drill rows:** Subtabla con header propio; número de columnas distinto al grid principal.

#### 2. Driver Lifecycle (DriverLifecycleView.jsx)
- **Estructura:** Tablas independientes (Serie por periodo, Desglose por park en `<details>`, Cohortes). Drilldown abre **modal**, no filas expandidas.
- **table-layout:** `min-w-full divide-y divide-gray-200`; thead `bg-gray-50`.
- **Sin subtablas** dentro de celdas; alineación correcta.

#### 3. Driver Supply Dynamics (SupplyView.jsx)
- **Estructura:** Una tabla por pestaña; filas de agrupación con `<tr><td colSpan={N}>Mes</td></tr>` y `<tr><td>Semana</td><td colSpan={N-1} /></tr>`; filas de datos con mismo número de columnas que el header.
- **Trend/badges:** up → `bg-green-100 text-green-800`, down → `bg-red-100 text-red-800`, neutral → `bg-gray-100 text-gray-600`. Migración: upgrade=green, downgrade=amber, drop=red, revival=blue.
- **Alineación:** Correcta (mismo grid).

#### 4. CoreTable.jsx
- **Estructura:** Una tabla, 9 columnas, sin expand.
- **Badges:** NOT_COMPARABLE (yellow), NO_REAL_YET (gray), COMPARABLE (green); REAL PARCIAL (blue).

#### 5. PlanTabs (out_of_universe / missing)
- **Estructura:** Tabla simple por pestaña.
- **Badges:** Por razón (UNMAPPED_COUNTRY=red, UNMAPPED_LINE=orange, etc.).

---

## FASE B — ESTÁNDAR ÚNICO DE GRILLAS

### A. Estructura
- **Una sola tabla por grilla:** un único `<table>` por vista de datos.
- **Un solo header:** un único `<thead>` con un `<tr>` de `<th>` que define las columnas.
- **Filas expandidas (drill):** deben ser **mismo número de `<td>`** que `<th>`. **Prohibido** renderizar una subtabla (`<table>`) dentro de un `<td colSpan>`. Cada fila de desglose es un `<tr>` con un `<td>` por columna.
- **table-layout:** `table-layout: fixed` recomendado cuando las columnas tienen anchos definidos para evitar saltos; en Tailwind se puede usar clases de ancho en `<th>` (p. ej. `w-8`, `w-20`).
- **Contenedor:** `overflow-x-auto` en el wrapper para scroll horizontal si aplica.

### B. Columnas
- **Orden consistente:** misma secuencia lógica en todas las vistas similares (dimensión → métricas → comparativos → estado).
- **Primera columna:** alineada a la izquierda (expand/indent o label).
- **Métricas numéricas:** `text-right`.
- **Comparativos (WoW/MoM/DoD):** ancho fijo cuando sea posible (p. ej. `w-20`) y colores según semántica (ver C).

### C. Comparativos
- **Positivo (up):** `bg-green-50` / `text-green-700` (o tokens: `GRID_COMPARATIVE_POSITIVE_BG`, `GRID_COMPARATIVE_POSITIVE_TEXT`).
- **Negativo (down):** `bg-red-50` / `text-red-700`.
- **Neutro:** `bg-gray-50` / `text-gray-600`.
- **% vs pp:** diferenciar en label ("Δ%" vs "pp"); mismo esquema de color.
- **WoW / MoM / DoD:** labels visibles en header (p. ej. "WoW Δ%", "MoM pp").

### D. Estados (periodo/dato)
- **Cerrado:** `bg-green-100 text-green-800`, label "Cerrado".
- **Abierto (parcial):** `bg-blue-100 text-blue-800`, label "Abierto".
- **Parcial (comparativo):** `bg-amber-100 text-amber-800`, label "Parcial".
- **Falta data:** `bg-red-100 text-red-800`, label "Falta data".
- **Vacío / Sin datos:** `bg-gray-200 text-gray-600`, label "Vacío".

Unificar en constantes/tokens para que todas las vistas usen la misma semántica.

### E. Drill rows (filas de desglose)
- **Mismo grid que el header:** cada fila de desglose tiene **exactamente** el mismo número de `<td>` que el `<thead>`.
- **Indentación:** primera columna (o segunda si la primera es icono expand) con `pl-6` o similar para el label del breakdown; celdas sin dato con "—" o vacío.
- **Prohibido:** `<table>` anidado dentro de un `<td>`; prohibido `colSpan` que envuelva una subtabla con columnas distintas.

### F. Estilo visual
- **Tipografía:** `text-sm` en celdas, `text-xs font-medium text-gray-500 uppercase` en headers.
- **Padding:** `px-3 py-2` o `px-4 py-3` consistente (elegir uno por tipo de grilla).
- **Bordes:** `divide-y divide-gray-200` en tabla; `border border-gray-200 rounded-lg` en contenedor.
- **Hover:** `hover:bg-slate-50` o `hover:bg-gray-50` en filas.
- **Zebra:** opcional; si se usa, mismo criterio en todas las grillas (p. ej. solo en filas de datos, no en agrupación).
- **Badges:** `inline-flex px-2 py-0.5 rounded text-xs font-medium` + clases de color según semántica.

### Anti-patrones prohibidos
- Subtabla (`<table>`) dentro de `<td>` para desglose que no replica las columnas del header.
- `colSpan` que agrupa una región con otra tabla de distinto número de columnas.
- Colores de comparativo/estado inventados por vista sin usar tokens compartidos.
- Labels de estado distintos para el mismo concepto (p. ej. "Abierto" vs "Parcial" sin criterio único).

---

## FASE C — BRECHAS CONTRA EL ESTÁNDAR

| Vista | Compliant | Partially | Non-compliant | Notas |
|-------|-----------|-----------|---------------|-------|
| Real LOB Drill | | | ✓ | Subtabla en expand; corregido en esta fase |
| Real LOB Daily | ✓ | | | Tabla simple, sin expand |
| Driver Lifecycle | ✓ | | | Sin expand en tabla; modal OK |
| Driver Supply Dynamics | ✓ | | | Agrupación con colspan correcta |
| CoreTable | | ✓ | | Estilos locales; migrar a tokens en backlog |
| PlanTabs | | ✓ | | Badges por razón; migrar a tokens en backlog |
| Snapshot | N/A | | | No es grilla |

**Prioridad de corrección:** Real LOB (Drill) — **aplicado en esta fase**. Resto: **backlog** (usar tokens en CoreTable, PlanTabs, Real LOB cuando se toquen).

---

## FASE D — CORRECCIÓN ESTRUCTURAL REAL LOB (APLICADA)

### Cambios realizados
1. **Eliminada la subtabla interna.** Las filas de desglose (LOB / Park / Tipo de servicio) ya no se renderizan como `<tr><td colSpan><table>...</table></td></tr>`.
2. **Cada fila de desglose es un `<tr>` con el mismo número de `<td>` que el header (13).**
   - Columna 0: vacía (espacio, sin icono expand en drill).
   - Columna 1: label del breakdown (LOB / Park / Tipo de servicio) con `pl-6` para indentación.
   - Columnas 2–9: Viajes, WoW Δ% (—), Margen total, WoW Δ% (—), Margen/trip, WoW Δ% (—), Km prom, WoW Δ% (—).
   - Columna 10: Segmento/B2B (badge B2B X% o "—").
   - Columnas 11–12: WoW pp (—), Estado (—).
3. **colSpan** unificado a **13** en filas de estado (Cargando…, Error, Sin datos) para coincidir con el número real de columnas del header.
4. **Estándar de colores/semántica:** uso de `frontend/src/constants/gridSemantics.js` (getEstadoConfig, getComparativeClass, GRID_BADGE, GRID_ESTADO) en Real LOB para estados, comparativos y badges.

### Validación
- Header y filas de desglose comparten el mismo `<table>` y el mismo número de columnas.
- No hay `<table>` anidado dentro de celdas.
- Alineación visual correcta entre cabecera y breakdown.

---

## FASE E — ESTANDARIZACIÓN DE COLORES Y SEMÁNTICA VISUAL

### Archivo creado: `frontend/src/constants/gridSemantics.js`
- **Estados de periodo:** CERRADO, ABIERTO, FALTA_DATA, VACIO, PARCIAL (comparativo).
- **Comparativo:** positivo (up), negativo (down), neutro (neutral) — clases Tailwind para bg y text.
- **Badges B2B/Segmento:** clase base + color.
- Uso en RealLOBDrillView para estado y comparativos; resto de vistas en backlog para migración.

### Consolidación
- Estilos inline o ad hoc en Real LOB reemplazados por constantes donde se ha aplicado el fix.
- Otras vistas (CoreTable, PlanTabs, SupplyView) mantienen sus estilos actuales; documentado para futura unificación.

---

## FASE F — VALIDACIÓN Y CIERRE

### Validación realizada
- Revisión de código: estructura de Real LOB Drill corregida; documento de auditoría y estándar creado; constantes compartidas creadas e integradas en Real LOB.
- Validación visual recomendada en navegador: Real LOB monthly/weekly, desglose por LOB, por Park, por Tipo de servicio; comprobar alineación, comparativos y estados.

### Archivos modificados
- `frontend/src/components/RealLOBDrillView.jsx` — reemplazo de subtabla por filas `<tr>` con 13 `<td>`; uso de `gridSemantics.js` (estados, comparativos, badges, PARCIAL).
- `frontend/src/constants/gridSemantics.js` — **nuevo:** tokens GRID_ESTADO, getEstadoConfig, GRID_COMPARATIVE, getComparativeClass, GRID_BADGE, GRID_TABLE.
- `docs/grid_system_audit_and_standards.md` — **nuevo:** auditoría, estándar, brechas, correcciones y backlog.

### Backlog
- Aplicar tokens de `gridSemantics.js` en CoreTable, PlanTabs, SupplyView (estados/badges).
- Revisar RealLOBView.jsx (legacy) y RealLOBDailyView.jsx para reutilizar mismos tokens si se modifican.
- Considerar `table-layout: fixed` y anchos explícitos en todas las grillas para consistencia.

---

## Resumen ejecutivo final

1. **Vistas auditadas:** Real LOB (Drill, Daily, Legacy/RealLOBView), Driver Lifecycle, Driver Supply Dynamics, Snapshot, Plan Válido/Legacy (MonthlySplit, WeeklyPlanVsReal), CORE (CoreTable), Plan Tabs (Expansión/Huecos).
2. **Diferencias encontradas:** Solo Real LOB Drill usaba subtabla anidada en el desglose (columnas distintas al header → desalineación). Resto: tablas planas o agrupación con colspan correcto; estilos/badges sin tokens compartidos.
3. **Estándar final definido:** Una tabla por grilla, un header, filas expandidas con el mismo número de columnas que el header (prohibida subtabla interna). Columnas: orden consistente, numéricas a la derecha. Comparativos: verde/rojo/gris (positivo/negativo/neutro). Estados: Cerrado/Abierto/Parcial/Falta data/Vacío con clases unificadas. Drill: mismo grid, indentación en primera columna de dato. Documentado en este mismo archivo (Fase B).
4. **Cambios aplicados en Real LOB:** Eliminada la subtabla; cada fila de desglose (LOB / Park / Tipo de servicio) es un `<tr>` con 13 `<td>` alineados al header. Filas de Cargando/Error/Sin datos con `colSpan={13}`.
5. **Cambios de colores/semántica visual:** Creado `frontend/src/constants/gridSemantics.js` (GRID_ESTADO, getEstadoConfig, GRID_COMPARATIVE, getComparativeClass, GRID_BADGE, GRID_TABLE). Real LOB Drill usa estos tokens para estados, comparativos y badges; badge "Parcial" unificado con GRID_ESTADO.PARCIAL.
6. **Validación realizada:** Revisión de código y estructura; sin errores de lint. Validación visual en navegador recomendada (Real LOB monthly/weekly, desglose por LOB, Park, Tipo de servicio).
7. **Archivos modificados:** `frontend/src/components/RealLOBDrillView.jsx`, `frontend/src/constants/gridSemantics.js` (nuevo), `docs/grid_system_audit_and_standards.md` (nuevo).
8. **Backlog:** Aplicar tokens de gridSemantics en CoreTable, PlanTabs, SupplyView; opcional `table-layout: fixed` y anchos explícitos en grillas.

---

## Veredicto final

**LISTO PARA PROBAR EN UI**

- Estándar único definido y documentado.
- Real LOB Drill corregido estructuralmente (una tabla, mismo número de columnas; sin subtabla).
- Colores y semántica documentados y centralizados en `gridSemantics.js`; Real LOB Drill los utiliza.
- Validación en navegador pendiente por parte del equipo (alineación, comparativos, estados, drill LOB/Park/Tipo de servicio).
