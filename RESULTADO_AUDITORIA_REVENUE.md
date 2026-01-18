# RESULTADO AUDITORÍA: Revenue Plan Bug

## ✅ HALLAZGOS

### PASO 1 - Tabla RAW Identificada
- **Tabla**: `ops.plan_trips_monthly`
- **Schema**: `ops`

### PASO 2 - Columnas Verificadas
- ✅ `projected_revenue` existe (numeric)
- ✅ `projected_ticket` existe (numeric) 
- ✅ `projected_trips` existe (integer)

### PASO 3 - Prueba de Fuego
**Resultados:**
- `revenue_from_file`: 8,473,034.60
- `gmv_inferred`: 3,770.73

⚠️ **PROBLEMA DETECTADO**: 
- El valor `8,473,034.60` es MUY ALTO (parece GMV, no revenue)
- El valor esperado debería ser ~263,428.97

**Interpretación:**
- Los datos en `projected_revenue` son GMV (trips × ticket)
- NO son el revenue_plan del Excel

### PASO 4 - Vista Identificada
- **Vista principal**: `ops.v_plan_trips_monthly_latest`
- **Vista secundaria**: `ops.v_plan_kpis_monthly_latest`

### PASO 5 - Definición de Vista
- La vista usa `p.projected_revenue` directamente de la tabla
- NO calcula trips × ticket en la vista misma
- **PERO**: Los datos en `projected_revenue` son incorrectos (GMV en lugar de revenue)

### PASO 6 - Estado de projected_revenue
- ✅ `projected_revenue` NO es GENERATED (es campo normal)
- ✅ La migración 009 ya está aplicada o no era necesaria

## 🐛 CAUSA RAÍZ IDENTIFICADA

**El bug NO está en la vista, está en los DATOS.**

`projected_revenue` contiene GMV (trips × ticket) en lugar del valor real `revenue_plan` del Excel.

### Posibles causas:
1. La ingesta nunca leyó `revenue_plan` del CSV/Excel
2. Los datos se cargaron antes de implementar el fix
3. El CSV no tiene columna `revenue_plan`

## 🔧 SOLUCIÓN

### Opción A: Reingestar con revenue_plan (RECOMENDADO)
1. Verificar que el CSV/Excel tenga columna `revenue_plan`
2. Reingestar el Plan completo con el script actualizado
3. El script `ingest_plan_from_csv_ruta27.py` ahora lee `revenue_plan` y lo guarda en `projected_revenue`

### Opción B: Actualizar datos existentes
Si no se puede reingestar, actualizar `projected_revenue` manualmente con valores correctos.

## ✅ PASOS SIGUIENTES

1. **Verificar CSV/Excel de origen:**
   - ¿Tiene columna `revenue_plan`?
   - ¿Los valores son ~263K o ~8M?

2. **Si el CSV tiene `revenue_plan` correcto:**
   - Reingestar usando `/plan/upload_ruta27` con `replace_all=true`

3. **Verificar después de reingesta:**
   ```sql
   SELECT 
     SUM(projected_revenue) as revenue_total,
     SUM(projected_trips * projected_ticket) as gmv_total
   FROM ops.plan_trips_monthly
   WHERE EXTRACT(YEAR FROM month) = 2026
     AND EXTRACT(MONTH FROM month) = 1
     AND country = 'PE';
   ```
   
   **Resultado esperado:**
   - `revenue_total` ≈ 263,428.97
   - `gmv_total` ≈ 8,473,034.60
   - Deben ser diferentes

## 📋 CONCLUSIÓN

- ✅ La estructura de BD está correcta (`projected_revenue` no es GENERATED)
- ✅ La vista está correcta (usa `projected_revenue` directamente)
- ❌ Los DATOS están incorrectos (contienen GMV en lugar de revenue)
- 🔧 **Acción requerida**: Reingestar Plan con CSV que tenga `revenue_plan`
