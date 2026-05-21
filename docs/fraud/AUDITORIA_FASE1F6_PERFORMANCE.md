# AUDITORIA FASE 1F-6 — PERFORMANCE REPORT

**Fecha**: 2026-05-20
**Estado**: **COMPLETO**

---

## 1. Runtime por rutina (limit=100, D-7 window)

| Rutina | Runtime | % Total | Bottleneck |
|---|---|---|---|
| coordinated_origin_pattern | 303.9s | 52.9% | CRITICAL — scan + REGEXP_REPLACE sobre 4M filas |
| repeated_route_signature | 86.9s | 15.1% | HIGH — full scan para route signatures |
| long_trip_outlier_v2 | 82.3s | 14.3% | HIGH — full scan para outliers |
| behavioral_driver_profile | 67.3s | 11.7% | MEDIUM — aggregacion multi-metrika |
| repeated_origin_pattern | 7.6s | 1.3% | LOW |
| low_avg_duration_pattern | 3.9s | 0.7% | LOW |
| route_loop_pattern | 3.3s | 0.6% | LOW |
| extreme_short_trip_ratio | 3.2s | 0.6% | LOW |
| park_behavior_concentration | 2.9s | 0.5% | LOW |
| low_avg_distance_pattern | 2.2s | 0.4% | LOW |
| short_trip_farming | 2.2s | 0.4% | LOW |
| low_variance_pattern | 2.1s | 0.4% | LOW |
| **TOTAL** | **574.7s** | **100%** | |

## 2. Top 3 Bottlenecks

### 2.1 coordinated_origin_pattern (303.9s)
- **Causa**: `REGEXP_REPLACE(SPLIT_PART(t.direccion, '->', 1), '[^a-z0-9 ]', '', 'g')` sobre 4M filas
- **Fix propuesto**: Indice funcional o pre-computo en trip_risk_features

### 2.2 repeated_route_signature (86.9s)
- **Causa**: `LIKE '%%->%%'` full scan + `SPLIT_PART` sobre direccion
- **Fix propuesto**: Indice sobre direccion con text_pattern_ops

### 2.3 long_trip_outlier_v2 (82.3s)
- **Causa**: `DISTINCT ON` con full scan para baseline comparison
- **Fix propuesto**: Pre-computar baselines y cachear

## 3. Daily-Ready Assessment

| Rutina rapida (< 10s) | 7 |
|---|---|
| Rutina media (10-60s) | 0 |
| Rutina lenta (> 60s) | 4 |
| Rutinas totales | 12 |

### Recomendacion para daily run

- Ejecutar solo las 7 rutinas rapidas diariamente (< 25s total)
- Ejecutar las 4 rutinas lentas semanalmente (coordinated_origin, repeated_route, long_trip_outlier, behavioral_driver_profile)
- Priorizar indice funcional para coordinated_origin

## 4. Indices recomendados

```sql
-- Para coordinated_origin (mayor impacto)
CREATE INDEX IF NOT EXISTS idx_trips_origin_cluster 
ON public.trips_2026 (
    LEFT(TRIM(LOWER(REGEXP_REPLACE(
        SPLIT_PART(direccion, '->', 1),
        '[^a-z0-9 ]', '', 'g'
    ))), 100)
) WHERE condicion = 'Completado' AND direccion LIKE '%->%';

-- Para todas las rutinas conductuales
CREATE INDEX IF NOT EXISTS idx_trips_behavioral 
ON public.trips_2026 (condicion, fecha_inicio_viaje, conductor_id, park_id)
WHERE condicion = 'Completado';
```

## 5. Veredicto

**GO condicionado para daily** — 7/12 rutinas son rapidas. Las 4 lentas requieren indices o ejecucion semanal. Performance aceptable para MVP.
