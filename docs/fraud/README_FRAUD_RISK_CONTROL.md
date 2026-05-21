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

### Behavioral Profile Class (Fase 1F-6)

Los drivers se clasifican en 5 perfiles conductuales:

| Profile | Score | Significado |
|---|---|---|
| `normal` | < 30 | Sin senales preocupantes |
| `watchlist` | 30-49 | Senales debiles, observar |
| `suspicious` | 50-69 | Patron inusual, revisar |
| `high_risk` | 70-84 | Senales fuertes, investigar |
| `critical_pattern` | >= 85 | Patron critico, prioridad maxima |

**Endpoint**: `GET /fraud/drivers/risk?behavioral_profile_class=high_risk`

### Behavioral Confidence Score (Fase 1F-6)

Score deterministico 0-100 por driver, almacenado en `fraud.driver_risk_snapshot.behavioral_confidence_score`. Complementa el `behavioral_profile_class` con granularidad numerica.

### Performance (Fase 1F-6)

| Categoria | Rutinas | Runtime total | Frecuencia |
|---|---|---|---|
| Rapidas | 7 | ~23s | Daily |
| Lentas | 4 | ~540s | Weekly |
| Total | 12 | ~575s | — |

Rutinas lentas que requieren optimizacion de indices:
- `coordinated_origin_pattern` (~304s)
- `repeated_route_signature` (~87s)
- `long_trip_outlier_v2` (~82s)
- `behavioral_driver_profile` (~67s)

### Limites operativos

| Guardrail | Valor | Proposito |
|---|---|---|
| max_cases_per_run | 50 | No crear mas de 50 casos por ejecucion |
| max_cases_per_rule | 20 | Limitar concentracion por regla |
| max_cases_per_park | 10 | Evitar concentracion geografica |
| max_cases_per_driver | 1 | Un solo caso abierto por driver/park |

### Uso para Autocobro Eligibility (futuro)

Los `behavioral_profile_class` seran input para politicas de elegibilidad de autocobro:
- `normal` / `watchlist`: elegible
- `suspicious`: revision manual
- `high_risk` / `critical_pattern`: no elegible hasta revision y clearance

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

## Case Confidence Score (Fase 1F-5C)

Score deterministico 0-100 que ayuda a priorizar la revision de casos sin ejecutar acciones automaticas.

### Como interpretar confidence

| Score | Label | Significado | Accion sugerida |
|---|---|---|---|
| 0-39 | low_confidence | Senal debil, posible ruido | Review rapida, probable descarte |
| 40-59 | medium_confidence | Combinacion moderada de senales | Review detallada |
| 60-79 | high_confidence | Multiples senales fuertes | Prioridad alta |
| 80-100 | very_high_confidence | Patron critico confirmado | Prioridad inmediata |

### Factores que suben el score

- +20: driver new_or_unproven
- +20: 2+ reglas de severidad high
- +30: 1 regla critical
- +15: repeated_route + low_duration/low_distance
- +15: short_trip_farming candidate
- +10: burst_activity
- +10: coordinated_origin con new drivers

### Factores que bajan el score

- -20: solo repeated_origin (sin combos)
- -15: high_traffic_origin
- -20: sample bajo o fallback_used=true

### IMPORTANTE

El confidence score **NO ejecuta acciones**. Solo ayuda a priorizar revision humana. No desconecta, no bloquea pagos, no apaga autocobro.

## Behavioral Profile Class (Fase 1F-5C)

Clasificacion deterministica del perfil conductual de cada driver en 5 categorias.

### Como interpretar profiles

| Profile | Score | Significado |
|---|---|---|
| `normal` | < 30 | Sin senales preocupantes. Driver tipico. |
| `watchlist` | 30-49 | Senales debiles. Observar evolucion. |
| `suspicious` | 50-69 | Patron inusual. Revisar en profundidad. |
| `high_risk` | 70-84 | Combinacion de senales fuertes. Investigar. |
| `critical_pattern` | >= 85 | Patron critico confirmado. Prioridad maxima. |

### Donde se almacena

- `fraud.driver_risk_snapshot.behavioral_profile_class`
- `fraud.driver_risk_snapshot.behavioral_profile_reason` (JSONB con desglose)
- `fraud.driver_risk_snapshot.behavioral_confidence_score`

Se recalcula cada vez que corre `routine_behavioral_driver_profile`.

## Candidates vs Cases

- **Signal flags**: detecciones debiles, solo informativas. NO generan casos.
- **Candidates**: combinacion de senales o anomalia fuerte. Son filtrados para case creation.
- **Cases**: solo se crean si cumplen criterios estrictos (score >= 80, 2+ high, critical + new, o farming candidate con combo).

## Por que no se automatiza todavia

1. **Sin integracion operativa**: Control Tower no esta conectado a sistemas de pago/autocobro real.
2. **Fase de validacion**: El motor esta en fase de calibracion y reduccion de ruido.
3. **Decision humana requerida**: Cada case debe ser revisado antes de cualquier accion.
4. **Preview-only**: Todas las acciones son preview. Las acciones reales requieren confirmacion manual via `/fraud/actions/manual-log`.

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
