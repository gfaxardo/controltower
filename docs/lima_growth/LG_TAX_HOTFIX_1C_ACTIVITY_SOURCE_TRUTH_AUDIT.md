# LG-TAX-HOTFIX-1C — ACTIVITY SOURCE TRUTH AUDIT

**Fase:** Lima Growth Foundation — Hotfix 1C  
**Motor:** Control Foundation (Lima Growth)  
**Estatus:** AUDIT / ROOT CAUSE IDENTIFIED  
**Fecha:** 2026-06-11  
**Audit Scope:** `completed_orders_week` in `driver_state_snapshot`

---

## TASK 0 — GOVERNANCE

Control Foundation / Lima Growth. Shadow taxonomy implementation (TAX-1.0B) revealed the anomaly. This audit is read-only — zero production changes.

---

## TASK 1 — VALIDAR DEFINICIÓN DE `completed_orders_week`

### Distribución en `driver_state_snapshot` (2026-06-10)

| Bucket | Drivers | % |
|--------|---------|---|
| 1 | 4,160 | 22.4% |
| 2-5 | 8,924 | 48.1% |
| 6-10 | 2,066 | 11.1% |
| 11-25 | 1,873 | 10.1% |
| 26-50 | 888 | 4.8% |
| 51-80 | 396 | 2.1% |
| 81-100 | 103 | 0.6% |
| 101-150 | 116 | 0.6% |
| 150+ | 19 | 0.1% |
| **Total > 0** | **18,545** | **100%** |
| Total = 0 | 0 | 0% |

### Validación contra benchmark operacional

| Métrica | Benchmark Esperado | driver_state |
|---------|-------------------|--------------|
| Daily active drivers | ~1,200 | N/A (completed_orders_day no auditado) |
| Weekly active drivers | ~4,000-5,000 | 18,545 → **ANOMALÍA** |
| Monthly active drivers | ~7,000-8,000 | N/A |

**Conclusión parcial**: `completed_orders_week > 0` para 18,545 drivers contradice el benchmark operativo. O bien la columna no mide lo que su nombre sugiere, o bien hay un error en el cálculo.

---

## TASK 2 — COMPARAR CONTRA RAW YANGO

### growth.yango_lima_orders_raw

| Ventana | Órdenes | Distinct Drivers |
|---------|---------|-----------------|
| 2026-06-10 (diario) | 0 | 0 |
| 2026-06-04 a 2026-06-10 (7d) | 12,085 | 1,591 |
| 2026-05-12 a 2026-06-10 (30d) | 12,322 | 1,626 |

**Nota**: Esta tabla tiene datos escasos. Solo 12,322 órdenes en 30 días, 1,626 drivers. La ingestión no está corriendo a plena capacidad para esta fecha.

### growth.yango_lima_driver_history_weekly

| Week | Drivers |
|------|---------|
| 2026-06-01 (current) | 2,257 |
| 2026-05-25 | 2,624 |
| 2026-05-18 | 2,729 |
| 2026-05-11 | 2,836 |
| 2026-05-04 | 2,997 |
| 2026-04-27 | 3,093 |
| 2026-04-20 | 3,198 |
| 2026-04-13 | 2,842 |
| ... | ... |
| Total (67 weeks) | **18,545** unique drivers |

### Comparación

| Fuente | Ventana | Drivers Activos |
|--------|---------|----------------|
| Operational benchmark | Weekly | ~4,000-5,000 |
| driver_state_snapshot | `completed_orders_week` | **18,545** |
| history_weekly | Current week (2026-06-01) | **2,257** |
| history_weekly | Last 4 weeks | 2,257-2,997/week |
| orders_raw | 30d | 1,626 |

---

## TASK 3 — MATRIZ DE MISMATCH

### driver_state vs history_weekly (current week = 2026-06-01)

| driver_state.completed_orders_week | history_weekly current week | Drivers |
|-------------------------------------|----------------------------|---------|
| > 0 | > 0 | **2,257** |
| > 0 | No data in current week (= 0 or missing) | **15,461** |
| = 0 | > 0 | 0 |
| = 0 | = 0 / missing | 0 |

