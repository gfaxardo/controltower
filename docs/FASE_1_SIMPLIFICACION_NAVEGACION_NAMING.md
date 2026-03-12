# Fase 1 — Simplificación de navegación, naming y jerarquía visual

**Objetivo:** Reducir carga cognitiva, ordenar la navegación, clarificar jerarquía, ocultar lo técnico del primer nivel y renombrar vistas a lenguaje de negocio. Sin cambios de backend ni lógica analítica.

---

## 1. Qué se cambió

### 1.1 Navegación principal (primer nivel)

- **Antes:** 10 tabs siempre visibles (Real LOB, Driver Lifecycle, Driver Supply Dynamics, Behavioral Alerts, Fleet Leakage, Driver Behavior, Action Engine, Snapshot, System Health, Legacy). Con `VITE_CT_LEGACY_ENABLED=true` hasta 16 ítems.
- **Ahora:** 6 ítems en primer nivel + un menú “Diagnósticos” (segundo nivel):
  1. **Resumen** — Plan vs Real en KPIs (antes Snapshot).
  2. **Real** — Drill por país/periodo/LOB/park (antes Real LOB).
  3. **Supply** — Dinámica de supply por park (antes Driver Supply Dynamics).
  4. **Conductores en riesgo** — Agrupación con 4 sub-vistas (antes 4 tabs separados).
  5. **Ciclo de vida** — Por park y cohortes (antes Driver Lifecycle).
  6. **Plan y validación** — Desglose plan/real, expansión, huecos, Fase 2B/2C, Universo & LOB (antes Legacy).
  7. **Diagnósticos ▾** — Menú desplegable con: System Health.

### 1.2 Agrupación “Conductores en riesgo”

- Las vistas **Behavioral Alerts**, **Driver Behavior**, **Fleet Leakage** y **Action Engine** pasan a ser **sub-vistas** de un único tab “Conductores en riesgo”.
- Sub-nav con labels de negocio:
  - **Alertas de conducta** (Behavioral Alerts).
  - **Desviación por ventanas** (Driver Behavior).
  - **Fuga de flota** (Fleet Leakage).
  - **Acciones recomendadas** (Action Engine).
- Misma familia conceptual (“quiénes requieren atención”) sin fusionar endpoints ni lógica.

### 1.3 Agrupación “Plan y validación”

- El antiguo **Legacy** se renombra a **Plan y validación** y conserva las mismas sub-pestañas:
  - Plan Válido, Expansión, Huecos, Fase 2B, Fase 2C, Universo & LOB.
- Ya no se usa `VITE_CT_LEGACY_ENABLED` para mostrar tabs extra en la barra: todo queda bajo “Plan y validación”.

### 1.4 Segundo nivel: Diagnósticos

- **System Health** sale del primer nivel y se accede desde **Diagnósticos ▾**.
- Dropdown con un ítem: “System Health”. Cierre al hacer click fuera.

### 1.5 Naming visible

| Antes (label en UI) | Ahora (label en UI) |
|---------------------|----------------------|
| Snapshot | Resumen |
| Real LOB | Real |
| Driver Supply Dynamics | Supply |
| Driver Lifecycle | Ciclo de vida |
| Legacy | Plan y validación |
| Behavioral Alerts | Alertas de conducta (sub-nav) |
| Driver Behavior | Desviación por ventanas (sub-nav) |
| Fleet Leakage | Fuga de flota (sub-nav) |
| Action Engine | Acciones recomendadas (sub-nav) |
| System Health | System Health (dentro de Diagnósticos) |

### 1.6 Jerarquía visual

- Cada vista principal tiene en App un `<section>` con:
  - `aria-label` para accesibilidad.
  - `<h2>` con el nombre de la vista.
  - `<p>` con subtítulo breve (propósito en una línea).
- Sub-navs con texto de contexto: “Quiénes requieren atención” (Conductores en riesgo), “Plan, validación y accountability” (Plan y validación).
- ExecutiveSnapshotView: título interno pasado a `<h3>` “Plan vs Real — KPIs” para no duplicar “Resumen”.

### 1.7 Vista de entrada por defecto

