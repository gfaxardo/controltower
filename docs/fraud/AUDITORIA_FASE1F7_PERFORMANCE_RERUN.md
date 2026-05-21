# AUDITORIA FASE 1F-7 — PERFORMANCE RE-RUN

**Fecha**: 2026-05-20
**Estado**: **COMPLETO**

---

## 1. Daily Mode (D-1, 7 routines)

| Metrica | Valor |
|---|---|
| Runtime total | **15.6s** |
| Signals | 4 |
| Candidates | 0 |
| Cases | 0 |
| Errors | 0 |

### Per-routine

| Routine | Runtime |
|---|---|
| repeated_origin_pattern | 2.6s |
| low_variance_pattern | 1.8s |
| low_avg_distance_pattern | 1.7s |
| low_avg_duration_pattern | 1.7s |
| extreme_short_trip_ratio | 1.6s |
| short_trip_farming | 1.2s |
| park_behavior_concentration | 1.1s |

## 2. Weekly Mode (D-7, 4 routines)

- **Timeout**: > 300s (coordinated_origin_pattern ~300s)
- **Expected runtime**: ~540s (from F1F-6 full run data)
- **Mitigation**: Ejecucion programada semanal, no diaria

## 3. Daily-Ready vs Weekly

| Frecuencia | Routines | Runtime | GO |
|---|---|---|---|
| Daily | 7 | 15.6s | YES |
| Weekly | 4 | ~540s | YES (acceptable for weekly) |

## 4. Veredicto

**GO** — Daily 15.6s esta muy por debajo del target de 120s. Weekly es aceptable para frecuencia semanal.
