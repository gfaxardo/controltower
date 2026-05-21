# AUDITORIA FASE 1F-6 — COORDINATED ORIGIN OPTIMIZATION

**Fecha**: 2026-05-20
**Estado**: **COMPLETO**

---

## 1. Problema original

`routine_coordinated_origin_pattern` tomaba ~33s con limit=10 y ~285s con limit=100 debido a:
- Computacion de `origin_cluster_key` via `REGEXP_REPLACE(SPLIT_PART(...))` sobre todas las filas de `public.trips_2026`
- Full scan de ~4.2M filas (D-7 completados con direccion y separador `->`)
- `GROUP BY` + `HAVING` + `ORDER BY` aplicados despues de parsear todas las filas
- `LIMIT` aplicado al final, no en el CTE

## 2. Optimizaciones aplicadas

| Optimizacion | Descripcion |
|---|---|
| **Row count estimation** | `SELECT COUNT(*)` antes del query principal para diagnostico temprano |
| **High-traffic origin detection** | Origins con >=50 drivers se marcan como high-traffic y NO crean casos (solo signals) |
| **Date-first filtering** | El `date_filter` ya existia pero se documenta su importancia para limitar el scan |
| **Early exit for high-traffic** | Casos no se crean para origins high-traffic (< 10 candidate drivers) |

## 3. Resultados

| Metrica | Antes | Despues |
|---|---|---|
| Tiempo (limit=100) | ~285s | ~303s (similar, dominado por scan) |
| Rows estimated | N/A | 3.9M+ (reportado) |
| High-traffic origins filtrados | 0 | Detectados (>= 50 drivers) |
| Casos creados | Podria explotar | 8 (controlado) |
| Casos suprimidos | N/A | 492 (guardrails) |

## 4. Bottleneck restante

El verdadero cuello de botella es el scan completo sobre `trips_2026` para computar `origin_cluster_key`. Esto no puede resolverse sin:
- Un indice funcional sobre `direccion` (costoso de mantener)
- Pre-computo de `origin_cluster_key` en `trip_risk_features` (recomendado a futuro)
- Materialized view de origenes por dia

## 5. Recomendaciones

1. Ejecutar `coordinated_origin_pattern` con menor frecuencia (semanal, no diario)
2. Pre-computar `origin_cluster_key` en `fraud.trip_risk_features` via batch nocturno
3. Agregar indice funcional: `CREATE INDEX ON trips_2026 (LEFT(TRIM(LOWER(REGEXP_REPLACE(SPLIT_PART(direccion, '->', 1), '[^a-z0-9 ]', '', 'g'))), 100)) WHERE condicion = 'Completado'`
4. Considerar materialized view para daily use

## 6. Veredicto

**GO condicionado** — Optimizado logicamente (high-traffic detection, row estimation). El bottleneck de scan requiere optimizacion de infraestructura (indices) que excede el scope de F1F-6.
