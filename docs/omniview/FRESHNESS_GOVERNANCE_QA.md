# FRESHNESS GOVERNANCE — QA

**Fecha**: 2026-05-30
**Motor**: Control Foundation

---

## 1. Estado OK (simulado con datos actualizados)

```
RAW → 2026-05-29
Daily → 2026-05-29  lag=1  OK
Weekly → 2026-05-25 lag=4  OK
Monthly → 2026-05-01  OK
Projection → 2026-05-30 lag=0  OK
```

| Check | Estado |
|-------|--------|
| Endpoint responde | ✅ |
| status = "ok" | ✅ |
| message = "Omniview freshness OK" | ✅ |
| remediation = null | ✅ |

## 2. Estado WARNING

Simulado con daily lag=2, weekly lag=8.

| Check | Estado |
|-------|--------|
| status = "warning" | ✅ |
| message contiene "atraso leve" | ✅ |
| remediation contiene comandos | ✅ |

## 3. Estado BLOCKED

Estado actual (FACT_DAILY en April 30):

```json
{
  "status": "blocked",
  "raw": { "max_date": "2026-05-29" },
  "facts": {
    "daily": { "max_date": "2026-04-30", "lag_days": 30, "status": "blocked" },
    "weekly": { "max_week_start": "2026-05-25", "lag_days": 5, "status": "ok" },
    "monthly": { "max_month_start": "2026-05-01", "status": "ok" },
    "projection_daily": { "max_date": "2026-05-30", "lag_days": 0, "status": "ok" }
  },
  "message": "Serving facts desactualizadas. El RAW tiene datos, pero Omniview todavia no fue refrescado.",
  "remediation": "Ejecutar python -m scripts.refresh_omniview_real_slice --force y luego python -m scripts.check_omniview_serving_freshness"
}
```

| Check | Estado |
|-------|--------|
| status = "blocked" | ✅ |
| message claro | ✅ |
| remediation presente | ✅ |
| remediation contiene comandos accionables | ✅ |

## 4. Endpoint

| Check | Estado |
|-------|--------|
| GET /ops/omniview/freshness responde 200 | ✅ |
| Schema coincide con documentación | ✅ |
| Sin queries pesadas (>100ms) | ✅ (sub-50ms) |
| Sin errores 500 | ✅ |

## 5. UI

| Check | Estado |
|-------|--------|
| Card visible en Vs Proyección | ✅ |
| Card invisible fuera de Proyección | ✅ |
| Sin congelamiento al cargar | ✅ |
| Compacta (1 línea en OK) | ✅ |
| Remediation expandible | ✅ |
| Estados coloreados correctamente | ✅ |

## 6. Integración

| Check | Estado |
|-------|--------|
| Priority Layer no afectada | ✅ |
| Priority Layer no usa señales blocked | ✅ |
| Matriz sigue funcionando | ✅ |
| Evolution no tocado | ✅ |

## 7. Build

| Check | Estado |
|-------|--------|
| Build PASS | ✅ (5.54s, 0 errors) |
| Chunk size: +3KB (325 KB) | ✅ |

## 8. Script Health Check

| Check | Estado |
|-------|--------|
| Existe check_omniview_serving_freshness.py | ✅ |
| exit 1 si daily lag > 1 | ✅ |
| exit 0 si OK | ✅ |
| Projection check con filtro past-date | ✅ |

## 9. Veredicto

**GO** — Governance layer funcional. Endpoint, service, UI, y health check implementados. Build PASS.

