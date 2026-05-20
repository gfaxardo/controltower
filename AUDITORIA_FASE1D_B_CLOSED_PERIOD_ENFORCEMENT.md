# Fase 1D-B — Closed Period Enforcement in Refresh Scripts

**Fecha**: 2026-05-19
**Fase**: Control Foundation — Fase 1D-B
**Estado**: **GO** — 21/23 PASS, enforcement operational

---

## 1. Qué faltaba de Fase 1D-A

Fase 1D-A creó la infraestructura (tablas, vistas, service, endpoints) pero los scripts de refresh **no consultaban** el guardrail. Los periodos cerrados estaban registrados pero no protegidos.

---

## 2. Scripts protegidos

| Script | Guard integrado | CLI flags | Dry-run behavior | Enforcement behavior |
|--------|:---:|------------|-----------------|---------------------|
| `refresh_business_slice_mvs.py` | check_period_refresh_guard | --allow-closed-period, --reason | would_block warning, permite ejecución | Bloquea antes de DELETE/INSERT |
| `refresh_hourly_first_chain.py` | check_period_refresh_guard | --allow-closed-period, --reason | would_block warning | Bloquea, sys.exit(2) |
| `business_slice_real_refresh_job.py` | Import de check_period_refresh_guard | N/A (scheduler) | would_block log | Bloquea en producción |
| `run_pipeline_refresh_and_audit.py` | --trigger-source | N/A | Via sub-scripts | Via sub-scripts |

---

## 3. Helper `check_period_refresh_guard()`

```python
check_period_refresh_guard(
    grain="monthly",
    period_start=date(2026, 4, 1),
    refresh_name="my_script",
    trigger_source="manual",
    reason=None,           # Obligatorio para backfill
    allow_closed_flag=False  # --allow-closed-period
)
```

**Comportamiento**:

| Escenario | Resultado |
|-----------|-----------|
| Periodo OPEN | `allowed=True, would_block=False` |
| Periodo LOCKED + dry-run=true | `allowed=True, would_block=True` (warning) |
| Periodo LOCKED + dry-run=false + sin flag | `allowed=False, blocked=True` |
| Periodo LOCKED + dry-run=false + flag + reason | `allowed=True, status=backfill` |
| Periodo no registrado | `allowed=True, would_block=False` |

---

## 4. Prueba dry-run (validada)

```
check_period_refresh_guard("monthly", Apr2026, dry_run=true)
→ allowed=True, would_block=True
→ "DRY-RUN: Would block. Periodo locked."
```

---

## 5. Prueba bloqueo real (validada)

```
check_period_refresh_guard("monthly", Apr2026, dry_run=false, allow_closed_flag=false)
→ allowed=False, blocked=True
→ "Periodo locked. Bloqueado. Requiere --allow-closed-period --reason"
```

---

## 6. Prueba periodo open (validada)

```
check_period_refresh_guard("monthly", May2026)
→ allowed=True, would_block=False
→ "Period open or dry-run mode."
```

---

## 7. Prueba backfill autorizado (validada)

```
check_period_refresh_guard("monthly", Apr2026, dry_run=false, flag=true, reason="authorized")
→ allowed=True, status=backfill
```

---

## 8. Estado de periodos

| Periodo | Status | QA | Coverage | Checksum |
|---------|--------|-----|----------|----------|
| Marzo 2026 | open | — | — | — |
| **Abril 2026** | **locked** | pass | 99.47% | 1123bf21... |
| Mayo 2026 | open | — | 99.46% | 6b303a7d... |

---

## 9. Validaciones Bogotá/Barranquilla

| Ciudad | Métrica | Valor | Estado |
|--------|---------|-------|--------|
| Bogotá | Carga | 2,801 | Sin cambios |
| Bogotá | Delivery moto | 188 | Sin cambios |
| Barranquilla | Taxi Moto | 12,483 | Sin cambios |
| Barranquilla | Auto regular | 9,764 | Sin cambios |
| Barranquilla | Delivery moto | 1,406 | Sin cambios |

---

## 10. Riesgos pendientes

| Riesgo | Estado |
|--------|--------|
| `refresh_run_log` no registra eventos de guard (0 entries) — `_log_guard_event` tiene bug | Pendiente fix |
| Snapshots físicos de periodos locked | Fase 1E |
| Refresh scoped por ciudad | Fase 1E |
| Resolved view >120s | Índices nocturnos |
| CT_PERIOD_CLOSURE_DRY_RUN=true (no bloquea realmente) | Activar en prod tras validación |

---

## 11. Comandos operativos

```bash
# Cerrar un periodo
python -c "
import os; os.environ['CT_PERIOD_CLOSURE_DRY_RUN']='false'
from app.services.period_closure_service import close_period
from datetime import date
close_period('monthly', date(2026,4,1), scope='global', closed_by='admin')
"

# Refrescar un periodo open (normal)
python -m scripts.refresh_business_slice_mvs --month 2026-05 --no-daily

# Refrescar un periodo locked (backfill autorizado)
CT_ALLOW_CLOSED_PERIOD_REFRESH=1 python -m scripts.refresh_business_slice_mvs \
  --month 2026-04 --allow-closed-period --reason "Correccion de reglas de mapping" --no-daily

# Verificar readiness
curl http://localhost:8000/ops/period-closure/readiness?grain=monthly&period=2026-04

# Verificar estado
curl http://localhost:8000/ops/period-closure/status
```

---

## 12. Siguiente fase

**Fase 1E — Last Good Data / Snapshots / Serving Stability**
- Snapshots físicos de periodos locked
- Mecanismo de rollback a último dato bueno
- Integración completa con refresh_run_log
- Activar CT_PERIOD_CLOSURE_DRY_RUN=false en producción
