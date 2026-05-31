# FRESHNESS GOVERNANCE — DOCUMENTATION

**Fecha**: 2026-05-30
**Motor**: Control Foundation
**Gate**: CF-H1D

---

## 1. Flujo de Gobernanza

```
RAW (public.trips_2026)
  → FACT_DAILY (ops.real_business_slice_day_fact)
    → FACT_WEEKLY (ops.real_business_slice_week_fact)
      → FACT_MONTHLY (ops.real_business_slice_month_fact)
        → PROJECTION SERVING (serving.omniview_projection_daily_fact)
          → OMNIVIEW UI
```

Cada capa se refresca independientemente. Si una capa se atrasa, las siguientes heredan el atraso.

---

## 2. Status Rules

### Daily (FACT_DAILY vs RAW)

| Lag | Status | Significado |
|-----|--------|-------------|
| ≤ 1 día | `ok` | Fresco. Datos del día anterior. |
| 2-3 días | `warning` | Atraso leve. Puede ser normal en fines de semana. |
| > 3 días | `blocked` | Atraso significativo. Requiere acción. |

### Weekly (FACT_WEEKLY)

| Lag | Status |
|-----|--------|
| ≤ 7 días | `ok` |
| 8-10 días | `warning` |
| > 10 días | `blocked` |

No se marca blocked solo porque la semana actual está parcial.

### Monthly (FACT_MONTHLY)

Se considera OK si el último mes procesado es el mes actual o el anterior. Si el mes actual es Junio y el último month_fact es Abril, se marca como warning.

### Projection Serving

Debe estar alineado con day_fact. Misma regla de lag que daily.

---

## 3. Por qué el APScheduler no garantiza refresh en dev

El `BackgroundScheduler` de APScheduler corre dentro del proceso FastAPI. Si el backend se detiene:
- Terminal cerrada
- Crash
- Reinicio del servidor
- Ventana de desarrollo cerrada

Los jobs programados (04:00 y 05:00) no se ejecutan. En producción esto se mitiga con el servidor corriendo 24/7 como servicio. En dev, el refresh depende de ejecución manual o de mantener el backend vivo.

---

## 4. Remediation

Si el estado es `blocked`:

```bash
cd backend

# Refresh day_fact + week_fact + month_fact
python -m scripts.refresh_omniview_real_slice --force

# Refresh projection serving fact
python -m scripts.refresh_omniview_projection_facts \
  --plan-version ruta27_2026_04_21 --grain daily --year 2026

# Verify
python -m scripts.check_omniview_serving_freshness
```

---

## 5. Endpoint

```
GET /ops/omniview/freshness
```

Response:
```json
{
  "status": "ok",
  "raw": { "max_date": "2026-05-29" },
  "facts": {
    "daily": { "max_date": "2026-05-29", "lag_days": 0, "status": "ok" },
    "weekly": { "max_week_start": "2026-05-25", "lag_days": 5, "status": "ok" },
    "monthly": { "max_month_start": "2026-05-01", "status": "ok" },
    "projection_daily": { "max_date": "2026-05-30", "lag_days": 0, "status": "ok" }
  },
  "message": "Omniview freshness OK",
  "remediation": null
}
```

---

## 6. Health Check Script

```bash
cd backend
python -m scripts.check_omniview_serving_freshness
python -m scripts.check_omniview_serving_freshness --max-lag-days 2
```

Sale con exit 1 si cualquier capa excede el lag máximo configurado.

---

## 7. UI Card

Componente: `frontend/src/components/omniview/freshness/OmniviewFreshnessGovernanceCard.jsx`

- Compacta (1 línea si OK)
- Muestra RAW → Daily → Weekly → Monthly → Projection
- Colores: verde (OK), ámbar (WARNING), rojo (BLOCKED)
- Remediation en `<details>` expandible
- Solo visible en modo Vs Proyección (`isProjectionMode && heavyQueriesEnabled`)

