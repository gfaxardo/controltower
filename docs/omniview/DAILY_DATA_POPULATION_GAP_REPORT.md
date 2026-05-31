# DAILY DATA POPULATION GAP — H1-B REPORT

**Fecha**: 2026-05-30
**Motor**: Control Foundation
**Gate**: H1-B Hotfix

---

## 1. Causa Raíz

**Alta probabilidad**: Gap en la fuente upstream `public.trips_2026` para los días May 25-28. Estos días no tienen filas en la tabla fuente, por lo que el pipeline de refresh no puede poblarlos en `FACT_DAILY`.

Evidencia:
- El código de refresh (`load_business_slice_day_for_month`) hace DELETE + INSERT del mes completo
- Si source tiene datos → day_fact tendrá datos
- Si source NO tiene datos → day_fact tendrá huecos
- No hay bug de código que cause omisión selectiva de días intermedios

---

## 2. Fechas Afectadas

| Fecha | Día | Estado |
|-------|-----|--------|
| 2026-05-25 | Lunes | SIN datos reales |
| 2026-05-26 | Martes | SIN datos reales |
| 2026-05-27 | Miércoles | SIN datos reales |
| 2026-05-28 | Jueves | SIN datos reales |
| 2026-05-24 | Domingo | OK |
| 2026-05-29 | Viernes | OK (aparece como último cierre) |
| 2026-05-30 | Sábado | Parcial (hoy) |

---

## 3. Capa Afectada

| Capa | Afectada | Detalle |
|------|----------|---------|
| Source (`public.trips_2026`) | **SÍ (upstream)** | Datos faltan para 25-28 |
| View (`v_real_trips_enriched_base`) | Hereda gap | UNION ALL de source |
| FACT_DAILY | Hereda gap | DELETE+INSERT completo pero source vacío |
| Backend API (`omniview-projection`) | Hereda gap | Lee de FACT_DAILY |
| Frontend | Muestra lo que hay | Sin datos reales → muestra vacío |

---

## 4. SQL de Diagnóstico

Ejecutar en base de datos de producción:

```sql
-- Verificar qué días tienen datos en source (causa raíz sospechada)
SELECT trip_date, count(*)
FROM public.trips_2026
WHERE trip_date BETWEEN '2026-05-24' AND '2026-05-30'
GROUP BY trip_date
ORDER BY trip_date;

-- Verificar qué días tienen datos en day_fact
SELECT trip_date, count(*), sum(trips_completed)
FROM ops.real_business_slice_day_fact
WHERE trip_date BETWEEN '2026-05-24' AND '2026-05-30'
GROUP BY trip_date
ORDER BY trip_date;

-- Verificar última refresh
SELECT MAX(refreshed_at), MAX(loaded_at)
FROM ops.real_business_slice_day_fact
WHERE trip_date >= '2026-05-01';
```

---

## 5. Fix Requerido

### Si source no tiene datos (H1 confirmada):
1. Investigar por qué el ETL upstream no cargó May 25-28 a `public.trips_2026`
2. Cargar los datos faltantes en `public.trips_2026`
3. Ejecutar refresh manual:
   ```bash
   python -m scripts.refresh_omniview_real_slice --force
   ```
   o via API:
   ```bash
   curl -X POST "http://localhost:8000/ops/business-slice/real-refresh-omniview?force=true"
   ```

### Si source SÍ tiene datos pero FACT_DAILY no:
   - Ejecutar backfill para May 2026:
   ```bash
   python -m scripts.backfill_business_slice_daily --from-date 2026-05-01 --to-date 2026-05-30
   ```

---

## 6. Código — Sin cambios requeridos

El código del pipeline (refresh job, loader, projection service, frontend) está correcto. No requiere modificaciones.

---

## 7. Build

N/A — no hay cambios de código.

---

## 8. Runtime

Pendiente de verificación post-backfill. Los pasos 4 (SQL diagnóstico) deben ejecutarse primero para confirmar la causa raíz.

---

## 9. Riesgos

| Riesgo | Severidad |
|--------|-----------|
| ETL upstream con gap recurrente (no es la primera vez) | HIGH |
| Refresh job no monitoreado (no hay alerta si source está vacío) | MEDIUM |
| No hay validación de completitud de datos en el pipeline | MEDIUM |

