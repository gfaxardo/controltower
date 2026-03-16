# Memo técnico final: Huecos de margen en fuente (módulo REAL)

## 1. Definición canónica de “hueco de margen”

- **Hueco de margen (anomalía principal):** Viajes **completados** con `comision_empresa_asociada` (margen) **NULL** en la fuente. Es decir: `completed_trips_without_margin` = completados sin margen en fuente.
- **Anomalía secundaria:** Viajes **cancelados** que sí tienen comisión/margen en fuente (`cancelled_trips_with_margin`). Inconsistencia de consistencia de datos, no hueco de cobertura.

## 2. Por qué solo aplica a completados

- Regla de negocio: a los viajes **completados** sí se les exige comisión/margen. Si están completados y el campo está NULL, la fuente no está entregando un dato que debería existir.
- Los cancelados no generan margen esperado; por tanto “cancelado + margen NULL” es **normal** y no se considera error.

## 3. Por qué cancelados sin margen no son error

- No se exige comisión a viajes cancelados. Que el campo esté vacío en cancelados es coherente con la regla de negocio.

## 4. Por qué cancelados con margen sí son anomalía de consistencia

- Es poco esperable que un viaje cancelado tenga comisión cargada. Si aparece, se considera inconsistencia de datos y se reporta por separado (anomalía secundaria), sin mezclarla con el hueco de completados.

## 5. Cómo se calcula la severidad

- **Anomalía principal (completados sin margen):**
  - **OK:** 0% completados sin margen.
  - **INFO:** > 0%.
  - **WARNING:** > 0,5% (umbral `MARGIN_GAP_PCT_WARNING`).
  - **CRITICAL:** > 2% o bien días con completed_trips > 0 y completed_trips_with_margin = 0 (cobertura 0% en periodo reciente).
- **Anomalía secundaria (cancelados con margen):**
  - **WARNING:** cancelled_with_margin_pct > 5%.
  - **CRITICAL:** cancelled_with_margin_pct > 10%.

Constantes en `backend/app/services/real_margin_quality_constants.py`.

## 6. Dónde se persiste

- Tabla **ops.real_margin_quality_audit** (migración 104): `alert_code`, `severity`, `detected_at`, `grain_date`, `affected_trips`, `denominator_trips`, `pct`, `message_humano_legible`, `metadata` (JSON). Códigos: `REAL_MARGIN_SOURCE_GAP_COMPLETED`, `REAL_CANCELLED_WITH_MARGIN`. El script de auditoría escribe con deduplicación por (alert_code, grain_date) del mismo día.

## 7. Cómo se expone en API

- **GET /ops/real/margin-quality** (`days_recent`, `findings_limit`): devuelve resumen (aggregate, severity_primary/secondary, margin_quality_status), flags (`has_margin_source_gap`, `margin_coverage_incomplete`, `has_cancelled_with_margin_issue`), lista `findings` y listas `affected_days`, `affected_week_dates`, `affected_month_dates` para badges en drill.
- **POST /ops/real/margin-quality/run**: ejecuta `scripts.audit_real_margin_source_gaps --days 90 --persist` y persiste en ops.real_margin_quality_audit.

## 8. Cómo se muestra en UI

- **Pestaña Real:** Card **RealMarginQualityCard** bajo el banner de frescura: estado (OK / Info / Aviso / Crítico), “Cobertura de margen en completados: XX.X%”, cantidad de completados sin margen, nota de que cancelados sin margen no son error. Si hay anomalía secundaria, bloque aparte para “cancelados con margen”.
- **Drill REAL:** Badge “Cobertura incompleta” en la celda de periodo cuando ese periodo (semana o mes) está en `affected_week_dates` o `affected_month_dates` (periodos con al menos un día con hueco de margen).

## 9. Cómo se integra al flujo hourly-first / REAL

- Cálculo sobre **ops.v_real_trip_fact_v2** (lee de v_trips_real_canon_120d): `trip_outcome_norm` (completed/cancelled) y `margin_total` (= comision_empresa_asociada). No se modifica la cadena hourly-first ni el populate del drill; solo se añade un job de auditoría que corre después del audit de freshness en **run_pipeline_refresh_and_audit** (paso “auditoría de calidad de margen”).

## 10. Archivos modificados o creados