**Mismatch count**: 15,461 drivers (83.4% del universo)

**Explicación**: Estos 15,461 drivers tienen `completed_orders_week > 0` en el snapshot porque el código usa su **última semana disponible** en `history_weekly`, no la semana actual. Su última semana con datos puede ser de hace meses (el rango completo del historial es 2025-02-24 a 2026-06-01, 67 semanas).

---

## TASK 4 — AUDITAR CÁLCULO DE DRIVER_STATE

### Código relevante

Archivo: `app/services/yego_lima_driver_state_service.py`

#### Línea 80-94: Construcción de `history_universe`

```python
cur.execute("""
    SELECT hw.driver_profile_id,
           hw.completed_orders_week,
           hw.week_start_date,
           hw.historical_band
    FROM growth.yango_lima_driver_history_weekly hw
    INNER JOIN (
        SELECT driver_profile_id, MAX(week_start_date) AS latest_week
        FROM growth.yango_lima_driver_history_weekly
        WHERE week_start_date <= %(monday)s
        GROUP BY driver_profile_id
    ) latest ON hw.driver_profile_id = latest.driver_profile_id
             AND hw.week_start_date = latest.latest_week
""")
```

#### Línea 173: Asignación a completed_orders_week

```python
orders_week = int(h.get("completed_orders_week", 0) or 0)
```

### Respuestas

| Pregunta | Respuesta |
|----------|-----------|
| ¿De qué tabla viene? | `growth.yango_lima_driver_history_weekly` |
| ¿Qué ventana usa? | **LATEST available week per driver** (MAX week_start_date <= snapshot Monday). NO es la semana actual. Puede ser cualquier semana histórica desde 2025-02-24. |
| ¿Usa ISO week? | Sí — `week_start_date` es lunes de la semana ISO. |
| ¿Usa acumulado histórico? | **No como acumulado, pero sí como "último dato disponible."** Si un driver no tiene datos en la semana actual, se usa su última semana con datos, que puede ser de hace meses. |
| ¿Filtra por completed? | `completed_orders_week` ya es una columna pre-calculada en `history_weekly`. No sabemos cómo se calculó originariamente. |
| ¿Filtra por Lima? | No explícitamente en este query. Depende de si `history_weekly` ya está filtrado. |
| ¿Filtra por fecha correcta? | **NO.** Usa `MAX(week_start_date) <= monday`, que devuelve la última semana disponible, no la semana actual. |

### El Bug

```python
# Línea 80-94: Obtiene la ÚLTIMA SEMANA de cada driver
MAX(week_start_date) <= %(monday)s  -- "<= monday" incluye semanas pasadas

# Línea 173: Usa esa semana como si fuera "esta semana"
orders_week = int(h.get("completed_orders_week", 0) or 0)
```

**Problema**: Si un driver tuvo órdenes en la semana del 2025-06-01 (52 semanas atrás), y no ha vuelto a aparecer, su `completed_orders_week` para el snapshot del 2026-06-10 seguirá siendo el valor de junio 2025. El código no distingue entre "semana actual" y "última semana disponible."

---

## TASK 5 — FUENTE CANÓNICA PARA ACTIVITY

### Propuesta

| Métrica | Fuente | Query | Ventana |
|---------|--------|-------|---------|
| `daily_active` | `growth.yango_lima_driver_360_daily` | `completed_orders > 0 AND date = D` | 1 día |
| `weekly_active` | `growth.yango_lima_driver_360_daily` | `completed_orders > 0 AND date BETWEEN D-6 AND D` | 7 días |
| `monthly_active` | `growth.yango_lima_driver_360_daily` | `completed_orders > 0 AND date BETWEEN D-29 AND D` | 30 días |

O alternativamente:

| Métrica | Fuente | Query |
|---------|--------|-------|
| `weekly_active_current` | `growth.yango_lima_driver_history_weekly` | `completed_orders_week > 0 AND week_start_date = CURRENT_ISO_MONDAY` |
| `churn_15d` | `growth.yango_lima_driver_history_weekly` | `MAX(week_start_date) < D-14 AND MAX(week_start_date) >= D-90` |
| `archived_90d` | `growth.yango_lima_driver_history_weekly` | `MAX(week_start_date) < D-90` |

### Regla de Oro

**NUNCA usar `completed_orders_week` de `driver_state_snapshot` como señal de "actividad actual."** La columna contiene datos de la última semana disponible para cada driver, que puede tener meses de antigüedad.

---

## TASK 6 — IMPACTO EN TAXONOMY

### Si usáramos `history_weekly` con filtro de recencia

| Estado | Drivers | Fuente |
|--------|---------|--------|
| ACTIVE (current week orders) | 2,257 | `history_weekly WHERE week_start_date = '2026-06-01' AND completed_orders_week > 0` |
| ACTIVE (last 14d) | 2,257-2,624 | `history_weekly WHERE week_start_date >= '2026-05-25'` |
| CHURN 15d (last trip 15-90d) | ~16,000+ | Drivers in history_weekly with last week between 2026-03-12 and 2026-05-25 |
| ARCHIVED 90d (last trip > 90d) | ~0 | Drivers never in history_weekly or last week before 2026-03-12 |

### Comparación contra 18,545

| Métrica | Taxonomy Shadow (con bug) | Real (con corrección) |
|---------|--------------------------|----------------------|
| ACTIVE | 18,545 (100%) | ~2,257-2,624 (12-14%) |
| CHURN | 0 | ~16,000 (86%) |
| ARCHIVED | 0 | ~0 |

**La taxonomía actual está clasificando a 15,461 drivers como ACTIVE cuando en realidad no han tenido actividad en la semana actual.**

---

## TASK 7 — VEREDICTO

### Clasificación: **E) PARK/FILTER MISMATCH + B) FIELD IS STALE**

### Explicación detallada

| Factor | Diagnóstico |
|--------|------------|
| **A) taxonomy misunderstood** | **NO.** La taxonomía usa correctamente `completed_orders_week > 0` como señal de actividad. El problema está en el dato de origen. |
| **B) completed_orders_week broken/stale** | **SÍ — PARCIAL.** La columna no está "rota" en el sentido de datos corruptos. Está **semánticamente mal:** contiene "última semana con datos" en vez de "semana actual." Para 15,461 drivers, esa última semana es de hace >14 días. |
| **C) raw orders query wrong** | **NO APLICA.** El raw no es la fuente de `completed_orders_week`. |
| **D) date/window mismatch** | **SÍ.** El query usa `MAX(week_start_date) <= monday` que devuelve la última semana *disponible*, no la semana *actual*. |
| **E) park/filter mismatch** | **NO DIRECTAMENTE.** Pero la discrepancia entre 1,626 (raw 30d) y 18,545 (history all-time) sugiere que `history_weekly` contiene datos históricos acumulados de todos los drivers que alguna vez existieron, no solo los activos. |
| **F) mixed** | **SÍ.** La causa raíz es una combinación de B + D: el query de `history_universe` no filtra por recencia, y el campo `completed_orders_week` se interpreta erróneamente como "órdenes de esta semana." |

### Veredicto Final

**`completed_orders_week` en `driver_state_snapshot` NO es un indicador de actividad actual.** Es un indicador de "última actividad conocida" que puede tener meses de antigüedad. El taxonomy shadow heredó este problema, resultando en 18,545 drivers clasificados como ACTIVE cuando en realidad solo ~2,257 lo están.

---

## TASK 8 — DOCUMENTACIÓN Y GO/NO-GO

### GO/NO-GO para uso de `driver_state_snapshot.completed_orders_week` como señal de actividad

**Veredicto: NO-GO. NO usar para Activity Status en taxonomy.**

### Evidencia

