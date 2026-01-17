# PASO B: Sistema Canónico de PLAN desde CSV Ruta 27

## 📋 Objetivo

Convertir la proyección Ruta 27 (CSV limpio) en una fuente canónica de PLAN, lista para comparación Plan vs Real.

## 🏗️ Arquitectura

```
CSV Ruta 27 → ops.plan_trips_monthly (versionado, append-only)
                    ↓
    ┌───────────────┼───────────────┐
    ↓               ↓               ↓
v_plan_trips_    v_plan_trips_    v_plan_kpis_
monthly          daily_equiv      monthly
```

## 📦 Componentes Implementados

### 1. Tabla Canónica: `ops.plan_trips_monthly`

Tabla versionada (append-only) que almacena el plan completo.

**Campos:**
- `plan_version` TEXT NOT NULL - Versión del plan (ej: 'ruta27_v1')
- `country` TEXT
- `city` TEXT
- `park_id` TEXT
- `lob_base` TEXT
- `segment` TEXT CHECK (segment IN ('b2b', 'b2c'))
- `month` DATE NOT NULL
- `projected_trips` INTEGER
- `projected_drivers` INTEGER
- `projected_ticket` NUMERIC
- `projected_trips_per_driver` NUMERIC (calculado)
- `projected_revenue` NUMERIC (calculado)
- `created_at` TIMESTAMPTZ DEFAULT NOW()

**Campos Calculados (STORED):**
- `projected_trips_per_driver = projected_trips / projected_drivers`
- `projected_revenue = projected_trips * projected_ticket`

**Constraints:**
- UNIQUE(plan_version, country, city, park_id, lob_base, segment, month)
- CHECK segment IN ('b2b', 'b2c')

### 2. Vistas

#### A) `ops.v_plan_trips_monthly`
Vista simplificada del plan mensual.

#### B) `ops.v_plan_trips_daily_equivalent`
Plan mensual convertido a equivalentes diarios (dividido por días del mes).

**Campos adicionales:**
- `projected_trips_daily`
- `projected_revenue_daily`
- `days_in_month`

#### C) `ops.v_plan_kpis_monthly`
KPIs mensuales del plan para consulta.

**Campos:**
- `kpi_trips`
- `kpi_drivers`
- `kpi_revenue`
- `kpi_productivity_required`
- `kpi_ticket_avg`
- `kpi_trips_per_driver`

### 3. Tabla de Validación: `ops.plan_validation_results`

Almacena resultados de validaciones post-ingesta.

**Tipos de validación:**
- `orphan_plan`: Combinaciones en Plan sin equivalente en Real
- `orphan_real`: Combinaciones en Real sin Plan correspondiente (warning)
- `missing_combo`: Plan sin datos reales históricos (info)

## 🚀 Instalación y Migración

### Paso 1: Ejecutar Migración Alembic

```bash
cd backend
alembic upgrade head
```

Esto creará:
- Esquema `ops` (si no existe)
- Tabla `ops.plan_trips_monthly`
- Vistas `ops.v_plan_trips_monthly`, `ops.v_plan_trips_daily_equivalent`, `ops.v_plan_kpis_monthly`
- Tabla `ops.plan_validation_results`

### Paso 2: Preparar CSV

El CSV debe tener las siguientes columnas (con headers):

```
country,city,park_id,lob_base,segment,month,projected_trips,projected_drivers,projected_ticket
Peru,Lima,park_001,Taxi,b2c,2026-01-01,10000,500,15.50
Colombia,Bogota,park_002,Delivery,b2b,2026-01-01,5000,200,25.00
```

**Validaciones:**
- `segment` debe ser 'b2b' o 'b2c'
- `month` debe ser formato fecha válido (YYYY-MM-DD o YYYY-MM)
- Campos numéricos: `projected_trips`, `projected_drivers`, `projected_ticket`

### Paso 3: Ingesta

#### Opción A: Script Python (Recomendado)

```bash
python scripts/ingest_plan_from_csv.py ruta27_proyeccion.csv ruta27_v1
```

#### Opción B: SQL Directo

```sql
SET plan_version = 'ruta27_v1';
SET csv_path = '/ruta/completa/al/archivo.csv';
\i scripts/sql/ingest_plan_trips_monthly.sql
```

