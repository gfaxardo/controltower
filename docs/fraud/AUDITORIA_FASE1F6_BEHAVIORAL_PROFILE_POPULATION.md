# AUDITORIA FASE 1F-6 — BEHAVIORAL PROFILE POPULATION

**Fecha**: 2026-05-20
**Estado**: **COMPLETO**

---

## 1. Ejecucion

| Metrica | Valor |
|---|---|
| Rutina | `routine_behavioral_driver_profile` |
| dry_run | false |
| window_days | 7 |
| limit | 100 |
| Fecha | 2026-05-13 a 2026-05-20 |

## 2. Correcciones previas

- **Bug**: `t.payment_method` columna no existe en `trips_2026`
- **Fix**: Eliminada referencia SQL, `card_trips = 0` (feature no disponible)

## 3. Resultados

| Metrica | Valor |
|---|---|
| Drivers evaluados | 100 |
| Runtime | 60.1s (primera ejecucion), 67.3s (full run) |
| Errors | 0 |

## 4. Behavioral Profile Distribution

| Profile | Count | % |
|---|---|---|
| **normal** | 100 | 100% |
| watchlist | 0 | 0% |
| suspicious | 0 | 0% |
| high_risk | 0 | 0% |
| critical_pattern | 0 | 0% |
| **NULL** (no profile) | 3 | — |

### Interpretacion

Con limit=100 y D-7, se perfilan los primeros 100 drivers con >=3 viajes. Todos resultan `normal` porque:
- La muestra es pequena (100 de ~73,000 drivers activos)
- Para ver perfiles suspicious/high_risk se necesita mayor muestra o ventana mas larga
- Los 3 NULL corresponden a entradas de `driver_risk_snapshot` creadas por otras rutinas (low_avg_duration, extreme_short_trip_ratio) que no computan behavioral profile

## 5. Campos Poblados en driver_risk_snapshot

| Campo | Poblado |
|---|---|
| behavioral_profile_class | SI (100) |
| behavioral_profile_reason | SI (JSONB) |
| behavioral_confidence_score | SI (numerico) |

## 6. Veredicto

**GO** — Behavioral profiles poblados correctamente. Distribucion esperada para muestra pequena. Listo para escalar con mayor limit.
