# PASO B: PLAN TOLERANTE, RECALCULABLE Y NO BLOQUEANTE

## Objetivo General
Consolidar definitivamente el PASO B (PLAN), asegurando que:

- ✅ El plan **nunca bloquea** la operación por incongruencias
- ✅ Toda incongruencia se convierte en **warning o info**
- ✅ El plan es **append-only y versionado**
- ✅ Reingestar una versión nueva **recalcula todo automáticamente**
- ✅ Control Tower puede **comparar Plan vs Real sin fricción**

## Principio Operativo Clave

**EL PLAN NUNCA BLOQUEA.**

Si hay dudas, inconsistencias o faltantes:
- ⚠️ Se marca como **warning** o **info**
- ✅ Se permite continuar
- 🔄 El usuario decide luego si corrige y reingesta

## Reglas Definitivas

### 1. Regla de Aplicabilidad

**Si `is_applicable = FALSE`:**
- ❌ NO se ingesta la fila
- ❌ NO genera warning
- ❌ NO participa en KPIs

**Si `is_applicable = TRUE` o `NULL`:**
- ✅ Se ingesta
- ⚠️ Puede generar warnings

**Implementación:** `backend/scripts/ingest_plan_from_csv_ruta27.py` (líneas 106-114)

### 2. Regla de Métricas Inválidas

Para filas ingestadas:
- `projected_trips <= 0` → **warning** `invalid_metrics`
- `projected_drivers IS NULL` → **warning** `invalid_metrics`
- `projected_ticket <= 0` → **warning** `invalid_metrics`

⚠️ **Nunca error bloqueante**

### 3. Regla de Matching Territorial

Matching Plan vs Real usa en este orden:
1. `plan_city_resolved_norm` (si existe)
2. `city_norm` (fallback)
3. `city_mismatch` → **warning** (no bloquea)

### 4. Severidades Finales

| Tipo | Severidad | Bloquea |
|------|-----------|---------|
| `duplicate_plan` | **error** | ✅ Sí |
| `invalid_segment` | **error** | ✅ Sí |
| `invalid_month` | **error** | ✅ Sí |
| `invalid_metrics` | **warning** | ❌ No |
| `city_mismatch` | **warning** | ❌ No |
| `orphan_plan` | **info/warning** | ❌ No |
| `orphan_real` | **info** | ❌ No |

**Reglas especiales:**
- `orphan_plan` es **info** para meses futuros (normal)
- `orphan_plan` es **warning** para meses pasados/presentes
- `orphan_real` es siempre **info** (informativo para gaps del plan)

### 5. Re-ingesta Segura

Al ejecutar:
```bash
python scripts/ingest_plan_from_csv_ruta27.py <csv> <nueva_version>
```

**Se cumple automáticamente:**
- ✅ Nueva `plan_version` (no modifica historia)
- ✅ Vistas `latest` apuntan automáticamente a la última versión
- ✅ KPIs se recalculan sin pasos manuales

**Vistas latest (auto-actualizables):**
- `ops.v_plan_versions` - Lista de versiones con metadata
- `ops.v_plan_trips_monthly_latest` - Última versión de trips
- `ops.v_plan_kpis_monthly_latest` - Última versión de KPIs

**Lógica:** Usan `ORDER BY MAX(created_at) DESC LIMIT 1` para siempre obtener la última versión.

### 6. Contrato para Control Tower

**Reglas que Control Tower puede asumir:**

1. **El PLAN siempre existe**
   - Puede tener warnings
   - Nunca está "roto"

2. **Comparar siempre contra vistas latest:**
   ```sql
   SELECT * FROM ops.v_plan_trips_monthly_latest;
   SELECT * FROM ops.v_plan_kpis_monthly_latest;
   ```

3. **REAL siempre desde:**
   ```sql
   SELECT * FROM ops.mv_real_trips_monthly;
   ```

4. **Campos garantizados para comparación:**

   **Plan (por grano: country, city, lob_base, segment, month):**
   - `projected_trips`
   - `projected_drivers`
   - `projected_ticket`
   - `projected_revenue` (calculado: `projected_trips * projected_ticket`)

   **Real (por grano: country, city, lob_base, segment, month):**
   - `trips_real_completed`
   - `active_drivers_real`
   - `avg_ticket_real`
   - `revenue_real_proxy` (calculado: `SUM(precio_yango_pro)`)

## Checklist de Auto-Verificación

Ejecutar para verificar que todo funciona:

