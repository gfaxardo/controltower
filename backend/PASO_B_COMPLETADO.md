# PASO B - PLAN: COMPLETADO

## ✅ Ejecutado

### 1. Migración 004 - Ajustes para park_id NULL y city_norm
- ✅ Agregada columna `city_norm` para normalización (sin romper city original)
- ✅ Ajustado UNIQUE constraint para manejar `park_id` NULL usando `COALESCE(park_id, '__NA__')`
- ✅ Migración ejecutada exitosamente

### 2. Vistas "Latest" Creadas
- ✅ `ops.v_plan_versions` - Lista de versiones con estadísticas
- ✅ `ops.v_plan_trips_monthly_latest` - Última versión de trips mensual
- ✅ `ops.v_plan_kpis_monthly_latest` - Última versión de KPIs

### 3. Script de Ingesta Adaptado
- ✅ `ingest_plan_from_csv_ruta27.py` - Adaptado para formato real del CSV
- ✅ Mapeo de columnas: `trips_plan` → `projected_trips`, `active_drivers_plan` → `projected_drivers`, `avg_ticket_plan` → `projected_ticket`
- ✅ Manejo automático de versiones duplicadas (agrega sufijo numérico)
- ✅ Validaciones: segment (b2b/b2c), year/month válidos
- ✅ Conversión float → int para trips y drivers (round down)

## 📋 Pasos para Completar Ingesta

### Paso 1: Ejecutar Ingesta
```bash
cd backend
python scripts/ingest_plan_from_csv_ruta27.py "c:\Users\Pc\Downloads\proyeccion simplificada - Hoja 2.csv" ruta27_v2026_01_16_a
```

**Nota:** Si la versión ya existe, se creará automáticamente `ruta27_v2026_01_16_a2`, `ruta27_v2026_01_16_a3`, etc.

### Paso 2: Ejecutar Validaciones
```bash
python scripts/validate_plan_post_ingestion.py <plan_version_final>
```

Reemplaza `<plan_version_final>` con la versión que se usó después de la ingesta.

### Paso 3: Generar Reporte Final
```bash
python scripts/report_plan_ready_for_comparison.py <plan_version_final>
```

### Paso 4: Verificar Ingesta
```bash
python scripts/verify_plan_ingestion_complete.py <plan_version_final>
```

O sin versión para usar la última:
```bash
python scripts/verify_plan_ingestion_complete.py
```

## 📊 Queries de Verificación

### Conteo por city/lob/segment/month
```sql
SELECT 
    city,
    lob_base,
    segment,
    month,
    COUNT(*) as count,
    SUM(projected_trips) as trips
FROM ops.plan_trips_monthly
WHERE plan_version = 'ruta27_v2026_01_16_a'
GROUP BY city, lob_base, segment, month
ORDER BY trips DESC
LIMIT 20;
```

### Top 10 Validaciones
```sql
SELECT 
    validation_type,
    severity,
    country,
    city,
    lob_base,
    month,
    row_count
FROM ops.plan_validation_results
WHERE plan_version = 'ruta27_v2026_01_16_a'
ORDER BY 
    CASE severity WHEN 'error' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
    row_count DESC
LIMIT 10;
```

### Verificar Vista Latest
```sql
SELECT * 
FROM ops.v_plan_kpis_monthly_latest 
LIMIT 20;
```

## 🎯 Estructura Final

### Tablas
- `ops.plan_trips_monthly` - Tabla canónica (versionada, append-only)
  - `city_norm` agregada para matching normalizado
  - `park_id` puede ser NULL
  - UNIQUE constraint maneja `park_id` NULL correctamente

### Vistas
- `ops.v_plan_versions` - Lista de versiones disponibles
- `ops.v_plan_trips_monthly_latest` - Última versión (sin hardcode)
- `ops.v_plan_kpis_monthly_latest` - KPIs de última versión (sin hardcode)

## ⚠️ Notas Importantes

1. **Normalización de City**: `city_norm` se calcula como `lower(trim(city))` (sin unaccent por ahora)
2. **park_id NULL**: El sistema soporta completamente `park_id` vacío mediante el constraint UNIQUE con `COALESCE(park_id, '__NA__')`
3. **Versionado Automático**: Si la versión ya existe, se agrega sufijo numérico automáticamente (no se hace UPDATE)
4. **Vistas Latest**: Las vistas latest siempre apuntan a la versión más reciente por `created_at`, evitando hardcode

## 🔄 Flujo Completo

```
CSV Ruta 27 → ingest_plan_from_csv_ruta27.py → ops.plan_trips_monthly
                                                   ↓
                        ┌──────────────────────────┼──────────────────────────┐
                        ↓                          ↓                          ↓
            validate_plan_post_    report_plan_ready_    verify_plan_ingestion_
            ingestion.py            comparison.py         complete.py
                        ↓                          ↓                          ↓
            ops.plan_validation_    Reporte Final         Queries de Verificación
            results
```

## ✅ Checklist Final

- [x] Migración 004 ejecutada (park_id NULL, city_norm)
- [x] Vistas latest creadas
- [x] Script de ingesta adaptado al formato real
- [ ] Ingesta ejecutada con CSV real
- [ ] Validaciones ejecutadas
- [ ] Reporte final generado
- [ ] Verificación completa ejecutada
