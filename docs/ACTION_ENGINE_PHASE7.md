# Action Engine — Phase 7

**Fecha:** 2026-04-02
**Estado:** OPERATIVO — genera acciones reales priorizadas
**Migración:** 123_action_engine_catalog_and_output

---

## 1. Qué es

El Action Engine traduce métricas y alertas de calidad en **acciones operativas concretas, priorizadas y trazables**. No es un dashboard: es lógica estructurada de decisiones.

**Pregunta central:** "¿Dónde actuar hoy y con qué prioridad?"

---

## 2. Catálogo de acciones

14 acciones operativas definidas en `ops.action_catalog`:

| ID | Acción | Tipo | Severidad | Trigger | Owner |
|----|--------|------|-----------|---------|-------|
| INGEST_ESCALATE | Escalar ingestión de comisión | finance | critical | pct_proxy >= 95% | data_engineering |
| TRIPS_DROP_CITY | Investigar caída de viajes | ops | high | trips WoW <= -20% | ops_city_manager |
| DRIVER_REACTIVATION | Reactivar conductores | supply | high | drivers WoW <= -15% | supply_team |
| TICKET_DROP | Revisar pricing | pricing | medium | ticket WoW <= -15% | pricing_team |
| CANCEL_RATE_SPIKE | Auditar cancelaciones | ops | high | cancel rate +5pp | ops_team |
| ZERO_REVENUE_CITY | Revenue cero en ciudad | finance | critical | revenue = 0 | data_engineering |
| REVENUE_DROP_CITY | Caída de revenue | finance | high | revenue WoW <= -30% | ops_city_manager |
| NAN_RAW_DATA | Limpiar NaN en fuente | data_quality | high | nan_count > 0 | data_engineering |
| DRIFT_CROSS_CHAIN | Drift entre cadenas | data_quality | medium | drift >= 15% | data_engineering |
| PARK_ANOMALY | Parque anómalo | ops | medium | anomaly_score >= 3 | ops_team |
| LOW_PRODUCTIVITY | Baja productividad | supply | medium | tpd WoW <= -20% | supply_team |
| MISSING_REVENUE | Viajes sin revenue | data_quality | high | missing >= 5% | data_engineering |
| ACQUISITION_NEEDED | Captación conductores | acquisition | high | demand/supply >= 3 | marketing |
| DATA_FRESHNESS | Datos desactualizados | data_quality | high | hours_old >= 48 | data_engineering |

---

## 3. Motor de decisiones

### Inputs

- `ops.mv_real_lob_day_v2` — trips, revenue, cancelaciones por ciudad/día
- `ops.revenue_quality_alerts` — alertas de calidad (últimas 24h)
- `ops.v_real_trip_fact_v2` — distribution de revenue source

### Reglas implementadas

| Regla | Métrica | Condición | Acción generada |
|-------|---------|-----------|-----------------|
| WoW trips | trips_wow_change_pct | <= -20% | TRIPS_DROP_CITY |
| WoW revenue | revenue_wow_change_pct | <= -30% | REVENUE_DROP_CITY |
| Zero revenue | city_revenue | = 0 con > 100 trips | ZERO_REVENUE_CITY |
| Cancel rate | cancel_rate_change_pp | >= +5pp | CANCEL_RATE_SPIKE |
| Proxy excesivo | pct_proxy | >= 95% (de alertas) | INGEST_ESCALATE |
| NaN raw | nan_count_raw | > 0 (de alertas) | NAN_RAW_DATA |
| Missing revenue | pct_missing | >= 5% (de alertas) | MISSING_REVENUE |
| Drift cadenas | drift_pct | >= 15% (de alertas) | DRIFT_CROSS_CHAIN |
| Freshness | hours_since_last_trip | >= 48h | DATA_FRESHNESS |

---

## 4. Priorización

```
priority_score = severity_weight × volume_factor × revenue_factor
```

| Componente | Cálculo |
|-----------|---------|
| severity_weight | critical=100, high=70, medium=40, low=10 |
| volume_factor | min(10, max(1, log2(completed_trips + 1))) |
| revenue_factor | min(10, max(1, log2(abs(revenue) + 1) / 3)) |

Acciones globales (sin ciudad específica) usan los pesos base sin multiplicadores de volumen.

---

## 5. Resultado real (2026-04-02)

| # | Prioridad | Severidad | Acción | Detalle |
|---|-----------|-----------|--------|---------|
| 1 | 100.0 | CRITICAL | Escalar ingestión comisión | 100% proxy (884,958 viajes) |
| 2 | 70.0 | HIGH | Limpiar NaN en datos fuente | 3 NaN en trips_2026 |
| 3 | 70.0 | HIGH | Datos desactualizados | day_v2: 473h sin refresh |
| 4 | 40.0 | MEDIUM | Drift entre cadenas | HF vs BS: 37.65% |

---

## 6. Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `GET /ops/action-engine/run` | GET | Ejecuta engine + persiste acciones |
| `GET /ops/action-engine/today?city=&severity=&limit=` | GET | Acciones del día (persistidas) |
| `GET /ops/action-engine/catalog` | GET | Catálogo de acciones disponibles |
| `POST /ops/action-engine/log?action_output_id=&action_id=&owner=&status=` | POST | Registrar ejecución de acción |

### Contrato de `/action-engine/today`

```json
{
  "date": "2026-04-02",
  "total": 4,
  "actions": [
    {
      "id": 1,
      "action_id": "INGEST_ESCALATE",
      "action_name": "Escalar problema de ingestión de comisión",
      "severity": "critical",
      "priority_score": 100.0,
      "reason": "Proxy coverage: 100.0% ...",
      "country": "",
      "city": "",
      "metric_name": "pct_proxy",
      "metric_value": 100.0,
      "threshold": 95,
      "suggested_owner": "data_engineering"
    }
  ]
}
```

---

## 7. Trazabilidad

### `ops.action_execution_log`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| action_output_id | FK → action_engine_output | Acción que se ejecutó |
| action_id | TEXT | ID del catálogo |
| execution_date | DATE | Cuándo se ejecutó |
| owner | TEXT | Quién la ejecutó |
| status | TEXT | pending / in_progress / done / ignored |
| notes | TEXT | Notas libres |

### Flujo

1. Engine genera acciones → `action_engine_output`
2. Operador revisa → `GET /action-engine/today`
3. Operador actúa → `POST /action-engine/log` con status
4. Historial auditable en `action_execution_log`

---

## 8. Cómo usar operativamente

### Diario

```bash
cd backend && python -m scripts.run_action_engine
```

### Via API

```
GET /ops/action-engine/run     → genera y persiste
GET /ops/action-engine/today   → consulta
```

### Flujo sugerido

1. Ejecutar engine al inicio del día (manual o cron)
2. Revisar acciones por severidad
3. Asignar owners
4. Registrar ejecución via /log
5. Revisar completitud al final del día

---

## 9. Archivos

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `backend/alembic/versions/123_action_engine_catalog_and_output.py` | CREADO | Catálogo, output, log |
| `backend/app/services/action_engine_service.py` | CREADO | Motor de decisiones |
| `backend/app/routers/ops.py` | MODIFICADO | 4 endpoints |
| `backend/scripts/run_action_engine.py` | CREADO | Script de ejecución |
| `docs/ACTION_ENGINE_PHASE7.md` | CREADO | Este documento |
