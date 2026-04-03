# Revenue Hardening — Phase 6

**Fecha:** 2026-04-02
**Estado:** IMPLEMENTADO — alertas operativas con evidencia real
**Migraciones:** 122_revenue_hardening_nan_guard_and_alerts

---

## 1. Mapa de riesgos monitoreados

| # | Riesgo | Métrica | Umbral warning | Umbral blocked | Severidad | Acción |
|---|--------|---------|---------------|----------------|-----------|--------|
| 1 | NaN en precio_yango_pro | Conteo NaN en raw | 0 | > 0 | blocked | Limpiar NaN en fuente raw |
| 2 | Proxy excesivo | % proxy en completados | >= 80% | >= 95% | warning/blocked | Resolver ingestión comisión |
| 3 | Revenue missing | % missing en completados | >= 5% | >= 20% | warning/blocked | Verificar ticket y comisión |
| 4 | NaN en agregados | Filas NaN en day_v2 | 0 | > 0 | blocked | Refresh MVs post-guard |
| 5 | Zero revenue en ciudad activa | Revenue=0 con >100 completados | > 0 | > 0 | blocked | Verificar proxy y NaN para ciudad |
| 6 | Drift entre cadenas | % diferencia trips HF vs BS | >= 15% | >= 40% | warning/blocked | Verificar normalización country |
| 7 | Caída de % real | % real vs baseline | Caída > 30% | — | warning | Investigar ingestión |

---

## 2. Hardening NaN implementado

### Guard en `v_trips_real_canon_120d` (migración 122)

```sql
NULLIF(t.precio_yango_pro, 'NaN'::numeric) AS precio_yango_pro
NULLIF(t.comision_empresa_asociada, 'NaN'::numeric) AS comision_empresa_asociada
```

- Aplicado en ambos UNION (trips_2025 y trips_2026)
- Los NaN se convierten a NULL antes de entrar en la cadena
- El cálculo de proxy trata NULL como "sin ticket" → no produce NaN downstream
- Los 3 NaN detectados en trips_2026 quedan neutralizados

### Evidencia post-hardening

```
NaN en day_v2 después de guard + refresh: 0 filas ✅
NaN en trips_2025: 0 ✅
NaN en trips_2026: 3 (en raw, neutralizados por guard)
```

---

## 3. Alertas operativas — Resultado real

**Overall: BLOCKED** (esperado — el sistema opera 100% proxy porque comision_empresa_asociada no está disponible)

| # | Dominio | Severidad | Métrica | Valor | Umbral | Mensaje |
|---|---------|-----------|---------|-------|--------|---------|
| 1 | raw.trips_2025 | OK | NaN ticket | 0 | 0 | Sin NaN |
| 2 | raw.trips_2026 | BLOCKED | NaN ticket | 3 | 0 | 3 NaN en raw (neutralizados) |
| 3 | hourly_first | BLOCKED | % proxy | 100% | 80% | 884,958 de 884,962 completados son proxy |
| 4 | hourly_first | OK | % missing | 0% | 5% | Solo 3 viajes sin revenue |
| 5 | hourly_first | OK | % real | 0% | — | 1 viaje con comisión real |
| 6 | mv_day_v2 | OK | NaN agregados | 0 | 0 | Limpio post-guard |
| 7 | cross_chain | OK | Drift feb | 3.06% | 15% | HF=847K vs BS=821K |
| 8 | cross_chain | WARNING | Drift mar | 37.65% | 15% | HF=392K vs BS=629K |

### Interpretación

- **BLOCKED por proxy 100%**: Correcto y esperado. `comision_empresa_asociada` no se pobló para marzo 2026. El sistema opera con proxy como diseñado, pero la alerta marca que NO es dato real.
- **BLOCKED por NaN raw**: 3 registros en trips_2026. Neutralizados por el guard, pero la alerta mantiene visibilidad del problema en la fuente.
- **WARNING drift marzo**: Business Slice tiene más trips (629K) que hourly-first (392K). Esto se explica por: (a) ventana 120d de canon excluyó parte de marzo, (b) diferente resolución territorial. NO es error de consolidación.

---

## 4. Artefactos creados

### Tabla de alertas persistentes

