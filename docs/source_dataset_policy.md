# Política de datasets fuente — trips_base y trips_2026

## Estado actual

- **trips_base** (public.trips_all): en data_freshness_expectations está marcado como **legacy** (migración 074). Fuente histórica con viajes &lt; 2026-01-01. Ya no es la fuente viva de datos recientes.
- **trips_2026** (public.trips_2026): fuente viva para viajes >= 2026-01-01. Recibe la ingestión actual.
- **v_trips_real_canon** / **v_trips_real_canon_120d**: unión de trips_all y trips_2026 con corte por fecha para evitar duplicados. Es la fuente canónica para REAL (fact → hourly → day → week → month).

## Decisión: trips_base

**trips_base ya no es fuente oficial para datos recientes.**

1. **Uso actual**: Solo histórico (&lt; 2026). La expectativa de freshness para trips_base puede dar SOURCE_STALE porque trips_all no se actualiza con fechas recientes (eso va a trips_2026).
2. **Acción**:
   - Mantener la expectativa en **legacy**: notes = "Legacy. Fuente histórica (trips_all) cortada; fuente viva: trips_2026. No usar como fuente operativa."
   - El **banner de salud** no debe depender de trips_base para marcar "Falta data" en la pestaña REAL; debe depender de real_operational / real_lob_drill u otros datasets activos.
   - No incluir trips_base en el pipeline de refresh como fuente viva (no hay que "actualizarla" para datos recientes).
3. **Dependencias**: Muchas vistas y scripts siguen leyendo trips_all para histórico o para unión con trips_2026 (v_trips_real_canon). Esas lecturas son correctas mientras la unión sea la fuente canónica. No se elimina trips_all; se deja de considerar como dataset que deba estar "al día" en freshness.

## SOURCE_STALE permitido

Si un dataset está oficialmente en **legacy** (trips_base), SOURCE_STALE es aceptable y no debe hacer fallar el criterio de "todos los datasets activos = OK". El sistema de freshness debe tratar los datasets legacy de forma distinta (grupo legacy, no bloquear el banner operativo).

## Resumen

- **trips_base**: Legacy; no es fuente oficial para datos recientes; SOURCE_STALE permitido.
- **trips_2026**: Fuente viva; debe estar en el pipeline de ingestión.
- **Banner / salud operativa**: Basada en real_operational, real_lob (cuando derive de day_v2), real_lob_drill (idem), no en trips_base.
