# Real Trip: Outcome y Cancellation Semantics

## trip_outcome_norm

Clasificación del resultado de cada viaje derivada de `condicion`:

| Valor | Condición fuente | Significado |
|-------|-----------------|-------------|
| `completed` | `condicion = 'Completado'` | Viaje terminado exitosamente |
| `cancelled` | `condicion = 'Cancelado'` o `condicion ILIKE '%cancel%'` | Viaje cancelado |
| `other` | Cualquier otro valor | Estado desconocido o en progreso |

### Campos derivados

- `is_completed` (BOOLEAN): `TRUE` cuando `trip_outcome_norm = 'completed'`
- `is_cancelled` (BOOLEAN): `TRUE` cuando `trip_outcome_norm = 'cancelled'`

## cancel_reason_norm

Normalización del campo `motivo_cancelacion` de la fuente:

### Proceso de normalización

1. Si NULL o vacío → NULL
2. `TRIM()` — quitar espacios al inicio/fin
3. `LOWER()` — minúsculas
4. Eliminar espacios múltiples → espacio simple
5. Eliminar caracteres Unicode no visibles (NBSP, zero-width space, BOM)

### Implementación

Función: `canon.normalize_cancel_reason(raw_reason TEXT)`

```sql
SELECT CASE
    WHEN raw_reason IS NULL OR TRIM(raw_reason) = '' THEN NULL
    ELSE LOWER(TRIM(
        regexp_replace(
            regexp_replace(raw_reason, '\s+', ' ', 'g'),
            '[\u00A0\u200B\uFEFF]', '', 'g'
        )
    ))
END
```

## cancel_reason_group

Agrupación de motivos normalizados en categorías de negocio:

| Grupo | Patrones que matchean | Significado |
|-------|----------------------|-------------|
| `cliente` | usuario, cliente, pasajero, user, passenger | Cancelación iniciada por el pasajero |
| `conductor` | conductor, driver, chofer | Cancelación iniciada por el conductor |
| `timeout_no_asignado` | timeout, tiempo, no asignado, sin conductor, no driver, expirado, expired, no encontr | No se asignó conductor a tiempo |
| `sistema` | sistema, system, error, fallo, technical | Error técnico o del sistema |
| `duplicado` | duplica, duplicate | Pedido duplicado |
| `otro` | (cualquier otro) | No clasificado |

### Implementación

Función: `canon.cancel_reason_group(norm_reason TEXT)`

### Notas

- Solo se busca `motivo_cancelacion` cuando el viaje está cancelado (optimización de performance).
- Si la fuente no tiene `motivo_cancelacion`, los campos `cancel_reason_norm` y `cancel_reason_group` serán NULL.
- La clasificación es conservadora; los casos ambiguos se clasifican como 'otro'.
- Para mejorar la clasificación en el futuro, se puede refinar la función `cancel_reason_group` sin tocar las capas de agregación.

## Métricas de cancelación en capas agregadas

| Métrica | Fórmula | Disponible en |
|---------|---------|--------------|
| `requested_trips` | COUNT(*) | hour, day |
| `completed_trips` | COUNT(*) FILTER (WHERE is_completed) | hour, day, week, month |
| `cancelled_trips` | COUNT(*) FILTER (WHERE is_cancelled) | hour, day, week, month |
| `cancellation_rate` | cancelled / requested | hour, day |
| `completion_rate` | completed / requested | hour, day |

## Duración del viaje

### Cálculo

```sql
trip_duration_seconds = EXTRACT(EPOCH FROM (fecha_finalizacion - fecha_inicio_viaje))
trip_duration_minutes = trip_duration_seconds / 60.0
```

### Protección contra valores inválidos

Solo se calcula si:
1. `fecha_inicio_viaje` no es NULL
2. `fecha_finalizacion` no es NULL
3. `fecha_finalizacion > fecha_inicio_viaje`
4. La diferencia está entre 30 segundos y 36000 segundos (10 horas)

Fuera de estos rangos → NULL (no se incluye en promedios).

### Métricas de duración en agregados

| Métrica | Cálculo | Disponible en |
|---------|---------|--------------|
| `duration_total_minutes` | SUM(trip_duration_minutes) | hour, day |
| `duration_avg_minutes` | AVG(trip_duration_minutes) en hour; SUM(total)/SUM(completed) en day | hour, day |
