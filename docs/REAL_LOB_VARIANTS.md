# REAL LOB — Variantes de tipo_servicio (Fase 2 Discovery)

**Objetivo:** Diagnosticar valores crudos en BD y su mapeo canónico.

---

## Query exploratoria (ejecutar en BD)

```sql
-- Variantes crudas (últimos 90d)
SELECT
    LOWER(TRIM(COALESCE(tipo_servicio::text, ''))) AS raw_value,
    COUNT(*) AS freq
FROM public.trips_all t
WHERE t.fecha_inicio_viaje::date >= (current_date - 90)
  AND tipo_servicio IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC;

-- Valores canónicos tras normalización (post-080)
SELECT
    canon.normalize_real_tipo_servicio(tipo_servicio::text) AS valor_canonico,
    COUNT(*) AS freq
FROM public.trips_all t
WHERE t.fecha_inicio_viaje::date >= (current_date - 90)
  AND tipo_servicio IS NOT NULL
GROUP BY 1
ORDER BY 2 DESC;
```

*(Si no existe aún `canon.normalize_real_tipo_servicio`, ejecutar primero `alembic upgrade head`.)*

---

## Tabla diagnóstico (rellenar con resultados)

| valor_crudo | valor_normalizado | frecuencia | valor_canonico |
|-------------|-------------------|------------|----------------|
| (ej. confort+) | (intermedio) | (count) | comfort_plus |
| (ej. tuk-tuk) | (intermedio) | (count) | tuk_tuk |
| (ej. mensajería) | (intermedio) | (count) | delivery |
| … | … | … | … |

---

## Mapeo canónico de referencia (080)

| Valor crudo (ejemplos) | valor_canonico |
|------------------------|----------------|
| confort+, confort plus, comfort+, comfort plus | comfort_plus |
| tuk-tuk, tuk_tuk | tuk_tuk |
| express, mensajería, mensajeria, expres, envíos, envios | delivery |
| económico, economico | economico |
| confort, comfort | comfort |
| minivan, premier, standard, start, xl, cargo, moto | (misma clave) |
| NULL, vacío, >30 chars | UNCLASSIFIED |

Tras ejecutar las queries y rellenar la tabla, guardar una copia de los resultados aquí o en un CSV para trazabilidad.
