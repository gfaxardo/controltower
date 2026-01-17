# 🚀 PASO C: GUÍA DE EJECUCIÓN DE PASOS SIGUIENTES

**Fecha:** 2026-01-27  
**Estado:** Implementación completa, pendiente ejecución de migración

---

## ✅ IMPLEMENTACIÓN COMPLETADA

Toda la implementación del módulo Plan vs Real está completa:

- ✅ Migración Alembic creada: `007_create_plan_vs_real_views.py`
- ✅ Servicio backend: `plan_vs_real_service.py`
- ✅ Endpoints API: `/ops/plan-vs-real/monthly` y `/ops/plan-vs-real/alerts`
- ✅ Componente frontend: `PlanVsRealView.jsx`
- ✅ Smoke test: `smoke_test_plan_vs_real.py`
- ✅ Documentación: `PASO_C_PLAN_VS_REAL_COMPLETADO.md`

---

## 📋 PASOS SIGUIENTES A EJECUTAR

### 1. ⚙️ Ejecutar Migración Alembic

**Pre-requisitos:**
- Base de datos PostgreSQL activa
- Variables de entorno configuradas (`.env` o entorno)
- Conexión a la base de datos funcional

**Comando:**
```bash
cd backend
alembic upgrade head
```

**Qué hace:**
- Crea las 4 vistas nuevas:
  - `ops.v_real_trips_monthly_latest`
  - `ops.v_real_kpis_monthly`
  - `ops.v_plan_vs_real_monthly_latest`
  - `ops.v_plan_vs_real_alerts_monthly_latest`
- Crea índice adicional en `ops.plan_trips_monthly` para performance

**Verificación esperada:**
```
INFO  [alembic.runtime.migration] Running upgrade 006_create_plan_city_map -> 007_create_plan_vs_real_views, create_plan_vs_real_views
```

---

### 2. 🧪 Ejecutar Smoke Test

**Comando:**
```bash
# Desde el directorio raíz del proyecto
python backend/scripts/smoke_test_plan_vs_real.py
```

**Qué verifica:**
1. ✅ Existencia de `ops.v_real_trips_monthly_latest`
2. ✅ Existencia de `ops.v_real_kpis_monthly`
3. ✅ Existencia de `ops.v_plan_vs_real_monthly_latest`
4. ✅ Existencia de `ops.v_plan_vs_real_alerts_monthly_latest`
5. ✅ Estructura de columnas en `v_plan_vs_real_monthly_latest`
6. ✅ Estructura de columnas en `v_plan_vs_real_alerts_monthly_latest`
7. ✅ Valores válidos de `status_bucket` (matched, plan_only, real_only, unknown)
8. ✅ Valores válidos de `alert_level` (CRITICO, MEDIO, OK)

**Salida esperada:**
```
================================================================================
SMOKE TEST: Vistas Plan vs Real (PASO C)
================================================================================

[1/8] Verificando ops.v_real_trips_monthly_latest...
  ✓ ops.v_real_trips_monthly_latest: X,XXX registros
[2/8] Verificando ops.v_real_kpis_monthly...
  ✓ ops.v_real_kpis_monthly: X,XXX registros
...

================================================================================
RESUMEN
================================================================================
✓ Pasados: 8
⚠ Warnings: 0
✗ Fallidos: 0

✅ Todos los tests pasaron correctamente
```

---

### 3. 🔍 Verificar Vistas Manualmente (SQL)

**Pre-requisitos:**
- Acceso a PostgreSQL (psql o cliente SQL)
- Conexión a la base de datos del proyecto

**Queries de verificación:**

