# FASE 2A.1.1 — DRIVER LIFECYCLE HARDENING

**Fecha:** 2026-05-21
**Motor:** Diagnostic Engine (#2 de 9)
**Fase:** 2A.1.1 — Performance + 2025/2026 Coverage
**Veredicto:** CONDITIONAL GO

---

## 1. PROBLEMA DETECTADO

Fase 2A.1 cerro GO pero con limitaciones tecnicas:

| Problema | Impacto |
|----------|---------|
| Solo lee `public.trips_2026` | No incluye data historica 2025 |
| Query directa sobre tabla fuente | ~3.8s por request |
| Sin capa materializada | Escaneo de ~50M rows con JOIN a dim_park |

---

## 2. DECISION ARQUITECTONICA

Crear tabla fact pre-agregada a grano `driver_id + activity_date`:

```
ops.driver_daily_activity_fact
```

Esto permite:
- Lectura desde tabla indexada y pre-agregada (no JOIN a dim_park por query)
- Cobertura 2025 + 2026 via UNION ALL durante el refresh
- Service mantiene logica de clasificacion sin cambios

---

## 3. FUENTE ANTERIOR

```python
TABLE_TRIPS = "public.trips_2026"
# Query directa:
#   FROM public.trips_2026 t
#   LEFT JOIN dim.dim_park p ON t.park_id = p.park_id
#   WHERE t.condicion = 'Completado'
#   GROUP BY t.conductor_id
```

---

## 4. NUEVA FUENTE OPTIMIZADA

```sql
ops.driver_daily_activity_fact
  PRIMARY KEY (driver_id, activity_date)
  -- poblado desde trips_2025 + trips_2026 (UNION ALL)
  -- country/city pre-resueltos via dim_park en tiempo de refresh
```

```python
FACT_TABLE = "ops.driver_daily_activity_fact"
# Query optimizada:
#   FROM ops.driver_daily_activity_fact f
#   WHERE f.activity_date >= CURRENT_DATE - %s
#   GROUP BY f.driver_id
#   -- sin JOIN a dim_park (ya resuelto)
```

---

## 5. COBERTURA 2025/2026

| Año | Estado | Filas |
|-----|--------|-------|
| 2026 | Habilitado | 309,649 |
| 2025 | Pendiente backfill | 0 |

**Backfill 2025:** Ejecutar en ventana de bajo trafico:
```bash
cd backend && python scripts/refresh_driver_daily_activity_fact.py --backfill-from 2025-01-01
```

---

## 6. INDICES CREADOS

| Indice | Columnas | Proposito |
|--------|----------|-----------|
| PK | (driver_id, activity_date) | Unicidad + lookup por driver |
| ix_dda_activity_date | (activity_date) | Filtro por fecha |
| ix_dda_driver_id | (driver_id) | Lookup por driver |
| ix_dda_country_city | (country, city) | Filtro geografico |
| ix_dda_country_city_date | (country, city, activity_date) | Filtro geo + fecha |
| ix_dda_date_driver | (activity_date, driver_id) | Range scan optimizado |

---

## 7. REFRESH SCRIPT

**Archivo:** `backend/scripts/refresh_driver_daily_activity_fact.py`

**Modos:**
- `--days N`: poblar ultimos N dias (rapido, default 90)
- `--full`: poblar todo el historico (truncate + insert)
- `--backfill-from YYYY-MM-DD`: poblar desde fecha especifica

**Validacion automatica:** conteos, date range, year breakdown, quality checks.

---

## 8. PERFORMANCE ANTES/DESPUES

| Endpoint | Antes (raw trips) | Despues (fact table) | Mejora |
|----------|-------------------|---------------------|--------|
| summary | ~3800ms | ~1800ms | 53% mas rapido |
| risk-list | ~3800ms | ~1800ms | 53% mas rapido |
| funnel | ~3800ms | ~1800ms | 53% mas rapido |

**Causa del remanente:** GROUP BY sobre 309K filas requiere hash aggregation en PostgreSQL. Una tabla pre-agregada a nivel driver eliminaria este costo (<500ms estimado).

---

## 9. RIESGOS REMANENTES

| Riesgo | Severidad | Mitigacion |
|--------|-----------|------------|
| 2025 no poblado aun | LOW | Backfill programado en ventana nocturna |
| GROUP BY sobre 309K filas | LOW | Tabla driver-level en Fase 2A.2 si es necesario |
| Fact table requiere refresh periodico | LOW | Script de refresh listo; programar via cron/scheduler |
| Primary key on (driver_id, activity_date) ocupa espacio | LOW | 309K filas = ~30MB estimado |

---

## 10. QUE NO SE CAMBIO

- Reglas de lifecycle (CHURNED, DORMANT, etc.) — sin cambios
- Reglas de risk_level (HIGH, MEDIUM, LOW) — sin cambios
- Contrato API (campos de respuesta) — aditivo (se agrego metadata)
- Router `/driver-lifecycle` — sin cambios
- Frontend `DriverLifecycleDashboard.jsx` — sin cambios
- Omniview Matrix — sin tocar
- Plan vs Real — sin tocar

---

## 11. VEREDICTO

**CONDITIONAL GO** — 26/27 validaciones QA aprobadas, 0 fallas criticas.

1 warning: 2025 data pending backfill (run `--backfill-from 2025-01-01` during low-traffic window).

Fase 2A.1.1 puede cerrarse. El unico pendiente es operacional (backfill 2025), no bloquea avance a 2A.2.

---

*Documento generado por Fase 2A.1.1 — Driver Lifecycle Hardening*
*QA script: backend/scripts/validate_phase2a1_1_driver_lifecycle_hardening.py*
*Refresh script: backend/scripts/refresh_driver_daily_activity_fact.py*
