# Driver Lifecycle — Vista alterna (solo datos reales)

**Proyecto:** YEGO CONTROL TOWER  
**Fuentes:** `public.trips_all`, `public.drivers`  
**Reglas:** No inventar columnas; Plan y Real no se mezclan; todo KPI trazable a filas base.

---

## A) MAPEO AUTOMÁTICO (SCAN)

### Cómo ejecutar el SCAN

```bash
cd backend
python -m scripts.driver_lifecycle_scan --timeout 300000
```

Salida en consola y en `backend/driver_lifecycle_scan_output.txt`. Con tablas muy grandes, aumentar `--timeout` o ejecutar las queries de información_schema y perfilado por separado.

### Resultado del SCAN (esquema detectado)

#### 1) Esquema y columnas

**public.trips_all**

| column_name            | data_type                     | is_nullable |
|------------------------|-------------------------------|-------------|
| id                     | character varying             | YES         |
| condicion               | character varying             | YES         |
| conductor_id            | character varying             | YES         |
| fecha_inicio_viaje      | timestamp without time zone    | YES         |
| fecha_finalizacion      | timestamp without time zone    | YES         |
| tipo_servicio           | character varying             | YES         |
| park_id                 | character varying             | YES         |
| ... (distancia_km, precio_yango_pro, efectivo, tarjeta, pago_corporativo, etc.) | | |

**public.drivers**

| column_name       | data_type                     | is_nullable |
|-------------------|-------------------------------|-------------|
| driver_id         | character varying             | NO          |
| id                | bigint                        | NO          |
| park_id           | character varying             | YES         |
| hire_date         | date                          | YES         |
| fire_date         | date                          | YES         |
| created_at        | timestamp without time zone   | YES         |
| updated_at        | timestamp without time zone   | YES         |
| work_status       | character varying             | YES         |
| current_status    | character varying             | YES         |
| active            | boolean                       | YES         |
| works_terms       | character varying             | YES         |
| ... (first_name, last_name, phone, rating, car_*, license_*, etc.) | | |

#### 2) Resumen SCAN (nombres reales)

| Concepto              | Columna / regla real                                      |
|-----------------------|-----------------------------------------------------------|
| **best_join_key**     | `trips_all.conductor_id = drivers.driver_id`              |
| **completion_ts**     | `fecha_finalizacion` (solo filas con `condicion = 'Completado'`; si muchos nulls, fallback `fecha_inicio_viaje`) |
| **request_ts**        | `fecha_inicio_viaje`                                     |
| **driver_key (trips)**| `conductor_id`                                           |
| **driver_key (drivers)** | `driver_id` (PK lógico)                               |
| **driver_registered_ts** | `drivers.created_at`                                 |
| **driver_approved_ts**  | No existe; opcional `hire_date` como proxy              |
| **Dimensiones (trips)**| `park_id`, `tipo_servicio`; country/city vía `dim.dim_park` si existe join |

#### 3) Join coverage

Ejecutar tras el SCAN (o con timeout alto) para validar:

```sql
SELECT
  (SELECT COUNT(*) FROM public.trips_all) AS total_trips,
  COUNT(*) AS trips_with_driver,
  COUNT(DISTINCT t.conductor_id) AS distinct_drivers_matched,
  ROUND(100.0 * COUNT(*) / NULLIF((SELECT COUNT(*) FROM public.trips_all), 0), 2) AS pct_trips_mapped
FROM public.trips_all t
INNER JOIN public.drivers d ON t.conductor_id = d.driver_id;
```

---

## B) DATA CONTRACT

### Tabla: trips_all (columnas usadas)

| Columna canónica  | Columna real             | Tipo   | Uso / regla |
|-------------------|--------------------------|--------|-------------|
| driver_key        | conductor_id             | varchar| Join con drivers; excluir NULL para lifecycle. |
| status            | condicion                | varchar| Solo filas `condicion = 'Completado'` para completados. |
| completion_ts     | fecha_finalizacion       | timestamptz | Timestamp fin viaje; nulls rellenar con fecha_inicio_viaje si aplica. |
| request_ts        | fecha_inicio_viaje       | timestamptz | Inicio/solicitud viaje. |
| dim_park          | park_id                  | varchar| Segmentación; puede mapear a country/city vía dim.dim_park. |
| dim_lob           | tipo_servicio            | varchar| Línea de negocio (real). |
| segment           | (derivado)               | —      | B2B si pago_corporativo > 0, si no B2C. |

**Reglas de limpieza**

- Excluir filas sin `conductor_id` para métricas por driver.
- Para “viaje completado”: `condicion = 'Completado'`.
- completion_ts: usar `fecha_finalizacion` cuando no sea NULL; si NULL y condicion = 'Completado', usar `fecha_inicio_viaje`.
- Normalización ciudad: solo si se usa join a dim.dim_park (no en trips_all directo).

### Tabla: drivers (columnas usadas)

| Columna canónica   | Columna real   | Tipo   | Uso / regla |
|--------------------|----------------|--------|-------------|
| driver_key         | driver_id     | varchar| Join con trips_all.conductor_id. |
| registered_ts      | created_at    | timestamptz | Alta en sistema; TtF desde registro. |
| hire_date          | hire_date     | date   | Opcional proxy “approved/activo en flota”. |
| status             | current_status / work_status | varchar | Estado driver (opcional para filtros). |
| park_id            | park_id       | varchar| Segmentación. |

