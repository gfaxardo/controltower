# Unified Segmentation Foundation — YEGO Lima Growth Tower

## Level 1: LIFECYCLE

| Estado | Regla |
|--------|-------|
| NEW | Primeros 14 dias desde primera semana registrada |
| REACTIVATED | Sin actividad > recovery_days, ahora activo de nuevo |
| ACTIVE | Actividad estable, sin caida significativa |
| DECLINING | Caida vs avg_orders_4w >= DECLINE_WARNING_PCT (15%) |
| CHURN_RISK | Caida vs avg_orders_4w >= DECLINE_RISK_PCT (30%) |
| CHURNED | Sin actividad > CHURN_DAYS (30) |
| RECOVERED | Venia de DECLINING/CHURN_RISK, ahora >= historico |
| UNKNOWN | Sin datos suficientes |

## Level 2: LOYALTY PROGRAM

| L1 | L2 |
|----|----|
| NEW, REACTIVATED | LOYALTY_14_90 |
| ACTIVE, RECOVERED | LOYALTY_ACTIVE_GROWTH |
| DECLINING, CHURN_RISK, CHURNED | LOYALTY_CHURN_PREVENTION |
| UNKNOWN | NONE |

## Level 3: ACTIONABLE COHORTS

| Cohort | Regla |
|--------|-------|
| NEW_0_14 | L1 = NEW |
| REACTIVATED_0_14 | L1 = REACTIVATED |
| NEAR_TARGET | distance_to_target <= max(10, 20% target) |
| HIGH_SUPPLY_LOW_ORDERS | supply >= avg AND orders < avg |
| RECOVERABLE | avg_orders_12w >= target AND orders < target |
| DECLINING_4W | L1 = DECLINING, caida > 30% |
| DECLINING_12W | L1 = DECLINING, caida <= 30% |
| CHURN_RISK | L1 = CHURN_RISK |
| RECOVERED | L1 = RECOVERED |
| STABLE | Activo sin accion inmediata |
| CHURNED | Sin actividad prolongada |

## Growth Priority

1. RECOVERABLE
2. NEAR_TARGET
3. HIGH_SUPPLY_LOW_ORDERS
4. NEW_0_14
5. REACTIVATED_0_14
6. DECLINING_4W
7. CHURN_RISK
8. DECLINING_12W
9. RECOVERED
10. STABLE
11. CHURNED

## Settings Configurables

| Setting | Default | Descripcion |
|---------|---------|-------------|
| LIMA_GROWTH_WEEKLY_TRIPS_TARGET | 50 | Target semanal de viajes |
| LIMA_GROWTH_DECLINE_WARNING_PCT | 15 | % caida para DECLINING |
| LIMA_GROWTH_DECLINE_RISK_PCT | 30 | % caida para CHURN_RISK |
| LIMA_GROWTH_CHURN_DAYS | 30 | Dias sin actividad = CHURNED |
| LIMA_GROWTH_RECOVERY_DAYS | 14 | Ventana para RECOVERED |
