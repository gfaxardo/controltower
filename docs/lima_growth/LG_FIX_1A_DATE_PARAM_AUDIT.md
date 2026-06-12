# LG_FIX_1A_DATE_PARAMETER_AUDIT — Date Parameter Audit

**Generated:** 2026-06-12T19:36  
**Operational date (backend):** `2026-06-12`  
**Date passed by UI to endpoints:** `2026-06-11` (derived from operational-date)

---

## Date Flow

```
LimaGrowthDashboardUI1A.jsx (useEffect line 34)
  → GET /yego-lima-growth/refresh/operational-date
  → response.operational_data_date = "2026-06-12"
  → setOperationalDate("2026-06-12")

useGrowthIntelligence(date="2026-06-12") (useEffect line 47-59)
  → calls each endpoint with date = "2026-06-12"
  e.g. getLimaGrowthOperationalSummary("2026-06-12")
       getLimaGrowthDriverStateSummary("2026-06-12")
```

**Nota:** El hook usa `if (!date) return` — espera que el date esté seteado antes de fetchear. La fecha se pasa directamente a cada endpoint como `params: { date }`.

---

## Mismatch Table

| Endpoint | Date Param Usado | Latest Date en Tabla | Mismatch | Impacto |
|----------|-----------------|---------------------|----------|---------|
| `/operational-summary` | `2026-06-12` | `2026-06-12` (snapshot) | NO | Data existe. No es 0. |
| `/driver-state/summary` | `2026-06-12` | `2026-06-12` (37K rows) | NO | Data existe. `total_drivers: 148167`. |
| `/operational-truth` | `2026-06-12` | `2026-06-12` (snapshot) | NO | Data existe, pero efectiva es `2026-06-09`. |
| `/programs/summary` | `2026-06-12` | `2026-06-12` (56K rows) | NO | Data existe. Programs tienen `eligible_total > 0`. |
| `/programs/status` | `2026-06-12` | `2026-06-12` | NO | Data existe. |
| `/taxonomy/summary` | `2026-06-12` | **2026-06-10** | **YES** | `total_drivers: 0`. Distribuciones vacías. |
| `/movement/summary` | `2026-06-12` | **2026-06-10** | **YES** | `total_movements: 0`, `entries: 0`, `exits: 0`. |
| `/movement/records` | `2026-06-12` | **2026-06-10** | **YES** | Posible causa del 404 (no hay records para esa fecha). |
| `/effectiveness/summary` | none (sin params) | **2026-06-10** (10 rows) | N/A | Tabla casi vacía causa 500. |

---

## Tablas vs Fechas Disponibles

| Fecha Solicitada | `driver_state_snapshot` | `program_eligibility_daily` | `driver_lifecycle_daily` | `taxonomy_v2_daily` | `driver_movement_fact` |
|-------------------|------------------------|----------------------------|------------------------|-------------------|----------------------|
| **2026-06-12** | 18,545 rows | 28,128 rows | **0 rows** | **0 rows** | **0 rows** |
| **2026-06-11** | 18,545 rows | 28,128 rows | **0 rows** | **0 rows** | **0 rows** |
| **2026-06-10** | 18,545 rows | 28,128 rows | **18,545 rows** | **18,545 rows** | **68,473 rows** |
| **2026-06-05** | 18,545 rows | 28,128 rows | 18,545 rows | 18,545 rows | data exists |

---

## Hipótesis Verificada

**El pipeline V2 diario NO se ejecutó para 2026-06-11 ni 2026-06-12.** Las tablas `driver_state_snapshot` y `program_eligibility_daily` tienen datos hasta 2026-06-12 (se actualizan por otro mecanismo). Pero `lifecycle_daily`, `taxonomy_v2_daily`, y `movement_fact` están congeladas en 2026-06-10.

---

## Impacto de Fecha por Tab UI1A

| Tab | Endpoints con Mismatch | Efecto Visible |
|-----|----------------------|----------------|
| **Banner** | (no usa date) | Real: system CRITICAL. 12 assets broken. |
| **Overview** | operational-truth (KPI source_date=06-09) | `drivers_with_program: 0` — el campo no existe en payload. |
| **Programs** | programs/summary (data OK) | `eligible_drivers: 0` — payload mismatch, no date mismatch. |
| **Segments** | taxonomy/summary (date mismatch 06-12 vs 06-10) | `total_drivers: 0`, distribuciones vacías. |
| **Movement** | movement/summary + records (date mismatch 06-12 vs 06-10) | `total_movements: 0`, records = 404. |
| **RNA** | loyalty/summary (OK), rna-priority (500) | RNA data = 0 porque loyalty/summary no tiene campos RNA. |
| **Driver Explorer** | /drivers/activity-summary (OK pero lento 21s) | Carga pero necesita filtro. |
| **Effectiveness** | effectiveness/summary (500) | 500 → tabla casi vacía. |

---

## Si la UI pidiera 2026-06-10 en vez de 2026-06-12

| Endpoint | Con 2026-06-12 | Con 2026-06-10 |
|----------|----------------|----------------|
| taxonomy/summary | total_drivers=0 | Probablemente con datos válidos |
| movement/summary | total_movements=0 | Probablemente con 68K+ transiciones |
| movement/records | 404 | Probablemente con datos |
| effectiveness/summary | 500 | 500 (tabla vacía independientemente de fecha) |

**Root cause NO es solo date mismatch — también hay payload shape mismatch y tablas vacías.**
