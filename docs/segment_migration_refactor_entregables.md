# Entregables: refactor segmentación semanal + Migration

## 1. Implementación realizada

- **FASE A:** Scan documentado en [segment_migration_refactor_scan.md](segment_migration_refactor_scan.md).
- **FASE B–E:** Migración Alembic `078_segment_taxonomy_elite_legend`: INSERT ELITE/LEGEND en `driver_segment_config`, cap FT 60–119, recreación de MVs con `ord`/`prev_ord` desde config (sin CASE hardcodeado).
- **FASE C–G:** Backend: `supply_service.py` (segment config ORDER BY ordering ASC, summary.stable en migration), `supply_definitions.py` (texto segments/migration/churned/reactivated).
- **FASE F–H:** Frontend: constante `segmentSemantics.js`, rediseño pestaña Migration (header, KPIs con Stable, insight, resumen por From, tabla sin lateral), glosario con leyenda de segmentos, park nombre en drilldown.
- **FASE J:** Script SQL de validación: [backend/scripts/sql/validate_segment_taxonomy.sql](../backend/scripts/sql/validate_segment_taxonomy.sql).

## 2. Archivos tocados

| Archivo | Cambio |
|---------|--------|
| `docs/segment_migration_refactor_scan.md` | Nuevo: mapeo previo obligatorio |
| `docs/segment_migration_refactor_entregables.md` | Nuevo: este documento |
| `backend/alembic/versions/078_segment_taxonomy_elite_legend.py` | Nuevo: migración additive + MVs con ordering desde config |
| `backend/app/services/supply_service.py` | get_supply_segment_config ORDER BY ordering ASC; get_supply_migration summary.stable |
| `backend/app/services/supply_definitions.py` | Definiciones segments, migration, churned, reactivated |
| `frontend/src/constants/segmentSemantics.js` | Nuevo: SEGMENT_ORDER, SEGMENT_LEGEND_MINIMAL, helpers |
| `frontend/src/components/SupplyView.jsx` | Fallback segmentos, Migration tab (header, KPIs, insight, resumen From, tabla sin lateral, park name en drilldown) |
| `frontend/src/components/DriverSupplyGlossary.jsx` | Leyenda de segmentos en entrada "Segments", import segmentSemantics |
| `backend/scripts/sql/validate_segment_taxonomy.sql` | Nuevo: validaciones post-cambio |

## 3. Decisiones técnicas

- **No destructivo:** Solo INSERT (ELITE, LEGEND) y UPDATE (FT max_trips_week) en config; recreación de MVs por dependencia, sin DROP de columnas ni tablas en uso.
- **Same-to-same:** Excluido de la tabla principal de Migration; se muestra como KPI "Stable" y en summary; opcionalmente consultable vía API (sigue en `data`, el front filtra `migration_type !== 'lateral'`).
- **Orden operativo:** Backend devuelve segment config con `ORDER BY ordering ASC`; frontend usa `SEGMENT_LEGEND_MINIMAL` y orden en resumen por From.
- **Legend/Elite:** Incluidos en config, MVs, alertas (recommended_action para ELITE/LEGEND) y en leyenda/glosario. Alias "Nivel Dios" solo en copy (segmentSemantics desc).

## 4. Compatibilidad

- Contrato API: se **extiende** (summary.stable); no se elimina ningún campo. Clientes que no usen `stable` siguen funcionando.
- Segment config: mismo esquema; orden de filas pasa a ASC (operativo). Frontend ya consumía el array y ordenaba/mapeaba; fallback actualizado a 6 segmentos.
- Migration `data`: incluye igual que antes las filas lateral; el frontend las oculta de la tabla principal y las refleja en el KPI Stable.

## 5. Migraciones

- **Sí:** Una migración Alembic (`078_segment_taxonomy_elite_legend`). **No destructiva:** no se borran columnas ni tablas; se recrean MVs (comportamiento estándar en esta cadena). Downgrade restaura MVs al estilo 067 (CASE de 5 segmentos) y marca ELITE/LEGEND con effective_to.

## 6. Cómo probar en local

1. Aplicar migración: `alembic upgrade head` (desde `backend/`).
2. Refrescar MVs de supply (si existe script): ejecutar refresh de `mv_driver_segments_weekly` y cadena (o el pipeline habitual).
3. Backend: `GET /ops/supply/segments/config` debe devolver filas con ELITE, LEGEND y ordering ASC. `GET /ops/supply/migration?park_id=...&from=...&to=...` debe incluir `summary.stable`.
4. Frontend: abrir Supply → Migration; comprobar header, KPIs (Stable), insight, resumen por From, tabla sin filas "lateral". Glosario "Ver definiciones" debe mostrar leyenda de segmentos bajo "Segments".
5. Validaciones: ejecutar [backend/scripts/sql/validate_segment_taxonomy.sql](../backend/scripts/sql/validate_segment_taxonomy.sql) y revisar distribución por segmento, masa Legend/Elite y transiciones.

## 7. Refresco de MVs

Tras `alembic upgrade head`, es necesario refrescar la cadena de MVs que depende de `mv_driver_segments_weekly`:

- `REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_driver_segments_weekly;`
- `REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_supply_segments_weekly;`
- `REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_supply_segment_anomalies_weekly;`
- `REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_supply_alerts_weekly;`

(Usar el script o procedimiento existente del proyecto si ya centraliza estos refreshes.)

## 8. Riesgos y pendientes

- **Riesgo:** Tras el refresh, datos históricos tendrán segment_week con ELITE/LEGEND y FT acotado a 60–119; rangos anteriores (p. ej. OCCASIONAL 1–4, CASUAL 5–19) no se han cambiado en esta entrega; si en el futuro se unifica "casual" 1–29, hará falta nueva versión de config (effective_from/to) y nuevo refresh.
- **Pendiente:** Decisión de negocio sobre PT 20–59 vs 30–59 (objetivo era pt 30–59; en esta entrega no se ha modificado PT/OCCASIONAL/CASUAL para no ampliar el alcance).

## 9. Checklist QA final

- [x] Scan previo documentado antes de implementar
- [x] No se inventan columnas; se usan existentes o extensión additive
- [x] Endpoints existentes no rotos (compatibilidad o extensión)
- [x] Migración no destructiva (no DROP de columnas/vistas en uso)
- [x] Segmentos visibles y consistentes (dormant, casual, pt, ft, elite, legend en config y leyenda)
- [x] Dormant visible y diferenciado de Churned/Revival en definiciones
- [x] Elite y Legend en config, MVs, alertas y UI (leyenda, fallback)
- [x] Migration: same-to-same no en tabla principal; jerarquía visual (header, KPIs, insight, resumen From, tabla)
- [x] Semana en formato S##-YYYY en header y tabla
- [x] Tooltips/leyenda explican segmentos (glosario + SEGMENT_LEGEND_MINIMAL)
- [x] Park mostrado por nombre en drilldown cuando aplica
- [x] Riesgos y pasos de refresco documentados
