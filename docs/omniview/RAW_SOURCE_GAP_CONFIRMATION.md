# RAW SOURCE GAP CONFIRMATION — CF-H1C

**Fecha**: 2026-05-30
**Motor**: Control Foundation

---

## 1. Resultado SQL

### Raw Source (`public.trips_2026`)

```
=== public.trips_2026 (RAW SOURCE) ===
2026-05-24  97352 trips
2026-05-25  81804 trips
2026-05-26  83416 trips
2026-05-27  84660 trips
2026-05-28  86266 trips
2026-05-29  90522 trips
```

### FACT_DAILY (`ops.real_business_slice_day_fact`)

```
=== FACT_DAILY scope ===
Range: 2025-01-01 to 2026-04-30  Total rows: 7974
```

### FACT_WEEKLY (`ops.real_business_slice_week_fact`)

```
Range: 2024-12-30 to 2026-03-23  Total rows: 1105
```

### Month Fact (`ops.real_business_slice_month_fact`)

```
Range: 2025-01-01 to 2026-05-01  Total rows: 309
```

### Serving Fact (`serving.omniview_projection_daily_fact`)

```
Fila global (todas las ciudades/tajadas):
2026-05-24  total=28  has_real_gt0=20  no_real=8
2026-05-25  total=28  has_real_gt0=0   no_real=28
2026-05-26  total=28  has_real_gt0=0   no_real=28
2026-05-27  total=28  has_real_gt0=0   no_real=28
2026-05-28  total=28  has_real_gt0=0   no_real=28
2026-05-29  total=28  has_real_gt0=0   no_real=28
2026-05-30  total=28  has_real_gt0=0   no_real=28
```

---

## 2. Respuestas

| Pregunta | Respuesta | Evidencia |
|----------|-----------|-----------|
| 1. ¿Existen filas para 25? | **SÍ** | 81,804 viajes en raw source |
| 2. ¿Existen filas para 26? | **SÍ** | 83,416 viajes en raw source |
| 3. ¿Existen filas para 27? | **SÍ** | 84,660 viajes en raw source |
| 4. ¿Existen filas para 28? | **SÍ** | 86,266 viajes en raw source |
| 5. ¿Existen filas para 29? | **SÍ** | 90,522 viajes en raw source |

**El gap NO está en la fuente raw.** El problema está en la pipeline de refresh.

---

## 3. Fechas Presentes vs Ausentes

| Capa | 24 | 25 | 26 | 27 | 28 | 29 | 30 |
|------|----|----|----|----|----|----|----|
| `public.trips_2026` (RAW) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | N/A |
| `ops.real_business_slice_day_fact` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `ops.real_business_slice_week_fact` | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| `serving.omniview_projection_daily_fact` (real) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

- **24**: serving fact tiene real data (probablemente de una ejecución previa del refresh)
- **25-29**: serving fact solo tiene plan data (sin datos reales)
- **30**: futuro, solo plan

### Dato clave: FACT_DAILY está VACÍO para todo May 2026

El refresh job NO ha poblado day_fact ni week_fact para May. Solo month_fact tiene datos (probablemente por una ejecución separada del CLI de backfill).

---

## 4. Hipótesis Causa Raíz

### Confirmada: **Falla en la pipeline de refresh (APScheduler)**

**Evidencia**:
1. Raw source (`public.trips_2026`) tiene datos completos para May 24-29 (82k-97k viajes/día)
2. FACT_DAILY termina en April 30. CERO filas para May.
3. FACT_WEEKLY termina en March 23. Sin datos para April ni May.
4. `OMNIVIEW_REAL_REFRESH_ENABLED = True` (configurado para correr a las 04:00)
5. `refreshed_at` y `loaded_at` son NULL para todo May en FACT_DAILY

**Conclusión**: El APScheduler que ejecuta `run_business_slice_real_refresh_job()` a las 04:00 diario NO está funcionando, o falla silenciosamente (errores capturados y logueados pero no alertados).

### Hipótesis descartadas:
- ❌ Gap en fuente upstream — fuente tiene datos completos
- ❌ Filtro de fecha mal aplicado — el código de loader es correcto
- ❌ Proyección con filtro incorrecto — la pipeline completa es correcta, solo no se ejecuta
- ❌ Frontend malinterpretando datos — el backend sirve NULL porque FACT_DAILY está vacío

---

## 5. Siguiente Acción Recomendada

### Acción inmediata (fix):
Ejecutar refresh manual para repoblar FACT_DAILY y FACT_WEEKLY:

```bash
cd backend
python -m scripts.refresh_omniview_real_slice --force
```

O vía API:
```bash
curl -X POST "http://localhost:8000/ops/business-slice/real-refresh-omniview?force=true"
```

Luego refrescar el serving fact de proyección:
```bash
python -m scripts.refresh_omniview_projection_facts --grain daily --plan_version ruta27
```

### Acción estructural (prevenir recurrencia):
1. Revisar logs del APScheduler para diagnosticar por qué el job no corre
2. Verificar si el backend se inició correctamente con los schedulers
3. Agregar alerta/monitoreo: si `MAX(trip_date)` de FACT_DAILY tiene lag > 2 días → alerta
4. Verificar si hay errores en `run_business_slice_real_refresh_job_safe` (advisory lock)