**Reglas**

- Join: `trips_all.conductor_id = drivers.driver_id`.
- Si `created_at` es NULL, TtF desde registro = N/A para ese driver.

---

## C) DEFINICIONES (KPI LOGIC)

### 1) Activation

- **activation_ts** = por driver, `MIN(completion_ts)` sobre viajes completados.
- completion_ts = `COALESCE(fecha_finalizacion, fecha_inicio_viaje)` con `condicion = 'Completado'`.

### 2) Time-to-first-trip (TtF)

- **Prioridad 1:** Si existe `drivers.created_at`:  
  `ttf_days = (activation_ts::date - created_at::date)` (o en horas si se prefiere).
- **Prioridad 2:** Si no hay created_at pero hay request_ts en trips:  
  `activation_ts - MIN(request_ts)` por driver (proxy “tiempo desde primer evento”).
- **Si ninguno:** TtF = N/A (documentar en contrato).

### 3) Lifetime

- **lifetime_days** = `(last_completed_ts::date - activation_ts::date)`.
- **last_completed_ts** = `MAX(completion_ts)` por driver (solo completados).
- **active_weeks** = número de semanas (week_start) con ≥ 1 viaje completado.
- **tenure_bucket**: ej. 0–7d, 8–30d, 31–90d, 91–365d, 365+d.

### 4) PT / FT (work mode)

- **Umbrales iniciales (proponer):**  
  - PT: trips por semana &lt; 20 (o trips por mes &lt; 80).  
  - FT: trips por semana ≥ 20 (o trips por mes ≥ 80).
- Calibración: percentiles P50, P75, P90 de trips/week y trips/month por driver para ajustar umbrales.

### 5) Churn

- **churn_14d:** driver con último completion_ts &gt; 14 días antes del fin del periodo de análisis y sin viajes en los últimos 14 días.
- **churn_28d:** igual con 28 días.
- **churn_flow_week t:** conductores que en semana t−1 tenían ≥1 completado y en semana t tienen 0 completados (y se consideran churned por ventana elegida).

### 6) Reactivation

- **reactivated_week:** en semana t el driver tiene ≥1 completado y en las N semanas anteriores (según ventana de churn) tenía 0 completados (estaba churned).

### 7) Activation hour

- **activation_hour** = `EXTRACT(HOUR FROM activation_ts)` (0..23); histograma para análisis.

### 8) Sessions + Intermittency (opcional)

- Sessionizar por driver con gap &gt; 90 min entre completion_ts consecutivos.
- Métricas: avg_session_duration, sessions_per_week, cv_trips_week (coef. variación viajes/semana).
- Flag “intermitencia alta” (heurístico; no afirmar multi-app).

---

## D) SQL (BUILD)

Schema objetivo: **ops** (existente). Si no existiera, usar `CREATE SCHEMA IF NOT EXISTS ops;`.

### D.1) MV driver_lifecycle_base (1 fila por driver)

Incluye: activation_ts, last_completed_ts, lifetime_days, activation_hour, registered_ts (created_at), ttf desde created_at si aplica. Join con drivers por `conductor_id = driver_id`.

**Archivo:** `backend/sql/driver_lifecycle_build.sql`

### D.2) MV driver_weekly_stats (driver-week)

- trips_completed_week, work_mode_week (PT/FT), is_active_week, churn_14/28, reactivated_week.
- Dims: por trip están park_id y tipo_servicio; por semana usar modo (mode) del park_id o del primer trip de la semana; documentar en contrato.

### D.3) MV driver_monthly_stats (driver-month)

- Misma lógica que semanal en granularidad mes.

### D.4) MV weekly_kpis y monthly_kpis (agregados por period + dims)

- activations, active_drivers, churn_flow, churn_rate, reactivated, reactivation_rate, PT/FT mix, lifetime median, etc.

### D.5) Índices y refresh

- Unique index en cada MV para `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
- Función `ops.refresh_driver_lifecycle_mvs()` que hace refresh en orden de dependencias.

---

## E) VALIDACIONES

Queries de chequeo:

1. **Activations por semana/mes**  
   Comprobar que activations en weekly_kpis = drivers cuyo `MIN(completion_ts)` cae en esa semana/mes.

2. **Join coverage**  
   % de trips con conductor_id mapeado a drivers (query de la sección A.3).

3. **TtF**  
   Distribución min/median/p90 de TtF; detectar outliers negativos (activation_ts &lt; created_at).

4. **Churn/Reactivation**  
   Ningún driver “reactivated” en t sin haber estado “churned” en ventana anterior; sanity check de flujo.

**Archivo:** `backend/sql/driver_lifecycle_validations.sql`

- Validación activations semanal/mensual vs count directo desde base.
- Join coverage % (trips completados con conductor_id mapeado a drivers).
- TtF: min/median/p90 y detección de outliers negativos (activation_ts &lt; registered_ts).
- Unicidad driver_key en base y (driver_key, week_start) en weekly_stats.