| Criterio | Resultado |
|----------|-----------|
| Campo mide lo que dice medir | **FAIL** — No mide "órdenes de esta semana" sino "órdenes de la última semana disponible" |
| Recencia de los datos | **FAIL** — 15,461/18,545 drivers (83.4%) tienen datos de >14 días de antigüedad |
| Concordancia con benchmark | **FAIL** — 18,545 vs esperado ~4,000-5,000 weekly active |
| Concordancia con raw orders | **FAIL** — 18,545 vs 1,626 drivers con órdenes en últimos 30 días |

### Recomendación

**Para Operational Status (ACTIVE/CHURN/ARCHIVED) en la taxonomía:**

1. **Fuente primaria**: `growth.yango_lima_driver_history_weekly` filtrando por `week_start_date = CURRENT_ISO_MONDAY` para determinar actividad actual.

2. **ACTIVE**: `completed_orders_week > 0 AND week_start_date = CURRENT_ISO_MONDAY`

3. **CHURN 15d**: `MAX(week_start_date) BETWEEN CURRENT_DATE - 90 AND CURRENT_DATE - 15`

4. **ARCHIVED 90d**: `MAX(week_start_date) < CURRENT_DATE - 90`

5. **Solución a largo plazo**: Usar `growth.yango_lima_driver_360_daily` con rolling windows (7d, 30d) en vez de history_weekly snapshots. Esto da recencia real día a día.

### Acción Inmediata (TAX-HOTFIX-1C-FIX)

NO modificar `driver_state_snapshot` (es usado por otros servicios). En su lugar, modificar `yego_lima_taxonomy_service.py` para que el Operational Status use queries directas contra `driver_history_weekly` con filtro de recencia, no contra `driver_state_snapshot.completed_orders_week`.

---

## APPENDIX A — Distribución de history_weekly por semana

| Semana | Drivers | Tendencia |
|--------|---------|-----------|
| 2026-06-01 | 2,257 | ← Current |
| 2026-05-25 | 2,624 | |
| 2026-05-18 | 2,729 | |
| 2026-05-11 | 2,836 | |
| 2026-05-04 | 2,997 | |
| 2026-04-27 | 3,093 | |
| 2026-04-20 | 3,198 | |
| 2026-04-13 | 2,842 | |
| ... | ... | 67 weeks total back to 2025-02-24 |

**Nota**: La caída en las últimas semanas (de ~3,200 a 2,257) puede indicar problemas de ingestión o estacionalidad real. Investigar por separado.

---

## APPENDIX B — Evidencia del Código

Archivo: `app/services/yego_lima_driver_state_service.py:80-94,173`

```python
# L80-94: Obtiene latest_week per driver (puede ser de hace meses)
SELECT driver_profile_id, MAX(week_start_date) AS latest_week
FROM growth.yango_lima_driver_history_weekly
WHERE week_start_date <= %(monday)s  -- "<= today" incluye toda la historia
GROUP BY driver_profile_id

# L173: Usa ese valor como "completed_orders_week"
orders_week = int(h.get("completed_orders_week", 0) or 0)
```

---

## APPENDIX C — Scripts

| Script | Propósito |
|--------|-----------|
| `scripts/tax_hotfix_1c_audit.py` | Distribución + búsqueda de tablas raw |
| `scripts/tax_hotfix_1c_audit2.py` | Raw orders vs driver_state vs history_weekly |
| `scripts/tax_hotfix_1c_rootcause.py` | Verificación del root cause (stale drivers) |

---

**LG-TAX-HOTFIX-1C — FIN DE LA AUDITORÍA**

*Root cause: `completed_orders_week` uses LATEST available week, not CURRENT week.*  
*15,461/18,545 drivers (83.4%) have stale data (>14 days old).*  
*Taxonomy ACTIVE = 18,545 is a data artifact, not operational reality.*  
*Real weekly active drivers: ~2,257.*  
*Veredicto: NO-GO for current activity signal. Fix required before taxonomy Activity Status is trustworthy.*