- **Tab inicial:** “Resumen” (antes “Real LOB”), para que la primera pantalla sea la vista ejecutiva Plan vs Real.

---

## 2. Qué no se cambió

- **Backend:** Cero cambios. Mismos endpoints y contratos.
- **Componentes internos:** No se renombraron archivos ni componentes (BehavioralAlertsView, FleetLeakageView, etc.).
- **Lógica de negocio:** Sin nuevas MVs, sin refactors de servicios ni SQL.
- **Filtros globales:** CollapsibleFilters se mantiene igual; no se tocó Filters.
- **Deep links / rutas:** Sigue sin existir enrutado por URL; no se introdujeron rutas nuevas.
- **Contenido de cada vista:** Misma funcionalidad; solo cambia la navegación y los labels desde App.

---

## 3. Nueva jerarquía de navegación

```
Primer nivel (barra principal)
├── Resumen
├── Real
├── Supply
├── Conductores en riesgo
│   └── Sub-nav: Alertas de conducta | Desviación por ventanas | Fuga de flota | Acciones recomendadas
├── Ciclo de vida
├── Plan y validación
│   └── Sub-nav: Plan Válido | Expansión | Huecos | Fase 2B | Fase 2C | Universo & LOB
└── Diagnósticos ▾
    └── System Health
```

---

## 4. Mapeo nombres antiguos → nuevos

| Nombre antiguo (UI) | Nombre nuevo (UI) | Ubicación |
|--------------------|-------------------|-----------|
| Snapshot | Resumen | Primer nivel |
| Real LOB | Real | Primer nivel |
| Driver Supply Dynamics | Supply | Primer nivel |
| Driver Lifecycle | Ciclo de vida | Primer nivel |
| Legacy | Plan y validación | Primer nivel |
| Behavioral Alerts | Alertas de conducta | Sub-nav de Conductores en riesgo |
| Driver Behavior | Desviación por ventanas | Sub-nav de Conductores en riesgo |
| Fleet Leakage | Fuga de flota | Sub-nav de Conductores en riesgo |
| Action Engine | Acciones recomendadas | Sub-nav de Conductores en riesgo |
| System Health | System Health | Dentro de Diagnósticos |

---

## 5. Vistas movidas a segundo nivel

- **System Health:** Ya no es un tab de primer nivel; se accede desde **Diagnósticos ▾**.
- **Behavioral Alerts, Driver Behavior, Fleet Leakage, Action Engine:** Siguen siendo vistas completas, pero están bajo el tab “Conductores en riesgo” como sub-vistas (no “ocultas”; solo agrupadas).

---

## 6. Riesgos abiertos

- **Sin rutas/URLs:** Si más adelante se añade enrutado (p. ej. `/resumen`, `/real`, `/conductores-en-riesgo/alertas`), habrá que alinear `activeTab` / sub-tabs con la URL.
- **Bookmarks / favoritos:** Cualquier bookmark a “pestaña X” será conceptual (no hay URL que guardar); si se implementan rutas, conviene mantener compatibilidad con la estructura actual.
- **LEGACY_ENABLED:** Ya no se usa para mostrar tabs extra; si algo dependía de ese comportamiento en otro entorno, hay que validarlo.

---

## 7. Qué queda para Fase 2

- Consolidación de vistas (simplificación por vista: filtros por defecto, columnas, KPIs).
- Mejora de estados vacíos y de error de forma homogénea en todas las vistas.
- Posible agrupación “Más filtros” en vistas con muchos filtros (p. ej. Alertas de conducta).
- Reducción de llamadas en Resumen (KPICards) cuando filtro “All” (endpoint agregado o cache).
- Revisión de componentes huérfanos (RealLOBView, PlanVsRealView, MonthlyView, CoreTable).

---

## 8. Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `frontend/src/App.jsx` | Nueva estructura de navegación (6 tabs + Diagnósticos), sub-navs Conductores en riesgo y Plan y validación, naming, secciones con h2/subtítulo, estado inicial Resumen, eliminación de LEGACY_ENABLED en la barra. |
| `frontend/src/components/ExecutiveSnapshotView.jsx` | Título interno de h2 “Snapshot (Plan vs Real)” a h3 “Plan vs Real — KPIs”. |
| `docs/FASE_1_SIMPLIFICACION_NAVEGACION_NAMING.md` | Este documento. |

