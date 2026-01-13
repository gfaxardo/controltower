# Sistema de Mapeo Territorial Canónico

## Resumen

Sistema canónico de mapeo territorial por `park_id` con trazabilidad, auditabilidad y KPIs de calidad.

### Componentes Implementados

1. **Base de Datos (Migración)**
   - Schema `ops` (si no existe)
   - Tabla staging: `ops.stg_park_territory`
   - Función merge: `ops.merge_park_territory_from_staging()`
   - Vistas de auditoría:
     - `ops.v_trip_territory_canonical`
     - `ops.v_territory_mapping_quality_kpis` (totales)
     - `ops.v_territory_mapping_quality_kpis_weekly` (semanales)

2. **Scripts**
   - `backend/scripts/export_parks_from_trips.sql` - Exporta parks desde trips_all
   - `backend/scripts/load_park_territory_csv.py` - Carga datos territoriales desde CSV

3. **API Endpoints**
   - `GET /ops/territory-quality/kpis?granularity=total|weekly`
   - `GET /ops/territory-quality/unmapped-parks?limit=50`

4. **Servicios**
   - `backend/app/services/territory_quality_service.py`

## Instrucciones de Ejecución

### 1. Ejecutar Migración

**Opción A: Alembic (si funciona)**
```bash
cd backend
alembic upgrade head
```

**Opción B: Script directo (recomendado si Alembic tiene problemas)**
```bash
cd backend
python scripts/run_territory_migration_direct.py
```

### 2. Exportar Parks desde trips_all

Para identificar qué parks necesitan mapeo territorial:

```bash
cd backend
psql -h <host> -U <user> -d yego_integral -f scripts/export_parks_from_trips.sql > parks_needing_mapping.csv
```

O desde Python:
```python
python -c "
import sys; sys.path.insert(0, 'backend')
from app.db.connection import get_db, init_db_pool
init_db_pool()
with get_db() as conn:
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.park_id, COUNT(*) as trips_count
        FROM public.trips_all t
        WHERE t.park_id IS NOT NULL
        GROUP BY t.park_id
        ORDER BY trips_count DESC
    ''')
    for row in cursor.fetchall():
        print(f'{row[0]},{row[1]}')
"
```

### 3. Preparar CSV de Mapeo Territorial

Crear archivo CSV con formato: `park_id,country,city`

Ejemplo `parks_territory.csv`:
```csv
park_id,country,city
08e20910d81d42658d4334d3f6d10ac0,Peru,Lima
abc123def456,Colombia,Bogota
xyz789uvw012,Mexico,CDMX
```

### 4. Cargar Datos Territoriales

**Modo dry-run (recomendado primero):**
```bash
cd backend
python scripts/load_park_territory_csv.py --csv parks_territory.csv --dry-run
```

**Carga real:**
```bash
cd backend
python scripts/load_park_territory_csv.py --csv parks_territory.csv --loaded-by "usuario@ejemplo.com"
```

El script:
1. Valida datos (duplicados, campos vacíos)
2. Carga a `ops.stg_park_territory`
3. Ejecuta `ops.merge_park_territory_from_staging()`
4. Muestra resumen: inserted, updated, rejected

### 5. Validar Mapeo Territorial

Ejecutar queries de validación:

```bash
cd backend
psql -h <host> -U <user> -d yego_integral -f scripts/validate_territory_mapping.sql
```

### 6. Verificar API Endpoints

**KPIs totales:**
```bash
curl http://localhost:8000/ops/territory-quality/kpis?granularity=total
```

**KPIs semanales:**
```bash
curl http://localhost:8000/ops/territory-quality/kpis?granularity=weekly
```

**Parks unmapped:**
```bash
curl http://localhost:8000/ops/territory-quality/unmapped-parks?limit=50
```

## Estructura de Datos

### Tabla Staging: `ops.stg_park_territory`
- `park_id` (text, NOT NULL)
- `country` (text)
- `city` (text)
- `loaded_at` (timestamptz, default now())
- `loaded_by` (text)

### Función: `ops.merge_park_territory_from_staging()`
- Valida: park_id no nulo, country/city no nulos
- INSERT: Si park_id no existe en `dim.dim_park`
- UPDATE: Si park_id existe y country/city cambian
- Retorna: (inserted_count, updated_count, rejected_count)

### Vista: `ops.v_trip_territory_canonical`
- `trip_id` (desde trips_all.id)
- `trip_date` (desde trips_all.fecha_inicio_viaje)
- `park_id`
- `country`, `city` (desde dim.dim_park)
- `is_territory_unknown` (flag: TRUE si dim_park no existe OR country/city NULL)

### Vista: `ops.v_territory_mapping_quality_kpis`
- `total_trips`
- `pct_territory_resolved` (%)
- `pct_territory_unknown` (%)
- `parks_in_trips` (distinct)
- `parks_unmapped` (distinct, en trips_all pero no en dim_park)
- `parks_with_null_country_city` (distinct)

### Vista: `ops.v_territory_mapping_quality_kpis_weekly`
- `week_start` (date)
- Mismos KPIs que totales, agrupados por semana

## Validaciones Obligatorias

1. **Conteo de trips_unknown y top park_id causantes:**
   ```sql
   SELECT * FROM ops.v_territory_mapping_quality_kpis;
   SELECT park_id, COUNT(*) as trips_count
   FROM ops.v_trip_territory_canonical
   WHERE is_territory_unknown = true
   GROUP BY park_id
   ORDER BY trips_count DESC
   LIMIT 20;
   ```

2. **Conteo parks_unmapped:**
   ```sql
   SELECT parks_unmapped FROM ops.v_territory_mapping_quality_kpis;
   ```

3. **Verificar que weekly KPIs suman coherente:**
   ```sql
   SELECT 
       (SELECT total_trips FROM ops.v_territory_mapping_quality_kpis) as total,
       (SELECT SUM(total_trips) FROM ops.v_territory_mapping_quality_kpis_weekly) as sum_weekly;
   ```

## Notas Importantes

- **NO inventar country/city desde trips_all**: Solo usar `dim.dim_park` como fuente canónica
- **Fuente de evidencia**: `trips_all.park_id` sirve solo para auditar cobertura
- **Si park_id aparece en trips_all y no existe en dim_park**: → `territory_unknown` (KPI rojo)
- **Si country o city es NULL**: → `territory_unknown` (KPI rojo)
- **Todo trazable y auditable**: staging table registra `loaded_at` y `loaded_by`

## Próximos Pasos (UI MVP)

Para implementar UI MVP, agregar:
1. Panel "Territory Mapping Quality" con KPIs
2. Badges `is_territory_unknown` en tablas de trips
3. Llamadas a endpoints `/ops/territory-quality/*`
