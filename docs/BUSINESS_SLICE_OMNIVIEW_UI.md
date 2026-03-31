# Business Slice Omniview — UI

## Propósito

Vista operativa en **Operación → Omniview** que consume `GET /ops/business-slice/omniview`: comparativo **current vs previous** (REAL), deltas y señales **definidas en backend**.

## Relación con Business Slice legacy

- **Business Slice** (subtab anterior): matriz mensual por métrica seleccionada y auditoría unmatched/conflicts.
- **Omniview**: comparativo multi-métrica, KPIs globales, jerarquía país → ciudad → tajada → flota y panel de detalle. **No la reemplaza.**

## Acotación weekly / daily

La UI **no envía** la petición si granularidad es semanal o diaria y no hay **país** (el API lo exige por rendimiento). Se muestra un estado vacío explicativo.

## Jerarquía de la tabla

1. **País** — métricas desde **subtotales** del backend (`subtotals`).
2. **Ciudad / tajada** — solo **sumas aditivas** de hijos (trips, revenue, cancelaciones en vista expandida); el resto en "—" para no falsear ratios.
3. **Flota (hoja)** — fila del API: señales, deltas y `direction` **tal cual** vienen del servidor.

## commission_pct en pantalla

El API entrega **ratio 0–1** (`meta.units.commission_pct.storage === 'ratio'`). La UI muestra **porcentaje** solo como formato visual; no altera el valor numérico subyente en el JSON.

## Componentes

- `BusinessSliceOmniview.jsx` — contenedor, controles, contexto, fetch.
- `BusinessSliceOmniviewKpis.jsx` — franja KPI desde `totals`.
- `BusinessSliceOmniviewTable.jsx` — tabla jerárquica.
- `BusinessSliceOmniviewSidebar.jsx` — drawer de detalle por fila.
- `omniview/omniviewUtils.js` — árbol, formato display, colores (sin reglas de negocio).