---

## 9. Checklist de validación visual

| # | Vista objetivo | Componente real | Label visible final | Ubicación en navegación | Cómo validar en UI |
|---|----------------|-----------------|---------------------|-------------------------|--------------------|
| 1 | Resumen | ExecutiveSnapshotView (KPICards) | Resumen | Primer nivel, primera pestaña por defecto | Abrir app → debe verse “Resumen” activo y KPIs Plan vs Real. |
| 2 | Real | RealLOBDrillView | Real | Primer nivel | Clic en “Real” → drill por país/periodo y opción Diario. |
| 3 | Supply | SupplyView | Supply | Primer nivel | Clic en “Supply” → 4 tabs: Overview, Composition, Migration, Alerts. |
| 4 | Conductores en riesgo | — (contenedor) | Conductores en riesgo | Primer nivel | Clic en “Conductores en riesgo” → aparece sub-nav con 4 opciones. |
| 5 | Alertas de conducta | BehavioralAlertsView | Alertas de conducta | Sub-nav de Conductores en riesgo | Dentro de Conductores en riesgo, clic en “Alertas de conducta” → tabla de alertas. |
| 6 | Desviación por ventanas | DriverBehaviorView | Desviación por ventanas | Sub-nav de Conductores en riesgo | Dentro de Conductores en riesgo, clic en “Desviación por ventanas” → vista Driver Behavior. |
| 7 | Fuga de flota | FleetLeakageView | Fuga de flota | Sub-nav de Conductores en riesgo | Dentro de Conductores en riesgo, clic en “Fuga de flota” → vista Fleet Leakage. |
| 8 | Acciones recomendadas | ActionEngineView | Acciones recomendadas | Sub-nav de Conductores en riesgo | Dentro de Conductores en riesgo, clic en “Acciones recomendadas” → vista Action Engine. |
| 9 | Ciclo de vida | DriverLifecycleView | Ciclo de vida | Primer nivel | Clic en “Ciclo de vida” → vista por park y cohortes. |
| 10 | Plan y validación | Contenedor Legacy | Plan y validación | Primer nivel | Clic en “Plan y validación” → sub-nav: Plan Válido, Expansión, Huecos, Fase 2B, Fase 2C, Universo & LOB. |
| 11 | Plan Válido / Expansión / Huecos / Fase 2B / Fase 2C / Universo & LOB | MonthlySplitView, WeeklyPlanVsRealView, PlanTabs, Phase2B*, Phase2C*, LobUniverseView | Igual que antes | Sub-nav de Plan y validación | En Plan y validación, clic en cada sub-tab → contenido correcto. |
| 12 | System Health | SystemHealthView | System Health | Dentro de “Diagnósticos ▾” | Clic en “Diagnósticos” → abrir dropdown → clic en “System Health” → vista System Health. |
| 13 | Sin vistas perdidas | — | — | — | Todas las vistas anteriores (Snapshot, Real LOB, Supply, Behavioral Alerts, Fleet Leakage, Driver Behavior, Action Engine, Driver Lifecycle, Legacy con 6 sub-vistas, System Health) siguen accesibles. |
| 14 | Sin labels viejos en barra principal | — | — | — | En la barra principal no debe aparecer “Real LOB”, “Driver Lifecycle”, “Behavioral Alerts”, “Legacy”, “Snapshot” ni “Driver Supply Dynamics”. |

---

## 10. Resumen ejecutivo

- **Implementación:** Un único archivo de navegación modificado en profundidad (`App.jsx`) y un ajuste de título en `ExecutiveSnapshotView.jsx`. Sin cambios en backend ni en el resto de componentes.
- **Nueva navegación:** 6 ítems principales + Diagnósticos (dropdown). “Conductores en riesgo” y “Plan y validación” con sub-navs. Entrada por defecto: Resumen.
- **Naming:** Labels pasados a lenguaje de negocio según el mapeo del documento de simplificación.
- **Validación:** Checklist anterior para comprobar en UI que todo sigue navegable y que no hay vistas perdidas ni labels antiguos en la barra principal.
