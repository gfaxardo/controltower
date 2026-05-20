# FRAUD RISK CONTROL — FASE 1F

## Proposito
Modulo antifraude sidecar, aditivo, auditable y deterministico para Control Tower.
Detecta patrones de fraude en conductores y viajes sin tocar modulos existentes.

## Principios
- **Sidecar**: no modifica Omniview, Plan vs Real, Forecast, ni Fase 2
- **Solo lectura** sobre fuentes operativas (public.trips_2026, public.payment_details)
- **Solo escritura** en esquema `fraud`
- **Deterministico**: sin IA, sin modelos probabilisticos
- **Auditable**: toda regla deja evidencia
- **Preview-only**: no ejecuta desconexiones, no bloquea pagos, no apaga autocobro

## Fuentes reales

| Fuente | Uso | Driver ID col |
|---|---|---|
| `public.trips_2026` | Viajes completados | `conductor_id` |
| `public.payment_details` | Cuentas bancarias | `driver_id` |
| `public.trips_driver_total` | Totales por driver | `driver_id` |
| `ops.scout_liquidation_ledger` | Liquidaciones | `driver_id` |

## Capacidades

| Capacidad | Disponible | Nota |
|---|---|---|
| payment_method | SI | Derivado de tarjeta/efectivo |
| amount | SI | precio_yango_pro |
| pickup address | SI | direccion |
| distance | SI | distancia_km |
| pickup lat/lng | NO | Sin columnas GPS |
| duration | NO | Sin columna |
| bonus source | NO | Sin tabla de bonos con driver_id |
| balance source | NO | Sin tabla de saldo/PLAC |
| bank source | SI | payment_details |

## Reglas (10)

1. **NEW_DRIVER_UNDER_50_TRIPS** (medium, w=20) — Driver con <50 viajes
2. **HIGH_CARD_AMOUNT_NEW_DRIVER** (high, w=30) — Nuevo + tarjeta + monto alto
3. **REPEATED_PICKUP_CLUSTER** (high, w=25) — Mismo origen repetido
4. **LONG_TRIP_OUTLIER** (high, w=25) — Viaje atipico largo
5. **SHORT_TRIP_BONUS_PATTERN** (high, w=30) — Viajes cortos para bono
6. **BURST_ACTIVITY_NEW_DRIVER** (high, w=25) — Actividad explosiva
7. **PARK_CONCENTRATION_RISK** (medium, w=20) — Concentracion en park
8. **POST_NEGATIVE_BALANCE_SIGNAL** (critical, w=50) — **DISABLED** sin fuente
9. **BANK_ACCOUNT_CLUSTER** (critical, w=40) — **ENABLED** — wiring a public.payment_details
10. **REFERRAL_BONUS_ABUSE_SIGNAL** (high, w=35) — **DISABLED** sin fuente de bonos

### Statistical & Behavioral Trip Fraud Engine (Fase 1F-5)

14 nuevas reglas basadas en comportamiento estadistico de viajes reales:

| Codigo | Peso | Severity |
|---|---|---|
| REPEATED_ORIGIN_PATTERN | 30 | high |
| REPEATED_ROUTE_SIGNATURE | 35 | high |
| SHORT_TRIP_FARMING_PATTERN | 40 | critical |
| ROUTE_LOOP_PATTERN | 35 | high |
| COORDINATED_ORIGIN_PATTERN | 45 | critical |
| TIME_WINDOW_DENSITY | 25 | high |
| LOW_AVG_DISTANCE_PATTERN | 35 | high |
| LOW_AVG_DURATION_PATTERN | 35 | high |
| EXTREME_SHORT_TRIP_RATIO | 40 | critical |
| LOW_VARIANCE_PATTERN | 30 | medium/high |
| LONG_TRIP_OUTLIER_V2 | 30 | medium/high |
| HIGH_CARD_AMOUNT_NEW_DRIVER_V2 | 35 | critical |
| BURST_ACTIVITY_NEW_DRIVER_V2 | 30 | high |
| PARK_CONCENTRATION_RISK_V2 | 25 | high |

