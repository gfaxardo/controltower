# LG_UI_ROUTE_AUDIT — Lima Growth Frontend Route Audit

**Generated:** 2026-06-12
**Scope:** Todas las rutas frontend activas relacionadas con Lima Growth.
**Rule:** Sin modificar código.

---

## 1. RUTAS ACTIVAS (ROUTE_MAP en App.jsx)

| # | Ruta URL | Sub-Key | Componente React | Archivo | Legacy / UI1A |
|---|----------|---------|------------------|---------|---------------|
| 1 | `/lima-growth` | `lima_growth_resumen` | `LimaGrowthDashboard` | `LimaGrowthDashboardV2.jsx` | Legacy V2 (Operational) |
| 2 | `/lima-growth/estado` | `lima_growth_estado` | `LimaGrowthDashboard` | `LimaGrowthDashboardV2.jsx` | Legacy — oculta |
| 3 | `/lima-growth/programas` | `lima_growth_programas` | `LimaGrowthDashboard` | `LimaGrowthDashboardV2.jsx` | Legacy — oculta |
| 4 | `/lima-growth/oportunidades` | `lima_growth_oportunidades` | `LimaGrowthDashboard` | `LimaGrowthDashboardV2.jsx` | Legacy — oculta |
| 5 | `/lima-growth/loopcontrol` | `lima_growth_loopcontrol` | `LimaGrowthDashboard` | `LimaGrowthDashboardV2.jsx` | Legacy — oculta |
| 6 | `/lima-growth/config` | `lima_growth_config` | `LimaGrowthDashboard` | `LimaGrowthDashboardV2.jsx` | Legacy — oculta |
| 7 | `/lima-growth/intelligence` | `lima_growth_intelligence` | `LimaGrowthIntelligenceDashboard` | `LimaGrowthDashboardUI1A.jsx` | **UI1A (certificada LG-UI-1A)** |

**Fuente:** `frontend/src/App.jsx:128-180`

El componente de las rutas 1-6 (`LimaGrowthDashboard`) se importa desde `LimaGrowthDashboardV2.jsx` en `App.jsx:67`. El componente de la ruta 7 (`LimaGrowthIntelligenceDashboard`) se importa desde `LimaGrowthDashboardUI1A.jsx` en `App.jsx:68`.

---

## 2. NAVEGACIÓN VISIBLE (menú superior)

El tab `Lima Growth` expone **2 sub-tabs** (`App.jsx:122-125`):

| Sub-tab Label | Sub-Key | Ruta | Componente | Visible |
|---------------|---------|------|------------|---------|
| **Operational** | `lima_growth_resumen` | `/lima-growth` | V2 | YES (default) |
| **Intelligence** | `lima_growth_intelligence` | `/lima-growth/intelligence` | UI1A | YES |

Ambos son `KEEP_VISIBLE` en el `controlTowerNavigationRegistry.js`.

---

## 3. REGISTRO DE NAVEGACIÓN (controlTowerNavigationRegistry.js)

| Key | Label | Visibility | Component (label) | Route |
|-----|-------|-----------|--------------------|-------|
| `lima_growth_resumen` | Resumen | KEEP_VISIBLE | LimaGrowthDashboard | `/lima-growth` |
| `lima_growth_estado` | Estado | HIDE_FROM_NAV | LimaGrowthDashboard | `/lima-growth/estado` |
| `lima_growth_programas` | Programas | HIDE_FROM_NAV | LimaGrowthDashboard | `/lima-growth/programas` |
| `lima_growth_oportunidades` | Oportunidades | HIDE_FROM_NAV | LimaGrowthDashboard | `/lima-growth/oportunidades` |
| `lima_growth_loopcontrol` | Ejecucion Loop | HIDE_FROM_NAV | LimaGrowthDashboard | `/lima-growth/loopcontrol` |
| `lima_growth_config` | Configuracion | HIDE_FROM_NAV | LimaGrowthDashboard | `/lima-growth/config` |
| `lima_growth_intelligence` | Intelligence | KEEP_VISIBLE | LimaGrowthIntelligenceDashboard | `/lima-growth/intelligence` |

**Fuente:** `frontend/src/config/controlTowerNavigationRegistry.js:644-744`

---

## 4. SECCIONES INTERNAS DEL DASHBOARD V2 (Operational)

El V2 Dashboard (`LimaGrowthDashboardV2.jsx:10-16`) expone navegación interna con sidebar:

| ID | Label | Componente | Archivo |
|----|-------|-----------|---------|
| `action_plan` | Today's Action Plan | `TodayActionPlanSection` | `lima-growth-v2/sections/TodayActionPlanSection.jsx` |
| `programs` | Programas y Estado | `ProgramsSection` | `lima-growth-v2/sections/ProgramsSection.jsx` |
| `queue` | Execution Queue | `ExecutionQueueSection` | `lima-growth-v2/sections/ExecutionQueueSection.jsx` |
| `intraday_signals` | Intraday Signals | `IntradaySignalsSection` | `lima-growth-v2/sections/IntradaySignalsSection.jsx` |
| `config` | Configuracion | `ControlConfigSection` | `lima-growth-v2/sections/ControlConfigSection.jsx` |

---

## 5. SECCIONES INTERNAS DEL DASHBOARD UI1A (Intelligence)

El UI1A Dashboard (`LimaGrowthDashboardUI1A.jsx:12-20`) expone navegación interna con tabs:

| ID | Label | Componente | Archivo |
|----|-------|-----------|---------|
| `overview` | Overview | `OverviewTab` | `lima-growth-ui1a/sections/OverviewTab.jsx` |
| `programs` | Programs | `ProgramsTab` | `lima-growth-ui1a/sections/ProgramsTab.jsx` |
| `segments` | Segments | `SegmentsTab` | `lima-growth-ui1a/sections/SegmentsTab.jsx` |
| `movement` | Movement | `MovementTab` | `lima-growth-ui1a/sections/MovementTab.jsx` |
| `rna` | RNA | `RNATab` | `lima-growth-ui1a/sections/RNATab.jsx` |
| `explorer` | Driver Explorer | `DriverExplorerTab` | `lima-growth-ui1a/sections/DriverExplorerTab.jsx` |
| `effectiveness` | Effectiveness | `EffectivenessTab` | `lima-growth-ui1a/sections/EffectivenessTab.jsx` |

---

## 6. ARCHIVOS MUERTOS (no importados por App.jsx)

| Archivo | Líneas | Estado |
|---------|--------|--------|
| `frontend/src/pages/LimaGrowthDashboard.jsx` | 2147 | Dead — V1 original, no importado |
| `frontend/src/pages/LimaGrowthDashboard.legacy.jsx` | 1154 | Dead — versión legacy aún más antigua |

---

## 7. IDENTIFICACIÓN

| Pregunta | Respuesta |
|----------|-----------|
| **Ruta de la UI antigua (queue/capacity/execution)** | `/lima-growth` — V2 Operational (Control Foundation). Contiene Execution Queue, Capacity Config, LoopControl como secciones internas con sidebar. |
| **Ruta de la UI nueva certificada LG-UI-1A** | `/lima-growth/intelligence` — Intelligence Dashboard. Componente `LimaGrowthDashboardUI1A.jsx`. |
| **Certificación oficial** | `docs/lima_growth/LG_UI_1A_BROWSER_CERTIFICATION.md` + `LG_UI_1A_IMPLEMENTATION_CERTIFICATION.md` + `LG_UI_1A_DASHBOARD_MVP_CERTIFICATION.md` |
| **¿Cuál está enlazada desde el menú "Lima Growth"?** | **Ambas.** El tab Lima Growth muestra 2 sub-tabs: "Operational" (V2) e "Intelligence" (UI1A). El default al clickear el tab es `/lima-growth` (Operational V2). |

---

## 8. RECOMENDACIÓN: NO-GO para cambiar navegación

**Motivo:** Las dos UIs sirven propósitos distintos y complementarios:

- **Operational** (`/lima-growth`, V2) cubre ejecución operativa: colas de asignación, configuración de capacidad, LoopControl, señales intradía. Es la UI de comando táctico diario.

- **Intelligence** (`/lima-growth/intelligence`, UI1A) cubre inteligencia analítica: taxonomía de drivers, análisis RNA, movimiento entre segmentos, efectividad de programas, explorador de drivers. Es la UI de análisis estratégico certificada LG-UI-1A.

**Conclusión:** Deben coexistir como sub-tabs del mismo menú superior. No se recomienda reemplazar uno por el otro ni cambiar la navegación actual. La arquitectura actual con dos sub-tabs visibles es correcta.

---

## 9. DISCREPANCIA MENOR EN EL REGISTRO

El `controlTowerNavigationRegistry.js` referencia `LimaGrowthDashboard` como `component` para `lima_growth_resumen` (línea 651), pero `App.jsx:67` importa ese alias desde `LimaGrowthDashboardV2.jsx`. El campo `component` en el registry es una etiqueta descriptiva, no controla qué archivo se carga. Esto es inocuo pero podría limpiarse para evitar confusión.

**Recomendación:** Actualizar el `component` en los entries 1-6 del registry a `'LimaGrowthDashboardV2'` para reflejar el archivo real.
