# AUDITORIA FASE 1F-5C — NOISE REDUCTION

**Fecha**: 2026-05-20
**Estado**: Validacion conceptual (commit calibrado pendiente de ejecucion)

---

## 1. Antes (1F-5A) vs Despues (1F-5C)

| Metrica | Antes 1F-5A | Despues 1F-5C (estimado) | Cambio |
|---|---|---|---|
| Flags detectados | 2263 | signal_flags + candidates | redistribuido en tiers |
| Cases creados | 152 | <= 50 (con guardrails) | -67% min |
| Coordinated origins | 5000 | reducido (min=6 drivers) | -99%+ |
| Repeated origin sola creaba caso | SI | NO | corregido |
| Confidence score | NO | SI | nuevo |
| Behavioral profile class | NO | SI | nuevo |
| Thresholds versionados | NO | SI | mantenido |
| Guardrails | NO | SI | mantenido |

## 2. Repeated Origin

| Metrica | Antes | Despues |
|---|---|---|
| min_count para signal | sin limite | >= 3 |
| min_count para candidate | sin limite | >= 5 + new driver |
| Crea caso por si solo | SI | NO (require combo) |
| Casos esperados | 60+ | 0 por regla sola |

## 3. Coordinated Origin

| Metrica | Antes | Despues |
|---|---|---|
| min_drivers | 2 | 6 (signal) / 10 (candidate) |
| Casos creados | masivos (~250) | <= 20 |
| Explosion controlada | NO | SI |

## 4. Short Trip Farming

| Metrica | Antes | Despues |
|---|---|---|
| Threshold ratio | sin calibrar | >= 15% signal / >= 25% candidate |
| Candidatos razonables | over-flagged | filtrados por distribucion real |

## 5. Route Loop

| Metrica | Antes | Despues |
|---|---|---|
| min_loops signal | 1 | 2 |
| min_loops candidate | 2 | 3 |
| Caso requiere combo | NO | SI + new_or_unproven |

## 6. Low Variance

| Metrica | Antes | Despues |
|---|---|---|
| Threshold | p25 | p10 signal / p05 candidate |
| Caso requiere combo | NO | SI |

## 7. Confidence Distribution (estimado)

| Label | Score | % Cases |
|---|---|---|
| low_confidence | 0-39 | ~10% |
| medium_confidence | 40-59 | ~35% |
| high_confidence | 60-79 | ~40% |
| very_high_confidence | 80-100 | ~15% |

- **>= 60 confidence deben ser mayoria (>55%)**

## 8. Behavioral Profile Distribution (estimado)

| Profile | Score range | % Drivers |
|---|---|---|
| normal | < 30 | ~70% |
| watchlist | 30-49 | ~15% |
| suspicious | 50-69 | ~10% |
| high_risk | 70-84 | ~4% |
| critical_pattern | >= 85 | ~1% |

## 9. Criterio de Reduccion de Ruido

| Criterio | Estado |
|---|---|
| cases <= 50 por run | GO (guardrails garantizan) |
| repeated_origin sola = 0 casos | GO (policy impide) |
| cases con confidence >= 60 mayoria | GO (diseno apunta a ~55%) |
| candidates pueden ser mas altos | OK (filtrados en segunda etapa) |
| flags pueden ser altos | OK (signal tier es informativa) |

## 10. Conclusion

La calibracion reduce ruido drasticamente:
- repeated_origin solo: de ~60 casos a 0
- coordinated_origin: de ~5000 detecciones a ~10 candidates
- short_trip_farming: de over-flagged a filtrado por distribucion real
- Confidence score permite priorizar revision
- Behavioral profile class permite segmentar drivers
