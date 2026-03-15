# REAL — Diccionario de mapeo de motivos de cancelación

## Fuente

- **motivo_cancelacion**: campo en la fuente (trips_all, trips_2026); valor libre/texto.
- Se expone en la capa canónica como **motivo_cancelacion_raw** y se normaliza para agregados.

## Cadena de transformación

1. **motivo_cancelacion_raw**: valor tal cual en la fuente (puede ser NULL o vacío).
2. **cancel_reason_norm**: resultado de `canon.normalize_cancel_reason(raw)`:
   - NULL si raw es NULL o solo espacios.
   - En minúsculas, espacios colapsados, caracteres de ancho cero eliminados.
3. **cancel_reason_group**: resultado de `canon.cancel_reason_group(norm)` para uso en UI y agregados.

## Grupos de negocio (cancel_reason_group)

| Grupo | Descripción | Patrones (norm) |
|-------|-------------|-----------------|
| cliente | Cancelación por parte del usuario/pasajero | usuario, cliente, pasajero, user, passenger |
| conductor | Cancelación por parte del conductor | conductor, driver, chofer |
| timeout_no_asignado | Sin asignación a tiempo / no encontró conductor | timeout, tiempo, no asignado, no encontr, sin conductor, no driver, expirado, expired |
| sistema | Fallo o decisión de sistema | sistema, system, error, fallo, technical |
| duplicado | Viaje duplicado | duplica, duplicate |
| otro | Cualquier otro motivo | (resto) |

## Uso en capas

- **Fact (v_real_trip_fact_v2)**: motivo_cancelacion_raw, cancel_reason_norm, cancel_reason_group por viaje.
- **Hourly (mv_real_lob_hour_v2)**: agregados por (trip_date, trip_hour, ..., cancel_reason_norm, cancel_reason_group).
- **Day (mv_real_lob_day_v2)**: idem por día.
- **Vistas de cancelaciones**: agrupación por reason_group o reason_norm según endpoint.

## Trazabilidad

- En drill o detalle se puede mostrar **raw** cuando haga falta.
- En KPIs y gráficos se usa **group** para no dispersar categorías.
- **norm** sirve para agregados intermedios y para ampliar el diccionario sin cambiar la UI.

## Ampliación

Para añadir categorías (ej. fraude/validación): actualizar la función `canon.cancel_reason_group` en migraciones y documentar aquí el nuevo grupo y los patrones.