```sql
-- 3.1. Verificar comparación mensual (primeros 50 registros)
SELECT 
    country,
    month,
    city_norm_real,
    lob_base,
    segment,
    plan_version,
    projected_trips,
    trips_real_completed,
    gap_trips,
    gap_revenue_proxy,
    status_bucket
FROM ops.v_plan_vs_real_monthly_latest 
LIMIT 50;

-- 3.2. Verificar alertas (primeros 50 registros)
SELECT 
    country,
    month,
    city_norm_real,
    lob_base,
    segment,
    gap_trips_pct,
    gap_revenue_pct,
    alert_level
FROM ops.v_plan_vs_real_alerts_monthly_latest 
LIMIT 50;

-- 3.3. Verificar distribución de status_bucket
SELECT 
    status_bucket, 
    COUNT(*) as total
FROM ops.v_plan_vs_real_monthly_latest 
GROUP BY status_bucket
ORDER BY total DESC;

-- 3.4. Verificar distribución de alert_level
SELECT 
    alert_level, 
    COUNT(*) as total
FROM ops.v_plan_vs_real_alerts_monthly_latest 
GROUP BY alert_level
ORDER BY total DESC;

-- 3.5. Verificar que latest_version apunta correctamente
WITH latest_version AS (
    SELECT plan_version
    FROM ops.plan_trips_monthly
    GROUP BY plan_version
    ORDER BY MAX(created_at) DESC
    LIMIT 1
)
SELECT 
    p.plan_version,
    COUNT(*) as registros
FROM ops.plan_trips_monthly p
INNER JOIN latest_version lv ON p.plan_version = lv.plan_version
GROUP BY p.plan_version;
```

**Verificaciones esperadas:**
- ✅ Vistas retornan datos (o vacío si no hay plan/real cargado aún)
- ✅ `status_bucket` tiene valores válidos: `matched`, `plan_only`, `real_only`, `unknown`
- ✅ `alert_level` tiene valores válidos: `CRITICO`, `MEDIO`, `OK`
- ✅ `latest_version` apunta a la versión más reciente del plan

---

### 4. 🔧 Verificar Endpoints API

**Pre-requisitos:**
- Backend ejecutándose (FastAPI)
- Variables de entorno configuradas

**Endpoints a probar:**

#### 4.1. Comparación Plan vs Real
```bash
# GET /ops/plan-vs-real/monthly
curl "http://localhost:8000/ops/plan-vs-real/monthly?country=Colombia&month=2025-01"

# Con más filtros
curl "http://localhost:8000/ops/plan-vs-real/monthly?country=Colombia&city=bogota&lob_base=ride&segment=b2c"
```

**Respuesta esperada:**
```json
{
  "data": [
    {
      "country": "Colombia",
      "month": "2025-01-01",
      "city_norm_real": "bogota",
      "lob_base": "ride",
      "segment": "b2c",
      "plan_version": "ruta27_v1",
      "projected_trips": 1000,
      "trips_real_completed": 950,
      "gap_trips": 50,
      "status_bucket": "matched",
      ...
    }
  ],
  "total_records": 1
}
```

#### 4.2. Alertas Plan vs Real
```bash
# GET /ops/plan-vs-real/alerts
curl "http://localhost:8000/ops/plan-vs-real/alerts?country=Colombia"

# Filtrar por nivel
curl "http://localhost:8000/ops/plan-vs-real/alerts?alert_level=CRITICO"
```

**Respuesta esperada:**
```json
{
  "data": [
    {
      "country": "Colombia",
      "month": "2025-01-01",
      "city_norm_real": "bogota",
      "gap_trips_pct": -15.5,
      "gap_revenue_pct": -18.2,
      "alert_level": "CRITICO",
      ...
    }
  ],
  "total_alerts": 1,
  "by_level": {
    "CRITICO": 1,
    "MEDIO": 0,
    "OK": 0
  }
}
```

---

### 5. 🖥️ Integrar Componente Frontend

**Pre-requisitos:**
- Frontend ejecutándose (React/Vite)
- Backend API funcionando

**Opciones de integración:**

#### Opción A: Agregar como nuevo Tab en App.jsx
```jsx
// En frontend/src/App.jsx
import PlanVsRealView from './components/PlanVsRealView'

// Agregar tab o sección nueva
<Tabs>
  <Tab label="Plan vs Real">
    <PlanVsRealView filters={filters} />
  </Tab>
  ...
</Tabs>
```

#### Opción B: Crear ruta dedicada
```jsx
// En frontend/src/App.jsx o router
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import PlanVsRealView from './components/PlanVsRealView'

<Routes>
  <Route path="/plan-vs-real" element={<PlanVsRealView filters={filters} />} />
  ...
</Routes>
```

