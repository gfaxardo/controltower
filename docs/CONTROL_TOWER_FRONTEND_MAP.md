# Control Tower — Frontend Map (Fase A)

## Tabs principales | Archivo

| Tabs | Archivo |
|------|---------|
| Real LOB, Driver Lifecycle, Supply (Real), Legacy | `frontend/src/App.jsx` |

## Componentes por función

| Función | Componente | Archivo |
|--------|------------|---------|
| KPI cards | KPICards | `frontend/src/components/KPICards.jsx` |
| Filtros | Filters | `frontend/src/components/Filters.jsx` |
| Upload de plan | UploadPlan | `frontend/src/components/UploadPlan.jsx` |
| Revenue por país (PE/CO) | Dentro de KPICards | `frontend/src/components/KPICards.jsx` |

## Vista "Fase 2A / 2B / 2C+"

- **Ubicación:** Layout global en `App.jsx`: header + UploadPlan + Filters + KPICards + tabs. No es una ruta; es la pantalla por defecto.
- Contenido Plan vs Real detallado: pestaña **Legacy → Plan Válido** (MonthlySplitView + WeeklyPlanVsRealView).

## Trips / Drivers YTD

- **Trips Real YTD, Trips Plan YTD, Drivers Real YTD, Drivers Plan YTD:** todos en `KPICards.jsx`.

## Revenue Plan YTD / Revenue Real (Comisión Yego)

- En `KPICards.jsx`: bloques Perú/Colombia (vista ALL) o cards por país.

## Subir Plan (Plantilla Simple)

- Componente: `UploadPlan.jsx`. Título visible: "Subir Plan (Plantilla Simple)".

## Servicios API usados por la vista Plan/Real

- **Archivo:** `frontend/src/services/api.js`
- **KPICards:** getPlanMonthlySummary, getRealMonthlySummary, getPlanMonthlySplit, getRealMonthlySplit
- **UploadPlan:** uploadPlan, uploadPlanRuta27
- **MonthlySplitView:** getRealMonthlySplit, getPlanMonthlySplit, getOverlapMonthly
- **WeeklyPlanVsRealView:** getPlanVsRealWeekly, getWeeklyAlerts
- **PlanTabs:** getPlanOutOfUniverse, getPlanMissing, getIngestionStatus
- **Filters:** ninguno (solo estado local + onFilterChange)

## Estructura jerárquica de render

```
App.jsx
├── Header
├── UploadPlan
├── Filters
├── KPICards
├── Nav (tabs)
├── RealLOBDrillView (real_lob)
├── DriverLifecycleView (driver_lifecycle)
├── SupplyView (supply)
└── Legacy
    ├── Plan Válido → MonthlySplitView, WeeklyPlanVsRealView
    ├── Expansión → PlanTabs
    ├── Huecos → PlanTabs
    ├── Fase 2B → Phase2BActionsTrackingView
    ├── Fase 2C → Phase2CAccountabilityView
    └── Universo & LOB → LobUniverseView
```

## Componentes no usados en App

- `PlanVsRealView.jsx`
- `MonthlyView.jsx`