**Capacidades**:
- Route parsing desde `direccion` (origen -> destino)
- Baseline estadistico por park/city/service_type
- Deteccion de farming, loops, origenes coordinados
- Perfil conductual completo por driver
- SQL agregada (no trae filas completas a Python)
- dry_run por defecto en todas las rutinas

**Endpoint**: `GET /fraud/trip-behavior/summary`

## Trust Tier

| Tier | Condicion |
|---|---|
| trusted | >= 50 viajes, sin casos high/critical |
| new_or_unproven | < 50 viajes |
| restricted | Caso abierto high/critical |
| unknown | Sin datos |

## Risk Score

| Rango | Severity | Accion recomendada |
|---|---|---|
| 0-29 | low | no_action |
| 30-59 | medium | monitor |
| 60-79 | high | review / hold_bonus_review / restrict_driver_review |
| 80+ | critical | disable_autocobro / restrict_driver_review |

## Endpoints

| Metodo | Path | Descripcion |
|---|---|---|
| GET | /fraud/health | Estado general |
| GET | /fraud/source-discovery | Fuentes disponibles |
| GET | /fraud/rules | Lista reglas |
| PATCH | /fraud/rules/{code} | Modificar regla |
| POST | /fraud/recompute | Ejecutar rutinas |
| GET | /fraud/drivers/risk | Lista drivers con riesgo |
| GET | /fraud/drivers/{id}/risk | Perfil completo |
| GET | /fraud/cases | Lista casos |
| POST | /fraud/cases/{id}/review | Revisar caso |
| POST | /fraud/actions/preview | Preview de accion |
| POST | /fraud/actions/manual-log | Registrar accion manual |
| GET | /fraud/routines/status | Estado rutinas |
| GET | /fraud/identity-clusters | Clusters bancarios (Fase 1F-1) |

## Bank Account Cluster Detection (Fase 1F-1)

Deteccion de multiples drivers compartiendo cuenta bancaria via `public.payment_details`.

- **Fuente**: `public.payment_details` (driver_id, bank_name, account_number)
- **Normalizacion**: bank_name + account_number -> stripped, lowered, special chars removed
- **Hashing**: SHA-256 sin salt (riesgo documentado)
- **Masking**: account_number se muestra como `1234****5678`; nunca completo
- **Severidad**: 2 drivers low -> 5+ drivers critical
- **Acciones**: review, hold_bonus_review, restrict_driver_review, disable_autocobro
- **Privacidad**: NO se expone account_number completo en API, logs, docs ni UI
- **Estado actual**: Wiring completo. Tabla tiene 0 filas - listo cuando se carguen datos.

## Scripts

- `fraud_source_discovery.py` — Descubre fuentes en PostgreSQL
- `fraud_seed_rules.py` — Seed idempotente de reglas
- `fraud_recompute.py` — Recomputo bajo demanda
- `fraud_daily_control.py` — Rutina diaria (lista para cron)

## Uso rapido

```bash
# 1. Migrar
cd backend
alembic upgrade head

# 2. Seed reglas
python scripts/fraud_seed_rules.py

# 3. Source discovery
python scripts/fraud_source_discovery.py

# 4. Dry run (no escribe)
python scripts/fraud_recompute.py --date-from 2026-05-01 --date-to 2026-05-19 --limit 1000 --dry-run true

# 5. Real run (escribe snapshots y cases)
python scripts/fraud_recompute.py --date-from 2026-05-01 --date-to 2026-05-19 --limit 10000 --dry-run false

# 6. Validar
python scripts/validate_fraud_phase1f.py
```

## Lo que NO hace

- NO ejecuta desconexion real de drivers
- NO apaga autocobro real
- NO bloquea pagos reales
- NO modifica Omniview Matrix
- NO modifica Plan vs Real
- NO toca Fase 2 Diagnostic Engine
- NO usa IA
- NO requiere nuevas dependencias
