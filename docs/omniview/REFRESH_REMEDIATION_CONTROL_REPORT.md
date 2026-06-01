# REFRESH REMEDIATION CONTROL — REPORTE FINAL

**Motor:** Control Foundation  
**Ticket:** CF-H1G  
**Fecha:** 2026-05-31  
**Estado:** COMPLETADO  

---

## 1. Política Dev/Prod

**Documento:** `docs/omniview/REFRESH_REMEDIATION_POLICY.md`

La política establece:

- **Dev:** APScheduler no garantiza refresh porque el backend se inicia/detiene frecuentemente y `CT_SCHEDULER_ENABLED=False` por defecto. La remediación es manual vía endpoint o UI.
- **Prod:** Se requiere scheduler externo (cron, systemd timer, GitHub Actions) — el backend no debe ser la única garantía del refresh.
- **Prohibiciones:** No backfill automático en startup, no ocultar alertas BLOCKED, no maquillar freshness, no fallback runtime en UI, no escanear RAW desde frontend.
- **Flujo de remediación** documentado con diagrama de secuencia.

---

## 2. Endpoint Creado

**Ruta:** `POST /ops/omniview/refresh`  
**Archivo:** `backend/app/routers/ops.py:660`

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `force` | query bool | Default `True`. Ignora cooldown entre corridas. |
| `status` | string | `ok`, `failed`, o `error` |
| `started_at` | ISO datetime | Inicio de la ejecución |
| `finished_at` | ISO datetime | Fin de la ejecución |
| `duration_seconds` | float | Duración total |
| `rows_affected` | int \| null | Filas en day_fact post-refresh |
| `errors` | list | Errores por mes o generales |
| `log` | list | Resumen por mes procesado |
| `freshness_after` | object | Estado post-refresh de freshness |
| `upstream_preflight` | object | Estado upstream antes del refresh |
| `before_max_trip_date` | string | MAX(trip_date) antes del refresh |

**Ejemplo de respuesta (éxito):**
```json
{
  "status": "ok",
  "started_at": "2026-05-31T10:00:00Z",
  "finished_at": "2026-05-31T10:00:12Z",
  "duration_seconds": 12.34,
  "rows_affected": 15234,
  "errors": [],
  "log": ["2026-04: day_rows=12340 week_rows=850 month_rows=1 5.2s", "2026-05: day_rows=15234 week_rows=920 month_rows=1 7.1s"],
  "freshness_after": {...},
  "upstream_preflight": {...},
  "before_max_trip_date": "2026-05-29"
}
```

---

## 3. UI Remediation

**Archivo:** `frontend/src/components/omniview/freshness/OmniviewFreshnessGovernanceCard.jsx`

Cambios:
- Nuevo botón rojo **"Refrescar Omniview"** visible solo cuando `status === "blocked"`.
- Flujo: confirmación → POST al endpoint → loading spinner en botón → re-fetch de freshness → resultado visible.
- Sin congelar UI: el refresh corre en segundo plano.
- Mensaje de resultado (éxito con duración, o error) mostrado debajo del botón.
- Endpoint configurado con timeout de 300s (5 min) en `api.js`.

**Archivo:** `frontend/src/services/api.js:201-204`
- Nueva función `postOmniviewRefresh(force)`.

---

## 4. Startup Behavior

**Archivo:** `backend/app/startup_checks.py` (nueva función `_run_omniview_freshness_startup_check`)

Al iniciar el backend:
1. Se ejecuta `get_omniview_freshness_governance()` — solo consultas `MAX(date)`, sin escaneos pesados.
2. Se loguea: RAW max date, daily max date, status, message.
3. Si status == "blocked", se loguea WARNING con remediation.
4. Se inyecta en el report `omniview_freshness_startup` y como check `non_blocking` (nunca bloquea el startup).
5. **NO se ejecuta backfill automático.**

El report se expone en `GET /health` bajo `startup.checks[]`.

---

## 5. QA

**Archivo:** `backend/tests/test_refresh_remediation.py`

Tests incluidos:

| Test | Descripción |
|------|-------------|
| `test_worst_status_ordering` | Verifica que `_worst_status` prioriza BLOCKED > WARNING > OK y ERROR sobre todo |
| `test_status_from_lag` | Verifica thresholds: lag≤1 OK, 2-3 WARNING, ≥4 BLOCKED, None ERROR |
| `test_freshness_governance_returns_expected_keys` | Estructura de respuesta completa |
| `test_freshness_governance_facts_structure` | Todas las capas (daily/weekly/monthly/projection) presentes |
| `test_freshness_governance_blocked_has_remediation_message` | BLOCKED incluye remediation |
| `test_freshness_governance_ok_has_no_remediation` | OK no muestra remediation |
| `test_refresh_job_return_structure` | Estructura del job de refresh |
| `test_refresh_job_respects_cooldown_by_default` | Cooldown entre corridas sin force |
| `test_refresh_job_force_bypasses_cooldown` | `force=True` ignora cooldown |
| `test_startup_omniview_freshness_check_injects_into_report` | Startup check agrega datos al report |
| `test_startup_check_does_not_alter_overall_when_blocked` | Check es non_blocking, no degrada startup |
| `test_ct_scheduler_disabled_by_default` | `CT_SCHEDULER_ENABLED=False` por defecto |
| `test_omniview_refresh_has_timeout_configured` | Timeout > 0 y >= 60s |
| `test_omniview_refresh_has_cooldown_configured` | Cooldown configurado entre 1 y 1440 min |

---

## 6. Riesgos Pendientes

| Riesgo | Severidad | Mitigación |
|--------|-----------|------------|
| Refresh sync puede tardar >30s en prod | Media | Migrar a async/job con polling de estado si el volumen crece |
| Sin scheduler externo en prod, el refresh no ocurre | Alta | Implementar cron/systemd timer (documentado en política sección 9) |
| Botón de refresh visible para cualquier usuario (sin auth role) | Media | Endpoint actual no tiene auth middleware; agregar cuando se implemente RBAC |
| Concurrent refresh desde múltiples tabs de UI | Baja | Advisory lock en el job (`refresh_guard`) protege contra race condition |
| El startup check asume que la DB ya está inicializada | Baja | Se ejecuta después de `init_db_pool()` en `run_startup_checks()` |

---

## 7. Archivos Modificados / Creados

| Archivo | Acción |
|---------|--------|
| `docs/omniview/REFRESH_REMEDIATION_POLICY.md` | Creado |
| `docs/omniview/REFRESH_REMEDIATION_CONTROL_REPORT.md` | Creado |
| `backend/app/routers/ops.py` | Modificado (nuevo endpoint POST /omniview/refresh) |
| `backend/app/startup_checks.py` | Modificado (nueva función `_run_omniview_freshness_startup_check`) |
| `frontend/src/components/omniview/freshness/OmniviewFreshnessGovernanceCard.jsx` | Modificado (botón de refresh + lógica) |
| `frontend/src/services/api.js` | Modificado (nueva función `postOmniviewRefresh`) |
| `backend/tests/test_refresh_remediation.py` | Creado |