```bash
# Verificación completa
python scripts/verify_plan_tolerance_final.py [plan_version]

# Si no se especifica plan_version, usa la última
```

**Verificaciones incluidas:**
- ✓ Reglas de aplicabilidad
- ✓ Severidades correctas
- ✓ Vistas latest funcionando
- ✓ Agregado Real disponible
- ✓ Campos garantizados presentes
- ✓ Estado final del plan (READY_OK / READY_WITH_WARNINGS)

**Esperado:**
- ✅ 0 errores (o errores justificados: duplicate_plan, invalid_segment, invalid_month)
- ⚠️ Warnings permitidos (invalid_metrics, city_mismatch)
- ℹ️ Info normal (orphan_plan, orphan_real)

## Flujo Operativo Completo

### Re-ingesta de Plan

```bash
# 1. Ingestar nueva versión
python scripts/ingest_plan_from_csv_ruta27.py ruta27.csv ruta27_v2026_01_16_b

# 2. Validar (opcional pero recomendado)
python scripts/validate_plan_post_ingestion.py ruta27_v2026_01_16_b

# 3. Reporte final
python scripts/report_plan_ready_for_comparison.py ruta27_v2026_01_16_b

# 4. Verificación completa
python scripts/verify_plan_tolerance_final.py ruta27_v2026_01_16_b
```

### Uso desde Control Tower

```sql
-- Obtener último plan
SELECT * FROM ops.v_plan_kpis_monthly_latest
WHERE country = 'CO'
AND city = 'Bogota'
AND lob_base = 'Delivery'
AND segment = 'b2c';

-- Comparar con Real
SELECT 
    p.month,
    p.projected_trips,
    r.trips_real_completed,
    p.projected_trips - COALESCE(r.trips_real_completed, 0) as delta_trips
FROM ops.v_plan_trips_monthly_latest p
LEFT JOIN ops.mv_real_trips_monthly r
    ON p.month = r.month
    AND COALESCE(p.plan_city_resolved_norm, p.city_norm) = r.city_norm
    AND p.lob_base = r.lob_base
    AND p.segment = r.segment
WHERE p.country = 'CO'
AND p.city = 'Bogota'
ORDER BY p.month;
```

## Archivos Clave

### Scripts de Ingesta y Validación
- `backend/scripts/ingest_plan_from_csv_ruta27.py` - Ingesta con soporte `is_applicable`
- `backend/scripts/validate_plan_post_ingestion.py` - Validaciones no bloqueantes
- `backend/scripts/report_plan_ready_for_comparison.py` - Reporte final

### Scripts de Verificación
- `backend/scripts/verify_plan_tolerance_final.py` - Auto-verificación completa
- `backend/scripts/diagnose_plan_warnings.py` - Diagnóstico de warnings

### SQL de Validaciones
- `backend/scripts/sql/validate_plan_trips_monthly_optimized.sql` - Validaciones SQL

### Migraciones
- `backend/alembic/versions/003_create_plan_trips_monthly_system.py` - Sistema base
- `backend/alembic/versions/004_fix_plan_trips_nullable_park_id_and_city_norm.py` - city_norm
- `backend/alembic/versions/005_create_real_trips_monthly_aggregate.py` - Agregado Real
- `backend/alembic/versions/006_create_plan_city_map.py` - City mapping

## Principios Cumplidos

- ✅ **Plan y Real no se mezclan**: Solo se comparan, nunca se modifican datos de Real
- ✅ **Plan es append-only**: Nunca UPDATE/DELETE, solo INSERT con nueva versión
- ✅ **Tolerancia total**: Incongruencias son warnings/info, no errores bloqueantes
- ✅ **Recalculable**: Re-ingesta crea nueva versión que automáticamente se convierte en "latest"
- ✅ **Auditable**: `created_at`, `plan_version` en cada registro
- ✅ **Sin lógica mágica**: Todo explícito en SQL y vistas

## Estado Final

✅ **PLAN TOLERANTE, RECALCULABLE Y NO BLOQUEANTE**

El sistema está consolidado y listo para:
- Iteración sin fricción
- Re-ingesta cuantas veces sea necesario
- Sin bloqueos por incongruencias menores
- Control Tower siempre tiene una versión válida
- Ruta 27 puede evolucionar sin miedo

---

**Última actualización:** 2026-01-16  
**Verificación:** Ejecutar `python scripts/verify_plan_tolerance_final.py`