| Archivo | Cambio |
|---------|--------|
| docs/REAL_MARGIN_SOURCE_GAP_FASE0_SCAN.md | Nuevo: scan FASE 0 |
| docs/REAL_MARGIN_SOURCE_GAP_CANONICAL_DEFINITION.md | Nuevo: definición canónica |
| docs/REAL_MARGIN_SOURCE_GAP_MEMO_FINAL.md | Nuevo: este memo |
| backend/app/services/real_margin_quality_constants.py | Nuevo: constantes y severidad |
| backend/app/services/real_margin_quality_service.py | Nuevo: resumen, findings, affected periods |
| backend/scripts/audit_real_margin_source_gaps.py | Nuevo: script de auditoría |
| backend/alembic/versions/104_real_margin_quality_audit.py | Nuevo: tabla ops.real_margin_quality_audit |
| backend/app/routers/ops.py | GET /real/margin-quality, POST /real/margin-quality/run |
| backend/scripts/run_pipeline_refresh_and_audit.py | Ejecución de audit_real_margin_source_gaps tras freshness |
| frontend/src/services/api.js | getRealMarginQuality |
| frontend/src/components/RealMarginQualityCard.jsx | Nuevo: card calidad de margen |
| frontend/src/App.jsx | Render de RealMarginQualityCard cuando activeTab === 'real' |
| frontend/src/components/RealLOBDrillView.jsx | Badge “Cobertura incompleta” por periodo |
| backend/tests/test_real_margin_quality.py | Nuevo: tests severidad y estructura API |

## 11. Cómo validar manualmente que quedó bien

- Ver **Checklist de validación manual** más abajo.

---

# Checklist de validación manual

## 1. Comando(s) a correr

```bash
cd backend
# Aplicar migración (tabla de auditoría)
python -m alembic upgrade 104_real_margin_quality_audit

# Auditoría de margen (imprime resumen y, con --persist, escribe en ops.real_margin_quality_audit)
python -m scripts.audit_real_margin_source_gaps --days 90 --persist
```

## 2. Endpoint(s) a revisar

- **GET** `http://localhost:8000/ops/real/margin-quality?days_recent=90`  
  Debe devolver JSON con `aggregate`, `severity_primary`, `severity_secondary`, `has_margin_source_gap`, `margin_coverage_incomplete`, `findings`, `affected_week_dates`, `affected_month_dates`.
- **POST** `http://localhost:8000/ops/real/margin-quality/run`  
  Ejecuta el script y devuelve `ok`, `returncode`, `stdout`, `stderr`.

## 3. Pantalla(s) UI donde debe verse la alerta

- **Pestaña Real:** Debajo del banner de frescura, la card “Calidad de margen” con estado y cobertura. Si hay hueco, texto con cantidad afectada y nota sobre cancelados.
- **Drill REAL (tabla por periodo):** En la columna del periodo, badge “Cobertura incompleta” en las filas cuyo periodo está afectado.

## 4. Ejemplo de caso OK

- Base con completados todos con margen y cancelados sin margen (o sin cancelados con margen). Card en estado “OK”, cobertura 100%. Sin badges en el drill (o listas `affected_*` vacías).

## 5. Ejemplo de caso Warning/Critical

- Inyectar o tener datos recientes con completados sin margen (p. ej. muchos con margin_total NULL en v_real_trip_fact_v2). Tras ejecutar el script o recargar la pestaña Real, la card debe pasar a Aviso o Crítico según % y “Cobertura de margen en completados” &lt; 100%. En el drill, los periodos con hueco deben mostrar el badge “Cobertura incompleta”.

## 6. Cómo confirmar que cancelados sin margen NO disparan error

- La métrica de anomalía principal usa solo `trip_outcome_norm = 'completed'` y `margin_total IS NULL`. Los cancelados no entran en `completed_trips_without_margin`. Comprobar en el agregado: aumentar cancelados sin margen no debe subir `completed_trips_without_margin` ni la severidad principal.

## 7. Cómo confirmar que completados sin margen SÍ disparan error

- Con datos donde haya completados y `margin_total` NULL en v_real_trip_fact_v2, `completed_trips_without_margin` &gt; 0 y la severidad principal debe ser INFO/WARNING/CRITICAL según umbrales. La card debe reflejarlo.

## 8. Cómo confirmar que cancelados con margen se detectan aparte

- La severidad secundaria y el flag `has_cancelled_with_margin_issue` dependen de `cancelled_trips_with_margin`. En la card, el bloque “Anomalía de consistencia: X viajes cancelados con comisión/margen” solo aparece cuando hay anomalía secundaria. No se mezcla con el mensaje principal de “completados sin margen”.
