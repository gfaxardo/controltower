# YEGO Control Tower - Fase 2A (Refactor Seguro + Plan/Real Equiparables + UI Digerible)

Sistema web completo para comparación Plan vs Real con validación de universo operativo. En esta fase, el sistema muestra Real histórico (2025) y Plan futuro (2026). La comparación activa se activará automáticamente cuando exista Real 2026.

## 📋 Arquitectura

```
Frontend (React + Vite) → Backend (FastAPI) → PostgreSQL (yego_integral)
                                         ↓
                                    plan.plan_long_valid
                                    plan.plan_long_out_of_universe
                                    plan.plan_long_missing
```

## 🏗️ Estructura del Proyecto

```
backend/app/
├── main.py                    # FastAPI app principal
├── settings.py                # Configuración (.env)
├── db/
│   ├── connection.py          # Pool de conexiones
│   └── schema_verify.py        # Verificación de esquema al inicio
├── contracts/
│   └── data_contract.py       # Mapeo semántico de columnas
├── adapters/
│   ├── real_repo.py          # Lee bi.* + dim.*
│   └── plan_repo.py          # Lee/escribe plan.*
├── services/
│   ├── plan_parser_service.py # Parsea hoja "Proyección"
│   ├── real_normalizer_service.py # Normaliza Real mensual
│   ├── ops_universe_service.py    # Construye universo operativo
│   ├── summary_service.py    # Pivots mensuales
│   └── core_service.py       # Join + deltas + status
└── routers/
    ├── plan.py               # Endpoints de plan
    ├── real.py               # Endpoints de real
    ├── core.py               # Endpoints core
    ├── ops.py                # Endpoints universo operativo
    └── health.py             # Healthcheck
```

## 🚀 Instalación y Configuración

### Backend

1. **Instalar dependencias:**
```bash
cd backend
pip install -r requirements.txt
```

2. **Configurar variables de entorno:**
Crear archivo `.env` en `backend/` con:
```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=yego_integral
DB_USER=tu_usuario
DB_PASSWORD=tu_password
ENVIRONMENT=dev
```

3. **Ejecutar el backend:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

El backend estará disponible en `http://localhost:8000`
Documentación API disponible en `http://localhost:8000/docs`

### Frontend

1. **Instalar dependencias:**
```bash
cd frontend
npm install
```

2. **Ejecutar el frontend:**
```bash
npm run dev
```

El frontend estará disponible en `http://localhost:5173`

## 📊 Fuentes de Datos

### REAL (Solo Lectura)

El sistema consume datos REAL desde las siguientes tablas/vistas de PostgreSQL:

- **bi.real_daily_enriched**: Datos reales diarios enriquecidos
- **bi.real_monthly_agg**: Datos reales agregados mensualmente
- **dim.dim_park**: Dimensión de parque (mapea park_id → city, country, line_of_business, park_name)

**Columnas mapeadas:**
- `trips` → `orders_completed` (en bi.real_monthly_agg y bi.real_daily_enriched)
- `revenue` → columna de ingresos (inspeccionada automáticamente, puede no existir)

**Nota:** El backend verifica automáticamente la estructura de estas tablas al iniciar y loggea las columnas encontradas. Si faltan columnas críticas, el sistema falla con mensajes claros en modo DEV.

### Columnas Reales Detectadas

El sistema inspecciona automáticamente las columnas reales al iniciar y documenta:

- **bi.real_monthly_agg:**
  - Columna de trips: `orders_completed`
  - Columna de revenue: Inspeccionada dinámicamente (puede no existir)
  - Formato de period: Construido desde `year` + `month` (formato YYYY-MM)

- **bi.real_daily_enriched:**
  - Columna de trips: `orders_completed`
  - Formato de fecha: Columna `date`

- **dim.dim_park:**
  - Columnas dimensionales: `park_id`, `city`, `country`, `default_line_of_business`

Los resultados de la inspección se loggean al iniciar el servidor. Revisa los logs para ver la estructura completa de columnas detectadas.

### PLAN

El Plan se carga desde una plantilla simple (CSV o XLSX) mediante la interfaz web. El sistema:

1. Valida columnas exactas: `period`, `country`, `city`, `line_of_business`, `metric`, `plan_value`
2. Valida formato de period: YYYY-MM
3. Valida metric: debe ser `trips`, `revenue`, `commission`, o `active_drivers`
4. Persiste en `plan.plan_long_raw`
5. Valida contra universo operativo y separa en 3 tablas:
   - `plan.plan_long_valid`: solo filas válidas (en universo operativo)
   - `plan.plan_long_out_of_universe`: ciudades/líneas no operativas
   - `plan.plan_long_missing`: combos operativos sin plan