### Paso 4: Validación Post-Ingesta

```bash
python scripts/validate_plan_post_ingestion.py ruta27_v1
```

O desde SQL:

```sql
SET plan_version = 'ruta27_v1';
\i scripts/sql/validate_plan_trips_monthly.sql
```

### Paso 5: Reporte Final

```bash
python scripts/report_plan_ready_for_comparison.py ruta27_v1
```

## 📊 Ejemplos de Consulta

### Consultar plan mensual

```sql
SELECT * 
FROM ops.v_plan_trips_monthly
WHERE plan_version = 'ruta27_v1'
AND month >= '2026-01-01'
ORDER BY month, country, city;
```

### Consultar equivalentes diarios

```sql
SELECT 
    month,
    country,
    city,
    projected_trips_daily,
    projected_revenue_daily,
    days_in_month
FROM ops.v_plan_trips_daily_equivalent
WHERE plan_version = 'ruta27_v1'
AND month = '2026-01-01';
```

### Consultar KPIs

```sql
SELECT 
    month,
    country,
    city,
    kpi_trips,
    kpi_drivers,
    kpi_revenue,
    kpi_productivity_required
FROM ops.v_plan_kpis_monthly
WHERE plan_version = 'ruta27_v1'
ORDER BY month, country, city;
```

### Ver validaciones

```sql
SELECT 
    validation_type,
    severity,
    country,
    city,
    lob_base,
    month,
    message
FROM ops.plan_validation_results
WHERE plan_version = 'ruta27_v1'
ORDER BY severity, validation_type;
```

## 🔍 Validaciones Implementadas

### 1. Orphan Plan (Warning)
Combinaciones en Plan sin equivalente en Real (park_id/lob/segment).

**Severidad:** `warning`

**Acción:** Revisar si son combinaciones nuevas o errores en el plan.

### 2. Orphan Real (Info)
Combinaciones en Real sin Plan correspondiente.

**Severidad:** `info` (solo warning, no bloquea)

**Acción:** Información para identificar huecos en el plan.

### 3. Missing Combo (Info)
Plan sin datos reales históricos (combinaciones nuevas o sin historial).

**Severidad:** `info`

**Acción:** Normal para meses futuros o nuevas combinaciones.

## ⚠️ Principios Críticos

1. **Append-Only**: Nada se actualiza ni borra. Solo INSERT.
2. **Versionado**: Cada versión del plan es independiente.
3. **Sin Mezcla**: Plan y Real no se mezclan en la misma tabla.
4. **Auditable**: Todo está registrado con `created_at` y `plan_version`.
5. **Sin Lógica Mágica**: Todo es explícito, calculable y auditable.

## 🚨 Restricciones

- ❌ NO tocar `trips_all`
- ❌ NO tocar Real (`bi.*`)
- ❌ NO crear lógica de negocio fuera de SQL
- ❌ NO hacer UPDATE de registros existentes
- ❌ NO borrar versiones previas

## ✅ Checklist de Verificación

Antes de considerar el plan listo para comparación:

- [ ] Migración Alembic ejecutada exitosamente
- [ ] CSV cargado sin errores
- [ ] Validaciones ejecutadas
- [ ] 0 errores en validaciones (warnings son aceptables)
- [ ] Vistas funcionando correctamente
- [ ] Reporte final confirma que está listo

## 📝 Notas Técnicas

- La tabla usa campos calculados `STORED` para `projected_trips_per_driver` y `projected_revenue`.
- El constraint UNIQUE previene duplicados por versión.
- Las vistas ordenan por `plan_version DESC` para mostrar última versión por defecto.
- Los índices están optimizados para consultas por `plan_version`, `month`, `park_id`, y `(country, city, lob_base)`.

## 🔗 Archivos Relacionados

- Migración: `backend/alembic/versions/003_create_plan_trips_monthly_system.py`
- Ingesta SQL: `backend/scripts/sql/ingest_plan_trips_monthly.sql`
- Ingesta Python: `backend/scripts/ingest_plan_from_csv.py`
- Validación SQL: `backend/scripts/sql/validate_plan_trips_monthly.sql`
- Validación Python: `backend/scripts/validate_plan_post_ingestion.py`
- Reporte: `backend/scripts/report_plan_ready_for_comparison.py`
