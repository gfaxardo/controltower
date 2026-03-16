# Pasos ejecutados — Evidencia (corrección E2E REAL)

**Fecha ejecución:** 2026-03-16

---

## 1. Diagnóstico ruptura (investigate_real_rupture_2026)

**Comando:** `cd backend; python -m scripts.investigate_real_rupture_2026`  
**Resultado:** OK (exit 0). FASE 5 (cobertura por país) dio timeout; el resto completó.

**Evidencia:**
- **trips_2026:** hasta 2026-02-09 con_comision ~22.6%, con_pago_corp 1415; desde 2026-02-16 con_comision=0, con_pago_corp=0.
- **v_real_trip_fact_v2:** mismo patrón (con_margin y b2b=0 desde 2026-02-16).
- **mv_real_lob_day_v2:** filas_con_margin y b2b_trips=0 desde 2026-02-16.
- **mv_real_lob_week_v3:** sum_margin=None, b2b_trips=0 desde 2026-02-16.
- **mv_real_lob_month_v3:** 2026-03 sum_margin=None, b2b_trips=0.

---

## 2. Auditoría cobertura comercial (audit_trips_2026_commercial_coverage)

**Comando:** `cd backend; python -m scripts.audit_trips_2026_commercial_coverage --verbose`  
**Resultado:** FAIL (exit 1), como se esperaba mientras la fuente siga rota.

**Salida:**  
Semanas 2026-02-16, 2026-02-23, 2026-03-02, 2026-03-09 con comision_pct=0% y pago_corp_count=0. Mensaje: "Posible ruptura de fuente (comision_empresa_asociada/pago_corporativo). Revisar proceso que alimenta trips_2026."

---

## 3. Pipeline refresh + populate (sin coverage audit)

**Comando:**  
`cd backend; python -m scripts.run_pipeline_refresh_and_audit --skip-coverage-audit --drill-days 60 --drill-weeks 8 --drill-months 4`

**Resultado:**
- **Refresh cadena hourly-first:** OK (hour → day → week → month).
- **Populate real_drill_dim_fact:** OK (days=60, weeks=8, months=4).
- **Refresh Driver Lifecycle MVs:** OK.
- **Refresh Supply MVs:** OK.
- **Auditoría freshness:** OK (escrita en ops.data_freshness_audit).
- **Auditoría cobertura trips_2026:** Omitida (--skip-coverage-audit).
- **Auditoría margin quality (audit_real_margin_source_gaps):** Timeout a 180 s → pipeline terminó con exit 1.

Conclusión: refresh y populate se ejecutaron correctamente; el fallo fue solo por timeout en el script de huecos de margen.

---

## 4. Llamadas API (runtime backend)

**Servidor:** http://127.0.0.1:8000 (uvicorn)

### GET /ops/real-lob/drill?period=week&desglose=LOB&segmento=all

- **Status:** 200.
- **Respuesta:** Objeto con `countries` (pe, co), cada uno con `kpis` agregados.
- **PE:** margen_total=1238983.1, margen_trip=0.6758, viajes_b2b=19075 (agregado sobre ventana reciente, incluye semanas buenas).
- **CO:** margen_total=384324593.74, margen_trip=276.18, viajes_b2b=0.
- **meta:** last_closed_week=2026-03-09, breakdown_valid=false.

### GET /ops/real-margin-quality?days_recent=90&findings_limit=5

- **Status:** 200.
- **Respuesta:** severity_primary=OK, has_margin_source_gap=false, margin_quality_status=OK, findings=[], affected_days/weeks/months vacíos.

---

## 5. Pasos que no se pueden hacer desde este repo

- **Corregir el proceso que escribe en trips_2026:** Ese proceso es externo; debe hacerlo el equipo/sistema que mantiene la ingestión.
- **Backfill en trips_2026:** Requiere que el proceso externo se corrija y se re-cargue la ventana desde 2026-02-16, o que se proporcione un CSV y se ejecute `backfill_trips_2026_commercial_from_csv.py`.
- **Validación UI (screenshots):** Requiere revisión manual en el navegador.

---

## 6. Próximos pasos recomendados

1. Identificar y corregir el proceso externo que alimenta `trips_2026` (comision_empresa_asociada, pago_corporativo).
2. Ejecutar backfill (re-carga o CSV + `backfill_trips_2026_commercial_from_csv.py`).
3. Ejecutar pipeline **sin** --skip-coverage-audit:  
   `python -m scripts.run_pipeline_refresh_and_audit`  
   (opcional: aumentar timeout de audit_real_margin_source_gaps o ejecutarlo aparte).
4. Validar de nuevo: `investigate_real_rupture_2026`, `audit_trips_2026_commercial_coverage`, APIs y UI.
