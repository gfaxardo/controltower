# LG-CTRL-AUDIT-1A — Autonomous Day Rollover Audit

**Date**: 2026-06-10  
**Status**: AUDIT COMPLETE  
**Decision**: **B) MANUAL INTERVENTION REQUIRED**

---

## TAREA 1 — Assignment Queue (5 days)

```
date       | READY  HELD  EXPORTED  TOTAL
2026-06-09 |   300   190        10    500
2026-06-08 |   310   190         0    500
2026-06-05 |   295   190        15    500
```

Solo 3 fechas. 500 registros por dia. Sin datos para 06-06, 06-07, 06-10.

---

## TAREA 2 — Control Loop State

```
date       | READY  ASSIGNED  IN_PROGRESS  CONTACTED  DONE  CLOSED  TOTAL
2026-06-10 |   549         0            0          0    15       0    564
```

Solo 1 fecha (2026-06-10). 549 READY, 15 DONE (exportados por test manual LG-CTRL-1.1A). Sin bridge automático queue→control_loop para otras fechas.

---

## TAREA 3 — Refresh Run Log (all runs)

```
id         | op_date     | status   | started              | finished
461ed50c   | 2026-06-09  | SUCCESS  | 2026-06-09 15:50:27  | 2026-06-09 16:05:59
c30f9c29   | 2026-06-08  | SUCCESS  | 2026-06-09 15:50:22  | 2026-06-09 16:05:59
976d7522   | 2026-06-05  | SUCCESS  | 2026-06-08 08:57:40  | 2026-06-08 09:02:16
2c69e75c   | 2026-06-05  | SUCCESS  | 2026-06-07 19:46:35  | 2026-06-07 19:49:19
cfbd285d   | 2026-06-05  | SUCCESS  | 2026-06-07 09:23:04  | 2026-06-07 09:25:30
eb5d486c   | 2026-06-05  | FAILED   | 2026-06-07 09:06:29  | 2026-06-07 09:06:32
0f35d429   | 2026-06-03  | FAILED   | 2026-06-06 22:12:39  | 2026-06-06 22:12:43
```

Solo 7 runs totales. Ninguno con `triggered_by='autonomous_tick'`.

### Trigger sources

```
triggered_by       | runs | dates
system             |    5 | 2026-06-03..2026-06-05
LG-CF-HOTFIX-1C   |    2 | 2026-06-08..2026-06-09
```

---

## TAREA 4 — Run que produjo 2026-06-09

```
run_id:      461ed50c-0b9d-4989-8e07-79cf4ea28e9f
date:        2026-06-09
status:      SUCCESS
started:     2026-06-09 15:50:27
finished:    2026-06-09 16:05:59
trigger:     LG-CF-HOTFIX-1C (MANUAL)
summary:     {'steps': []}
```

El pipeline fue ejecutado manualmente como parte de LG-CF-HOTFIX-1C a las 15:50. Produjo snapshot, eligibility, priorización, y queue para 2026-06-08 y 2026-06-09.

---

## TAREA 5 — Comparación 06-08 vs 06-09

```
Metric          | 2026-06-08 | 2026-06-09
snapshot        |     18,545 |     18,545
eligible        |     28,128 |     28,128
prioritized     |      5,505 |      5,505
queue           |        500 |        500
lc_exports      |          0 |          2
control_loop    |          0 |          0
```

Ambas fechas comparten los mismos números base — producidos por el mismo run manual. No hay rollover autónomo.

---

## Data Source Freshness

```
component          | status   | max_date
driver_state       | WARNING  | 2026-06-09
eligibility        | WARNING  | 2026-06-09
prioritized        | WARNING  | 2026-06-09
queue              | WARNING  | 2026-06-09
raw_orders         | FRESH    | 2026-06-09
daily_registry     | WARNING  | 2026-06-09
```

Todos los componentes muestran max_date = 2026-06-09. Latencia ~39 horas (WARNING). raw_orders está FRESH (datos hasta 2026-06-09 15:47). Sin datos para 2026-06-10.

---

## RESPUESTA FINAL

### Preguntas

| Pregunta | Respuesta | Evidencia |
|---|---|---|
| 1. Queue generada automáticamente? | **NO** | `triggered_by='LG-CF-HOTFIX-1C'` (manual), no `autonomous_tick` runs |
| 2. Queue generada manualmente? | **SI** | Run 461ed50c ejecutado manualmente a las 15:50 del 09-06 |
| 3. Control Loop recibió registros nuevos? | **NO** via scheduler | Solo exportaciones manuales de test (2 campaigns) |
| 4. Bridge automático queue→control_loop? | **NO** | Sin evidencia en refresh_run_log |
| 5. Evidencia de intervención humana? | **SI** | Todos los runs >06-05 son `LG-CF-HOTFIX-1C` (manual) |

### Clasificación

**B) MANUAL INTERVENTION REQUIRED**

El scheduler autónomo está configurado pero:
- Zero ejecuciones registradas con `triggered_by='autonomous_tick'`
- El trigger `system` dejó de producir runs después de 2026-06-05
- El pipeline diario requiere intervención manual (`LG-CF-HOTFIX-1C`, `POST /refresh/run`)
- Sin nuevos datos raw (el último `ended_at` en raw_orders es 2026-06-09), el scheduler no tendría datos frescos para procesar — pero el scheduler ni siquiera intentó ejecutarse

### Causa probable

El scheduler arranca (`Lima Growth autonomous scheduler programado: cada 5 min.` en logs de startup) pero el `autonomous_tick` no produce runs porque:
1. El scheduler se registra en el APScheduler pero el trigger de ejecución depende de la existencia de datos fresh (>24h)
2. O el `autonomous_tick` falla silenciosamente (el overlap-protection podría estar bloqueando)
3. O `CT_SCHEDULER_ENABLED` no está configurado para ejecución automática