**Plantilla Simple del Plan:**

Formato esperado (CSV o XLSX) con columnas exactas:

| period | country | city | line_of_business | metric | plan_value |
|--------|---------|------|------------------|--------|------------|
| 2026-01 | Peru | Lima | Taxi | trips | 10000 |
| 2026-01 | Peru | Lima | Taxi | revenue | 50000 |
| 2026-02 | Colombia | Bogota | Taxi | trips | 8000 |

- **period**: Formato YYYY-MM (ej: 2026-01)
- **country**: País (ej: Peru, Colombia)
- **city**: Ciudad (ej: Lima, Bogota)
- **line_of_business**: Línea de negocio (ej: Taxi, Delivery)
- **metric**: Debe ser uno de: `trips`, `revenue`, `commission`, `active_drivers`
- **plan_value**: Valor numérico del plan

**Nota:** También existe soporte para formato Excel complejo (deprecated) mediante `/plan/upload`, pero se recomienda usar la plantilla simple.

## 🌍 Universo Operativo

El sistema construye automáticamente el universo operativo desde Postgres:

- Fuente: `bi.real_monthly_agg` + `dim.dim_park`
- Regla: incluir solo combinaciones `(country, city, line_of_business)` con `SUM(orders_completed) > 0` en 2025
- Uso: el plan se valida contra este universo; solo las filas válidas aparecen en la vista principal

## 🔌 Endpoints API

### Plan

- `POST /plan/upload_simple`: Sube un archivo de plantilla simple (CSV o XLSX) del Plan
  - Formato: `multipart/form-data`
  - Retorna: `rows_loaded`, `rows_valid`, `rows_out_of_universe`, `missing_combos_count`, `source_file_name`, `uploaded_at`, `file_hash`, `preview_out_of_universe_top20`
  - Valida columnas exactas: period, country, city, line_of_business, metric, plan_value

- `POST /plan/upload`: [DEPRECATED] Sube un archivo Excel del Plan (formato complejo)
  - Formato: `multipart/form-data`
  - Retorna: `rows_valid`, `rows_out_of_universe`, `missing_combos_count`, `source_file_name`, `uploaded_at`, `file_hash`

- `GET /plan/summary/monthly`: Obtiene resumen mensual de Plan en formato pivot
  - Parámetros: `country`, `city`, `line_of_business`, `year`
  - Retorna: `period`, `trips_plan`, `revenue_plan`

- `GET /plan/out_of_universe`: Obtiene datos del plan fuera del universo operativo
  - Parámetros: `country`, `city`, `line_of_business`, `year`

- `GET /plan/missing`: Obtiene combinaciones operativas sin plan
  - Parámetros: `country`, `city`, `line_of_business`

### Real

- `GET /real/summary/monthly`: Obtiene resumen mensual de Real en formato pivot
  - Parámetros: `country`, `city`, `line_of_business`, `year`
  - Retorna: `period`, `trips_real`, `revenue_real` (nullable)

### Core

- `GET /core/summary/monthly`: Vista mensual combinada de Plan y Real
  - Parámetros: `country`, `city`, `line_of_business`, `year_real` (default 2025), `year_plan` (default 2026)
  - Retorna: `period`, `trips_plan`, `revenue_plan`, `trips_real`, `revenue_real`, `delta_trips_abs`, `delta_trips_pct`, `delta_revenue_abs`, `delta_revenue_pct`, `comparison_status`

### Ops

- `GET /ops/universe`: Retorna el universo operativo
  - Parámetros: `country?`, `city?` (filtros opcionales)
  - Retorna: lista de combinaciones `(country, city, line_of_business)` válidas

### Health

- `GET /health`: Healthcheck del servicio

## 📈 Vista CORE

La vista CORE combina Plan y Real y calcula:

- **trips_plan**, **revenue_plan**: Valores del Plan (nullable)
- **trips_real**, **revenue_real**: Valores del Real (nullable)
- **delta_trips_abs**, **delta_revenue_abs**: Diferencia absoluta (real - plan)
- **delta_trips_pct**, **delta_revenue_pct**: Diferencia porcentual ((real/plan) - 1) * 100
- **comparison_status**: Estado de comparación:
  - `NOT_COMPARABLE`: Plan y Real en años distintos → delta null
  - `NO_REAL_YET`: Plan futuro sin Real disponible → delta null
  - `COMPARABLE`: Plan y Real comparables (mismo año y existe real) → delta calculado

## 🖥️ Interfaz de Usuario

### Vista Principal (Plan Válido)