**Verificaciones:**
- ✅ Tab Comparación muestra tabla con datos
- ✅ Badges de `status_bucket` funcionan correctamente
- ✅ Tab Alertas muestra alertas ordenadas por severidad
- ✅ Filtros aplican correctamente

---

## 🐛 SOLUCIÓN DE PROBLEMAS COMUNES

### Error: "connection to server at localhost failed"
**Solución:**
- Verificar que PostgreSQL esté ejecutándose
- Verificar variables de entorno: `DATABASE_URL` o `.env`
- Verificar credenciales en `backend/app/db/connection.py`

### Error: "relation ops.v_plan_vs_real_monthly_latest does not exist"
**Solución:**
- Ejecutar migración Alembic: `alembic upgrade head`
- Verificar que la migración `007_create_plan_vs_real_views` se ejecutó correctamente
- Verificar logs de Alembic para errores

### Error: "UnicodeDecodeError: 'utf-8' codec can't decode"
**Solución:**
- Configurar encoding UTF-8 en PostgreSQL
- Verificar configuración de Alembic en `backend/alembic/env.py`
- Usar `export PGCLIENTENCODING=UTF8` (Linux/Mac) o configurar en Windows

### Vistas vacías (0 registros)
**Causa:** No hay datos de Plan o Real cargados
**Solución:**
- Verificar que existe `ops.plan_trips_monthly` con datos
- Verificar que existe `ops.mv_real_trips_monthly` con datos
- Ejecutar refresh de `mv_real_trips_monthly` si es necesario:
  ```sql
  REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly;
  ```

### Endpoints retornan 500 Error
**Solución:**
- Verificar logs del backend (FastAPI)
- Verificar que las vistas existen en la base de datos
- Verificar conexión a la base de datos desde el backend
- Revisar `backend/app/services/plan_vs_real_service.py` para errores de query

---

## ✅ CHECKLIST DE VERIFICACIÓN FINAL

- [ ] Migración Alembic ejecutada sin errores
- [ ] Smoke test pasa todos los checks (8/8)
- [ ] Vistas SQL retornan datos (o vacío válido)
- [ ] Endpoint `/ops/plan-vs-real/monthly` funciona
- [ ] Endpoint `/ops/plan-vs-real/alerts` funciona
- [ ] Componente frontend muestra datos correctamente
- [ ] Badges de `status_bucket` funcionan
- [ ] Badges de `alert_level` funcionan
- [ ] Filtros aplican correctamente
- [ ] Sin errores en consola del navegador
- [ ] Sin errores en logs del backend

---

## 📝 NOTAS ADICIONALES

### Refresh de Materialized View
Si `ops.mv_real_trips_monthly` necesita actualizarse (nuevos datos de trips_all):
```sql
-- Refresh concurrente (no bloquea)
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_trips_monthly;

-- O refresh normal (bloquea, más rápido)
REFRESH MATERIALIZED VIEW ops.mv_real_trips_monthly;
```

### Re-ingesta del Plan
Cuando se re-ingesta el CSV del plan:
- Nueva versión se crea automáticamente en `ops.plan_trips_monthly`
- Vistas latest apuntan automáticamente a la nueva versión
- **No se requiere acción manual** ✅

### Estado del Sistema
**READY_WITH_WARNINGS** significa:
- ✅ Sistema funcional y operativo
- ⚠️ Puede haber warnings/info (plan_only, real_only) - esto es normal
- ✅ Alertas solo para `matched` (accionable)

---

## 🎯 PRÓXIMOS PASOS DESPUÉS DE EJECUTAR

Una vez completados todos los pasos anteriores:

1. ✅ **Sistema operativo:** Control Tower puede operar día a día, semana a semana, mes a mes
2. ✅ **Re-ingesta automática:** Cada nuevo CSV del plan recalcula todo sin intervención
3. ✅ **Alertas accionables:** Solo matched tiene alertas, resto es info
4. ✅ **No bloqueante:** Warnings/info no detienen el sistema

**El módulo Plan vs Real está listo para producción.** 🚀
