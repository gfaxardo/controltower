# FRESHNESS GOVERNANCE — FINAL REPORT

**Fecha**: 2026-05-30
**Motor**: Control Foundation
**Gate**: CF-H1D

---

## 1. Estado: **GO**

Omniview Freshness Governance implementado y funcional. Build PASS. Endpoint activo. UI integrada.

---

## 2. Componentes Creados

| Capa | Archivo | Descripción |
|------|---------|-------------|
| Backend Service | `backend/app/services/omniview_freshness_governance_service.py` | Consulta liviana MAX(date) de RAW → FACT_DAILY → FACT_WEEKLY → FACT_MONTHLY → PROJECTION |
| Backend Endpoint | `backend/app/routers/ops.py` (nuevo endpoint) | `GET /ops/omniview/freshness` |
| Frontend API | `frontend/src/services/api.js` | `getOmniviewFreshnessGovernance()` |
| Frontend UI | `frontend/src/components/omniview/freshness/OmniviewFreshnessGovernanceCard.jsx` | Card compacta con estados OK/WARNING/BLOCKED |
| Wire | `frontend/src/components/BusinessSliceOmniviewMatrix.jsx` | Integración en Vs Proyección |
| Health Check | `backend/scripts/check_omniview_serving_freshness.py` | Script de verificación (ya existía, mejorado) |

---

## 3. Reglas de Status

| Capa | OK | WARNING | BLOCKED |
|------|----|---------|---------|
| Daily | lag ≤ 1 día | 2-3 días | > 3 días |
| Weekly | lag ≤ 7 días | 8-10 días | > 10 días |
| Monthly | mes actual o anterior | atraso > 1 mes | — |
| Projection | lag ≤ 1 día | 2-3 días | > 3 días |

---

## 4. Remediation

```
"Ejecutar python -m scripts.refresh_omniview_real_slice --force
 y luego python -m scripts.check_omniview_serving_freshness"
```

Visible en `<details>` expandible en la UI cuando status es WARNING o BLOCKED.

---

## 5. Evidencia Build

```
✓ built in 5.54s
dist/assets/BusinessSliceOmniviewMatrix-CzMzDWDM.js  325.14 kB │ gzip: 89.55 kB
0 errors, 0 warnings (solo chunk size pre-existente)
```

---

## 6. Evidencia Runtime

```
GET /ops/omniview/freshness → 200 OK
{
  "status": "blocked",
  "raw": { "max_date": "2026-05-29" },
  "facts": {
    "daily": { "max_date": "2026-04-30", "lag_days": 30, "status": "blocked" },
    "weekly": { "max_week_start": "2026-05-25", "lag_days": 5, "status": "ok" },
    "monthly": { "max_month_start": "2026-05-01", "status": "ok" },
    "projection_daily": { "max_date": "2026-05-30", "lag_days": 0, "status": "ok" }
  }
}
```

---

## 7. Riesgos Pendientes

| Riesgo | Severidad | Nota |
|--------|-----------|------|
| FACT_DAILY sigue en April 30 | MEDIUM | Backfill manual requerido. El APScheduler depende del backend vivo. |
| Governance detecta pero no corrige | LOW | Por diseño — solo alerta y guía remediación. |
| UI card puede ser ignorada si es muy sutil | LOW | El estado BLOCKED usa colores rojos visibles. |

---

## 8. Criterios GO

- [x] Endpoint `/ops/omniview/freshness` existe
- [x] daily/week/month/projection status visible
- [x] blocked no pasa silencioso (rojo + mensaje)
- [x] remediation clara
- [x] script health check existe (`check_omniview_serving_freshness.py`)
- [x] UI compacta
- [x] Build PASS
- [x] Omniview sigue funcionando (no regresión)
- [x] Priority Layer no afectada
- [x] Evolution no tocado

---

## 9. Documentos Generados

| Documento | Path |
|-----------|------|
| Governance Docs | `docs/omniview/FRESHNESS_GOVERNANCE.md` |
| QA | `docs/omniview/FRESHNESS_GOVERNANCE_QA.md` |
| Final Report | `docs/omniview/FRESHNESS_GOVERNANCE_REPORT.md` |

