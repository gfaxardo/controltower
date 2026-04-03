# Política de datasets fuente — trips_2025, trips_2026 y trips_base (legacy)

## Estado actual (actualizado 2026-04-02)

- **trips_2025** (public.trips_2025): fuente oficial para viajes de 2025-01-01 a 2025-12-31.
- **trips_2026** (public.trips_2026): fuente oficial/viva para viajes >= 2026-01-01. Recibe la ingestión actual.
- **trips_base** (public.trips_all): **LEGACY / compatibilidad temporal**. En data_freshness_expectations está marcado como legacy (migración 074). NO es fuente oficial para auditoría ni reconstrucción. Ver `docs/SOURCE_OF_TRUTH_REAL_AUDIT_V2.md`.
- **v_trips_real_canon** / **v_trips_real_canon_120d**: unión legacy (trips_all + trips_2026) con corte por fecha. Pendiente migración a trips_2025 + trips_2026.
- **ops.v_real_trips_enriched_base**: unión oficial trips_2025 + trips_2026 (migración 118). Usada por Business Slice.

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