- Tabla mensual digerible (12 filas máximo)
- Muestra Plan 2026 + Real 2025
- Deltas solo si `comparison_status === 'COMPARABLE'`
- Cards KPI: Trips Real YTD, Trips Plan YTD, Revenue (si existe)

### Tabs

1. **Plan Válido** (default): muestra solo filas en universo operativo
2. **Fuera de Universo**: muestra ciudades/líneas no operativas (para revisión)
3. **Huecos del Plan**: muestra combos operativos sin plan

### Filtros

- País
- Ciudad
- Línea de Negocio
- Año Real (default: 2025)
- Año Plan (default: 2026)

## ⚠️ Estado Actual (Fase 2A)

- **Real disponible**: 2025 (parcial)
- **Plan disponible**: 2026
- **Comparación activa**: NO (se activará automáticamente cuando exista Real 2026)
- **comparison_status**: Principalmente `NOT_COMPARABLE` o `NO_REAL_YET`

El sistema está **preparado** para que en enero 2026, cuando exista Real 2026, la comparación se active automáticamente sin cambios de código.

## 🗄️ Esquema de Base de Datos

### plan.plan_long_valid

Tabla donde se almacena el Plan válido (en universo operativo):

```sql
CREATE TABLE plan.plan_long_valid (
    id SERIAL PRIMARY KEY,
    period_type VARCHAR(10) NOT NULL,
    period VARCHAR(20) NOT NULL,
    country VARCHAR(100),
    city VARCHAR(100),
    line_of_business VARCHAR(100),
    metric VARCHAR(50) NOT NULL,
    plan_value NUMERIC NOT NULL,
    source_file_name VARCHAR(255),
    uploaded_at TIMESTAMP DEFAULT NOW(),
    file_hash VARCHAR(64),
    CONSTRAINT plan_long_valid_unique UNIQUE(period_type, period, country, city, line_of_business, metric, file_hash)
);
```

### plan.plan_long_out_of_universe

Tabla donde se almacena el Plan fuera del universo operativo.

### plan.plan_long_missing

Tabla donde se almacenan los huecos del plan (combos operativos sin plan).

**Nota:** El esquema y las tablas se crean automáticamente al primer upload del Plan.

## 🔍 Verificación de Esquema

El backend verifica automáticamente las columnas mínimas requeridas al iniciar:

- `dim.dim_park`: `park_id`, `city`, `country`, `default_line_of_business`
- `bi.real_monthly_agg`: `park_id`, `year`, `month`, `orders_completed`
- `bi.real_daily_enriched`: `park_id`, `date`, `orders_completed`

Si faltan columnas críticas y `ENVIRONMENT=dev`, el sistema falla con mensajes claros.

## 🚨 Reglas Críticas

- ❌ **NO exportar CSV, Excel, Google Sheets ni archivos descargables**
- ✅ **REAL solo desde Postgres**: `bi.real_daily_enriched`, `bi.real_monthly_agg`, `dim.dim_park`
- ✅ **PLAN desde Excel** → `plan.plan_long_*` (3 tablas)
- ✅ **NO inventar columnas**: siempre inspeccionar schema
- ✅ **Si falta revenue real**: dejar null, nunca inventar
- ✅ **Universo operativo manda**: nunca inventar ciudad/línea
- ✅ **Delta solo si comparable**: `year_real == year_plan` y existe real

## 📝 Próximas Fases

- **Fase 2B**: Cuando exista Real 2026, se activará automáticamente `COMPARABLE`
- **Fase 3**: Alertas automáticas y notificaciones
- **Fase 4**: Dashboard avanzado con visualizaciones
- **Fase 5**: Integraciones adicionales

## 🛠️ Desarrollo

### Verificación de Esquema

El sistema inspecciona automáticamente las columnas de las tablas de BD al iniciar. Si necesitas verificar qué columnas se están usando, revisa los logs al iniciar el servidor.

### Mapeo de Columnas

El mapeo semántico de columnas se define en `app/contracts/data_contract.py`:
- `trips` → `orders_completed`
- `revenue` → columna de ingresos (inspeccionada dinámicamente)

## 📞 Soporte

Para dudas o problemas:

1. Revisar los logs del backend para ver estructuras de tablas inspeccionadas
2. Verificar que las variables de entorno estén configuradas correctamente
3. Verificar que las tablas `bi.real_*` y `dim.dim_park` existan en la base de datos
4. Revisar la documentación API en `/docs` cuando el backend esté corriendo

## 📄 Licencia

Sistema interno de YEGO - Uso exclusivo del proyecto YEGO CONTROL TOWER.
