# H6 — Validación E2E (evidencia)

**Fecha:** 2026-04-08  
**Entorno de prueba:** desarrollo local Windows, Python 3.11, repo `YEGO CONTROL TOWER`.

## 1. Alembic / DB

| Comando | Resultado |
|---------|-----------|
| `cd backend && python -m alembic heads` | `129_ensure_v_real_data_coverage (head)` |

**Nota:** No se ejecutó `alembic upgrade` contra una BD de integración en esta sesión (depende de credenciales y servidor). En despliegue: `alembic upgrade head` y verificar `SELECT to_regclass('ops.v_real_data_coverage');` → no NULL.

## 2. Backend — imports y sintaxis

| Comando | Resultado |
|---------|-----------|
| `python -m py_compile app/services/real_drill_service.py app/services/real_lob_drill_pro_service.py app/startup_checks.py app/routers/health.py` | Exit code 0 |

## 3. Tests automatizados

| Comando | Resultado |
|---------|-----------|
| `pytest tests/test_bi_guardrail.py tests/test_period_state_engine.py -q` | **8 passed** |
| `pytest tests/test_real_coherence.py -q` | **4 passed, 1 skipped** |

## 4. API en vivo (limitación)

| Comando | Resultado |
|---------|-----------|
| `Invoke-WebRequest http://127.0.0.1:8000/health` | **200** con cuerpo `{"status":"ok","service":"YEGO Control Tower API"}` |

**Limitación:** El proceso uvicorn en ejecución era una **versión anterior** del código (respuesta legacy sin `startup`). Tras desplegar este hardening, repetir `/health` y validar presencia de `status` ∈ {ok, degraded, blocked}, `db_connection`, `startup.checks`.

## 5. Endpoints manuales recomendados (post-reinicio)

```http
GET /health
GET /ops/real-lob/drill?period=month&desglose=LOB&segmento=all
GET /ops/business-slice/coverage-summary?year=2026
GET /ops/business-slice/filters
GET /ops/data-trust?view=resumen
```

## Veredicto de esta fase (herramientas)

**CONDITIONAL GO** — Código y tests locales pasan; migración **129** definida; validación HTTP completa del nuevo `/health` requiere **reiniciar** el servidor con el código actualizado; aplicación de migraciones requiere **BD real**.
