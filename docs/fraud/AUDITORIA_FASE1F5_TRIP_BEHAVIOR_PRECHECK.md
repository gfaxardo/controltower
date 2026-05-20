# AUDITORIA FASE 1F-5 — TRIP BEHAVIOR PRECHECK

**Fecha**: 2026-05-20

## Rama

```
master
```

Estado: up to date with origin/master.

## Working Tree

| Archivo | Estado |
|---|---|
| backend/app/main.py | modified |
| backend/app/settings.py | modified |
| backend/alembic/versions/144_fraud_risk_foundation.py | untracked |
| backend/alembic/versions/145_payment_identity_onboarding.py | untracked |
| backend/alembic/versions/146_routine_run_log.py | untracked |
| backend/app/routers/fraud.py | untracked |
| backend/app/services/fraud/ | untracked |
| backend/scripts/fraud_*.py | untracked |
| docs/fraud/ | untracked |

Nota: Los cambios en main.py y settings.py son los de wiring antifraude de fases anteriores (necesarios). Los archivos untracked son todos de FASE 1F.

## Tablas Fraud

| Tabla | Existe | Filas |
|---|---|---|
| fraud.rule_catalog | SI | 10 |
| fraud.driver_trust_snapshot | SI | 20,505 |
| fraud.trip_risk_features | SI | 0 |
| fraud.driver_risk_snapshot | SI | - |
| fraud.risk_cases | SI | 21 |
| fraud.action_audit_log | SI | - |
| fraud.external_identity_clusters | SI | - |
| fraud.routine_run_log | SI | - |
| fraud.payment_identity_source | SI | - |
| fraud.payment_identity_import_log | SI | - |

## driver_trust_snapshot

- Count: 20,505 drivers
- Cumple con el threshold esperado (~20,505).

## Fuente de viajes

- `public.trips_2026`: 16,464,379 filas totales | 3,964,280 completados | 20,560 drivers unicos.

## Omniview / Plan vs Real

- No hay cambios pendientes en archivos de Omniview o Plan vs Real.
- Los cambios en main.py y settings.py son solo wiring de rutas antifraude.
- Las migraciones untracked son solo del esquema fraud.

## Decisión

**GO**. Condiciones minimas satisfechas:
- Esquema fraud existe.
- Tablas core existen.
- driver_trust_snapshot tiene 20,505 drivers.
- trips_2026 tiene 16.4M+ filas.
- `direccion` contiene rutas con separador `->`.
- No hay cambios sucios no relacionados.
- Omniview/Plan vs Real intactos.
