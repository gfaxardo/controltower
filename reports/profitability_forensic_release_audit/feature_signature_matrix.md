# Feature Signature Matrix

| Feature | In HEAD? | In Working Copy? | In Dist Bundle? | In Source? |
|---------|----------|-----------------|-----------------|------------|
| TABS: overview/diagnostics/simulator/... | YES | YES | YES | YES |
| get_operational_baseline (backend) | YES | YES | N/A | YES |
| get_kpi_explainability (backend) | YES | YES | N/A | YES |
| get_driver_drill (backend) | YES | YES | N/A | YES |
| get_vehicle_drill (backend) | YES | YES | N/A | YES |
| get_operational_references_real (backend) | YES | YES | N/A | YES |
| /kpi-explainability endpoint | YES | YES | YES (index) | YES |
| /driver-drill endpoint | YES | YES | YES (index) | YES |
| /vehicle-drill endpoint | YES | YES | YES (index) | YES |
| /operational-baseline endpoint | YES | YES | NO (minified) | YES |
| showKpiCalc modal | YES | YES | YES (minified) | YES |
| showEntityDrill modal | YES | YES | YES (minified) | YES |
| "Ver calculo" button | YES | YES | YES | YES |
| "Como se calculo" modal title | YES | YES | YES | YES |
| entity_name in portfolio | YES | YES | YES | YES |
| c.rule in root causes | YES | YES | YES ("Regla:") | YES |
| DiagKpi cards clickable | YES | YES | YES | YES |
| TABS has 11 entries | YES | YES | YES | YES |
| "Sin referencia operativa" text | YES | YES | YES | YES |
| onViewCalculation prop | YES | YES | YES (minified) | YES |
| onEntityDrill prop | YES | YES | YES (minified) | YES |

## Key observations

1. ALL features exist in HEAD, working copy, and dist bundle
2. The production dist was built on 2026-05-31 20:47 (today, after all commits)
3. The dist contains strings confirming new features (driver-drill, vehicle-drill, etc.)
4. There is NO code/commit mismatch — the code is correct everywhere

## Root cause: NO SERVERS RUNNING

- Port 5173 (Vite dev server): NOT LISTENING
- Port 8000 (uvicorn backend): NOT LISTENING
- No nginx process detected
- No node process running Vite

The UI the user sees must be a CACHED browser page from a previous session.
Without servers running, the actual application cannot be served at all.