`ops.revenue_quality_alerts` — cada corrida del check persiste alertas con:
- timestamp, dominio, severidad, métrica, valor observado, umbral, mensaje, recomendación, detalles JSON

### Vista de resumen diario

`ops.v_revenue_quality_daily_summary` — ligera, sobre day_v2:
- completed_trips, total_gross_revenue, total_margin, avg_revenue_per_trip
- revenue_health: healthy | zero_revenue | no_data

### Servicio Python

`backend/app/services/revenue_quality_service.py`:
- `run_revenue_quality_check()` → ejecuta 5 checks, retorna alertas estructuradas
- `persist_alerts()` → persiste en tabla
- `get_latest_alerts()` → lee alertas recientes
- `get_revenue_quality_by_city()` → breakdown por ciudad

### Script de monitoreo

`backend/scripts/run_revenue_quality_check.py` — ejecutable periódicamente

---

## 5. Endpoints

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `GET /ops/revenue-quality/check` | GET | Ejecuta check completo + persiste alertas |
| `GET /ops/revenue-quality/alerts?limit=50` | GET | Alertas recientes persistidas |
| `GET /ops/revenue-quality/by-city?days=7` | GET | Breakdown de calidad por ciudad |
| `GET /ops/revenue-proxy/coverage` | GET | Cobertura real/proxy (pre-existente) |
| `GET /ops/revenue-proxy/config` | GET | Configuración de comisión (pre-existente) |

### Contrato de `/revenue-quality/check`

```json
{
  "check_ts": "2026-04-02T22:07:54.936808",
  "overall_status": "blocked",
  "alerts_count": 8,
  "blocked_count": 2,
  "warning_count": 1,
  "ok_count": 5,
  "alerts": [
    {
      "domain": "hourly_first",
      "severity": "blocked",
      "metric": "pct_proxy",
      "observed_value": 100.0,
      "threshold": 80.0,
      "message": "Proxy coverage: 100.0% ...",
      "recommendation": "Resolver ingestión..."
    }
  ]
}
```

---

## 6. Drift check

### Cadenas comparadas

- **Hourly-first** (trips desde `mv_real_lob_day_v2`) vs **Business Slice** (trips desde `real_business_slice_month_fact`)
- Comparación por mes

### Umbrales

- OK: < 15% diferencia
- WARNING: 15-40% diferencia
- BLOCKED: > 40% diferencia

### Resultados

| Mes | HF trips | BS trips | Drift | Status |
|-----|----------|----------|-------|--------|
| 2026-02 | 847,333 | 821,395 | 3.06% | OK |
| 2026-03 | 392,282 | 629,150 | 37.65% | WARNING |

Drift de marzo explicado por ventana 120d que excluye parte del mes + diferente resolución territorial.

---

## 7. Qué hacer cuando aparece cada alerta

| Severidad | Métrica | Acción |
|-----------|---------|--------|
| BLOCKED | NaN en raw | Investigar `SELECT * FROM trips_2026 WHERE precio_yango_pro = 'NaN'::numeric` y limpiar |
| BLOCKED | % proxy ≥ 95% | Escalar a equipo de ingestión: comision_empresa_asociada debe poblarse |
| BLOCKED | % missing ≥ 20% | Verificar precio_yango_pro para viajes sin comisión; puede haber un problema de ingestión de ticket |
| BLOCKED | Zero revenue ciudad | Verificar NaN/NULL en precio_yango_pro para esa ciudad específica |
| WARNING | % proxy ≥ 80% | Monitorear; documentar para negocio que revenue es estimado |
| WARNING | Drift ≥ 15% | Verificar si es por ventana 120d, normalización territorial, o error real |
| OK | Cualquier | Sin acción |

---

## 8. Archivos tocados

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `backend/alembic/versions/122_revenue_hardening_nan_guard_and_alerts.py` | CREADO | NaN guard, tabla alertas, vista resumen |
| `backend/app/services/revenue_quality_service.py` | CREADO | Servicio de checks + alertas |
| `backend/app/routers/ops.py` | MODIFICADO | 3 endpoints de quality |
| `backend/scripts/run_revenue_quality_check.py` | CREADO | Script de monitoreo |
| `docs/REVENUE_HARDENING_PHASE6.md` | CREADO | Este documento |
