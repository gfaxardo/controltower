# OPERATIONAL MATURITY AUDIT — FASE 1H.4

**Date:** 2026-05-24
**Scope:** Full navigation registry, App.jsx, route groups, feature flags, legacy views

---

## 1. CLASSIFICATION MATRIX

### STABLE — Core Operational Views

| Key | Module | Engine | Phase | Notes |
|---|---|---|---|---|
| `performance_resumen` | ExecutiveSnapshotView | Control Foundation | 1H | Executive KPIs |
| `performance_plan_vs_real` | MonthlySplitView + WeeklyPlanVsRealView | Control Foundation | 1H | Plan vs Real comparison |
| `performance_real` | RealOperationalView | Control Foundation | 1H | Hourly operational view |
| `operacion_omniview_matrix` | BusinessSliceOmniviewMatrix | Control Foundation | 1H | **Canonical operational truth** |
| `operacion_lob_drill` | RealLOBDrillView | Control Foundation | 1H | LOB hierarchical drill |
| `operacion_control_loop_pvr` | ControlLoopPlanVsRealView | Control Foundation | 1H | Control loop PvR |
| `operacion_reportes` | BusinessSliceOmniviewReports | Control Foundation | 1H | Omniview reports |
| `system_health` | SystemHealthView | Control Foundation | 1H | System health/observability |
| `drivers_supply` | SupplyView | Control Foundation | 1H | Driver supply/migration |

### HARDENING — Active stabilization

| Key | Module | Engine | Phase | Notes |
|---|---|---|---|---|
| `performance_yango_loyalty` | YangoLoyaltyView | Control Foundation | 1H | New loyalty tracker |
| `plan_acciones` | Phase2BActionsTrackingView + Phase2CAccountabilityView | Control Foundation | 1H | Accountability tracking |
| `plan_universo` | LobUniverseView | Control Foundation | 1H | LOB universe mapping |
| `plan_validacion` | PlanTabs | Control Foundation | 1H | Plan validation (expansion/gaps) |
| `drivers_lifecycle` | DriverLifecycleView | Control Foundation | 1H | Driver lifecycle base |

### IN_CONSTRUCTION — Diagnostic Engine (READY NEXT)

| Key | Module | Engine | Phase | Notes |
|---|---|---|---|---|
| `drivers_diagnostic` | DriverLifecycleDashboard | Diagnostic | 2A.1 | Lifecycle diagnostics |
| `drivers_behavior_benchmarking` | DriverBehaviorBenchmarkingDashboard | Diagnostic | 2A.2 | Behavior benchmarking |
| `drivers_behavioral_alerts` | BehavioralAlertsView | Diagnostic | 2A | Behavioral alerts |
| `drivers_fleet_leakage` | FleetLeakageView | Diagnostic | 2A | Fleet leakage |
| `drivers_behavioral_patterns` | BehavioralPatternDiagnosisDashboard | Diagnostic | 2A.3 | Behavioral patterns |
| `drivers_operational_intelligence` | OperationalBehavioralIntelligenceDashboard | Diagnostic | 2B | Operational intelligence |
| `drivers_recoverability` | RecoverabilityIntelligenceDashboard | Diagnostic | 2C.1 | Recoverability (shadow) |
| `riesgo_driver_behavior` | DriverBehaviorView | Diagnostic | 2A | Behavior deviation |
| `operacion_oportunidades` | OperationalOpportunitiesView | Diagnostic | 2B | Operational opportunities |

### LEGACY — Hidden by default

| Key | Module | Engine | Phase | Notes |
|---|---|---|---|---|
| `operacion_omniview` | BusinessSliceOmniview | Control Foundation | 1H.3 | Superseded by Omniview Matrix |
| `operacion_business_slice` | BusinessSliceView | Control Foundation | 1H.3 | Superseded by Omniview Matrix |
| `en_revision_behavioral_alerts_legacy` | BehavioralAlertsView | Diagnostic | 1H | Moved to Drivers tab |
| `en_revision_fleet_leakage_legacy` | FleetLeakageView | Diagnostic | 1H | Moved to Drivers tab |

### EXPERIMENTAL — Only via feature flag

| Key | Module | Engine | Phase | Notes |
|---|---|---|---|---|
| `real_vs_projection` | RealVsProjectionView | Forecast | BACKLOG | Proto-forecast |

### DEPRECATED — Sunset path

| Key | Module | Engine | Phase | Notes |
|---|---|---|---|---|
| `riesgo_action_engine` | ActionEngineView | Action | BACKLOG | Requires Decision Engine first |

---

## 2. FEATURE FLAGS INVENTORY

| Flag | Module | Active? | Notes |
|---|---|---|---|
| `VITE_OMNIVIEW_MATRIX_MANUAL_LOAD` | Omniview Matrix | DEV | Defers heavy queries |
| `VITE_SHOW_DEV_MODULES` | All DEV_ONLY modules | DEV | Shows hidden dev modules |
| `import.meta.env.DEV` | Vite built-in | — | Development mode |

---

## 3. REDUNDANCY DETECTION

| Redundancy | Status | Action |
|---|---|---|
| `operacion_omniview` ↔ `operacion_omniview_matrix` | FIXED (1H.3) | HIDE_FROM_NAV |
| `operacion_business_slice` ↔ `operacion_omniview_matrix` | FIXED (1H.3) | HIDE_FROM_NAV |
| `en_revision_alertas` ↔ `drivers_behavioral_alerts` | FIXED | HIDE_FROM_NAV (legacy) |
| `en_revision_flota` ↔ `drivers_fleet_leakage` | FIXED | HIDE_FROM_NAV (legacy) |
| Global `CollapsibleFilters` in Omniview views | FIXED (1H.3) | Conditionally hidden |

---

## 4. VISIBILITY GOVERNANCE

```
STABLE         → KEEP_VISIBLE, primary navigation
HARDENING      → KEEP_VISIBLE, subtle "Hardening" badge
IN_CONSTRUCTION → KEEP_VISIBLE, clear "En construcción" badge + phase indicator
EXPERIMENTAL   → HIDE_FROM_NAV, requires feature flag
LEGACY         → HIDE_FROM_NAV, accessible via direct route or legacy toggle
DEPRECATED     → HIDE_FROM_NAV, placeholder with sunset warning
```

---

## 5. RISK ASSESSMENT

| Risk | Level | Mitigation |
|---|---|---|
| Breaking navigation | LOW | Registry is additive, doesn't remove existing routes |
| Confusing users with badges | LOW | Badges are subtle (pill style, non-intrusive) |
| Performance overhead | NONE | Registry is a static JS object, no runtime cost |
| Orphan components | NONE | No components deleted, only visibility governed |
| Registry drift | LOW | QA script validates consistency |

---

*End of Operational Maturity Audit — Phase 1H.4*
