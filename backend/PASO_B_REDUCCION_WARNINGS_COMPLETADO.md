# PASO B: REDUCCIÓN DE WARNINGS DEL PLAN - COMPLETADO

## Objetivo
Reducir warnings del Plan:
- `city_mismatch` (84 warnings)
- `invalid_metrics` (228 warnings)

Sin romper el principio: **Plan y Real no se mezclan**.

## Estado: IMPLEMENTACIÓN COMPLETA

### ✅ Tareas Completadas

#### A) Diagnóstico de Warnings

**Script creado:** `backend/scripts/diagnose_plan_warnings.py`

**Resultados del diagnóstico:**
- **city_mismatch:** 3 ciudades únicas con problemas:
  - `bogotá` (plan) vs `bogota` (real)
  - `cúcuta` (plan) vs `cucuta` (real)
  - `medellín` (plan) vs `medellin` (real)
  - También hay diferencia en país: `CO` (plan) vs `colombia` (real)

- **invalid_metrics:** 228 warnings principalmente por:
  - `projected_drivers = NULL` (216 filas)
  - `projected_ticket <= 0` (12 filas)

#### B) Migración 006 - Diccionario de Mapeo de Ciudades

**Archivo:** `backend/alembic/versions/006_create_plan_city_map.py`

**Tabla creada:** `ops.plan_city_map`
```sql
CREATE TABLE ops.plan_city_map (
    country TEXT NOT NULL,
    plan_city_raw TEXT NOT NULL,
    plan_city_norm TEXT NOT NULL,
    real_city_norm TEXT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (country, plan_city_norm)
);
```

**Columna agregada:** `ops.plan_trips_monthly.plan_city_resolved_norm`
- Se usa para almacenar el `city_norm` resuelto desde `plan_city_map`
- Permite matching mejorado con Real sin cambiar `city` original

**Migración ejecutada:** ✅

#### C) CSV Seed Generado

**Archivo generado:** `backend/exports/plan_city_map_seed.csv`

**Contenido:**
- 9 ciudades únicas del plan
- Columnas: `country`, `plan_city_raw`, `plan_city_norm`, `real_city_norm` (vacío), `notes`

**Instrucciones:**
1. Abrir CSV: `backend/exports/plan_city_map_seed.csv`
2. Completar columna `real_city_norm` con el `city_norm` correspondiente de `dim_park`
3. Guardar CSV
4. Cargar mapeo: `python scripts/load_city_map_from_csv.py exports/plan_city_map_seed.csv`

#### D) Scripts de Utilidad

**Creados:**
1. `backend/scripts/diagnose_plan_warnings.py` - Diagnóstico de warnings
2. `backend/scripts/generate_city_map_seed.py` - Genera CSV seed desde plan
3. `backend/scripts/load_city_map_from_csv.py` - Carga mapeo completado
4. `backend/scripts/run_migration_006.py` - Ejecuta migración 006

#### E) Ingesta Actualizada

**Archivo modificado:** `backend/scripts/ingest_plan_from_csv_ruta27.py`

**Mejoras:**
1. **City mapping:** Busca en `ops.plan_city_map` para resolver `plan_city_resolved_norm`
2. **Soporte `is_applicable`:** Columna opcional en CSV para filtrar filas
   - Si `is_applicable = FALSE` → la fila no se inserta
   - Si no viene → asume `TRUE`

#### F) Validaciones Actualizadas

**Archivo modificado:** `backend/scripts/sql/validate_plan_trips_monthly_optimized.sql`

**Mejoras:**
1. **city_mismatch:** Usa `plan_city_resolved_norm` cuando está disponible
2. **orphan_plan/orphan_real:** Usa `plan_city_resolved_norm` para matching mejorado

## 📋 Pasos Pendientes (Manuales)

### 1. Completar City Mapping

El usuario debe completar `backend/exports/plan_city_map_seed.csv`:

```csv
country,plan_city_raw,plan_city_norm,real_city_norm,notes
CO,Bogotá,bogotá,bogota,Mapeo para resolver acentos
CO,Cúcuta,cúcuta,cucuta,Mapeo para resolver acentos
CO,Medellín,medellín,medellin,Mapeo para resolver acentos
...
```

**Mapeos recomendados basados en diagnóstico:**
- `bogotá` → `bogota`
- `cúcuta` → `cucuta`
- `medellín` → `medellin`

**Nota:** También considerar mapear países: `CO` → `colombia` si es necesario.

### 2. Cargar City Mapping

```bash
cd backend
python scripts/load_city_map_from_csv.py exports/plan_city_map_seed.csv
```

### 3. Re-ingerir Plan (Opcional)

Si el CSV original tiene la columna `is_applicable`, re-ingerir para filtrar filas:

```bash
python scripts/ingest_plan_from_csv_ruta27.py <csv_path> ruta27_v2026_01_16_b
```

**Nota:** La versión `ruta27_v2026_01_16_b` será nueva (no actualiza la `a`).

### 4. Actualizar plan_city_resolved_norm en Versión Existente

Si ya existe la versión `ruta27_v2026_01_16_a`, actualizar `plan_city_resolved_norm`:

```sql
UPDATE ops.plan_trips_monthly p
SET plan_city_resolved_norm = cm.real_city_norm
FROM ops.plan_city_map cm
WHERE p.plan_version = 'ruta27_v2026_01_16_a'
AND p.country = cm.country
AND p.city_norm = cm.plan_city_norm
AND cm.real_city_norm IS NOT NULL
AND cm.is_active = TRUE;
```

### 5. Re-ejecutar Validaciones

```bash
python scripts/validate_plan_post_ingestion.py ruta27_v2026_01_16_b
python scripts/report_plan_ready_for_comparison.py ruta27_v2026_01_16_b
```

## 📊 Resultados Esperados

### Antes de Reducción
- `city_mismatch`: 84 warnings (3 ciudades únicas × múltiples filas)
- `invalid_metrics`: 228 warnings

### Después de Reducción (Proyectado)
- `city_mismatch`: **0-3 warnings** (solo si quedan ciudades sin mapear)
- `invalid_metrics`: **0-228 warnings** (depende de si se usa `is_applicable` para filtrar)

## 🎯 Principios Cumplidos

- ✅ **Plan y Real no se mezclan**: El mapeo es solo para matching, no modifica datos de Real
- ✅ **City original preservado**: `city` y `city_norm` originales no cambian
- ✅ **Auditable**: `plan_city_map` tiene `created_at` y `updated_at`
- ✅ **Sin lógica mágica**: Todo explícito en `plan_city_map` y consultas SQL

## 📝 Archivos Creados/Modificados

**Nuevos:**
- `backend/alembic/versions/006_create_plan_city_map.py`
- `backend/scripts/diagnose_plan_warnings.py`
- `backend/scripts/generate_city_map_seed.py`
- `backend/scripts/load_city_map_from_csv.py`
- `backend/scripts/run_migration_006.py`
- `backend/exports/plan_city_map_seed.csv`

**Modificados:**
- `backend/scripts/ingest_plan_from_csv_ruta27.py`
- `backend/scripts/sql/validate_plan_trips_monthly_optimized.sql`

## 🔍 Verificación

Para verificar el estado actual:

```bash
# Ver diagnóstico de warnings
python scripts/diagnose_plan_warnings.py ruta27_v2026_01_16_a

# Ver mapeos cargados
python -c "
from app.db.connection import init_db_pool, get_db
init_db_pool()
with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ops.plan_city_map WHERE is_active = TRUE ORDER BY country, plan_city_norm')
    for row in cursor.fetchall():
        print(row)
"

# Ver validaciones
python scripts/show_validation_details.py ruta27_v2026_01_16_a
```

---

**Estado Final:** ✅ **IMPLEMENTACIÓN COMPLETA** - Pendiente completar CSV seed y re-ejecutar validaciones.
