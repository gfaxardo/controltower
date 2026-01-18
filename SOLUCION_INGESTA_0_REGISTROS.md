# SOLUCIÓN: Ingesta con 0 Registros

## 🔍 DIAGNÓSTICO COMPLETADO

**Estado:** La tabla `ops.plan_trips_monthly` está **completamente vacía** después de la ingesta.

**Causa más probable:** Las filas del CSV están siendo rechazadas por validaciones o hay errores silenciosos.

## 🔧 FIX APLICADO

✅ **Corregido contador de registros insertados:**
- Ahora solo cuenta si `cursor.rowcount > 0`
- Evita contar cuando `ON CONFLICT DO NOTHING` no inserta

## 📋 PASOS PARA RESOLVER

### PASO 1: Verificar CSV Localmente

Ejecutar script de prueba:
```powershell
cd c:\cursor\controltower\controltower\backend
python scripts\test_csv_ingestion.py "<ruta_completa_al_csv>"
```

Esto mostrará:
- ✅ Columnas presentes
- ✅ Formato de primeras filas
- ❌ Errores de validación detectados

### PASO 2: Verificar Logs del Backend

**En la terminal donde corre el backend (uvicorn), buscar:**
- Línea que dice "INGESTA COMPLETADA"
- Número de "Registros insertados"
- Lista de "Errores encontrados"

**Ejemplo de salida esperada:**
```
INGESTA COMPLETADA
Plan Version: ruta27_v2026_01_17
Registros insertados: 0

Errores encontrados: 150
  - Fila 2: segment inválido 'xxx'
  - Fila 3: year/month inválido (2025/13)
  ...
```

### PASO 3: Validaciones Comunes que Rechazan Filas

El script rechaza filas si:

1. **`segment` inválido:**
   - ❌ Valores como: 'B2B', 'B2C' (mayúsculas)
   - ❌ Valores como: 'b2b ', ' b2c' (con espacios)
   - ✅ Solo acepta: 'b2b' o 'b2c' (exactamente, minúsculas)

2. **`year`/`month` inválido:**
   - ❌ `year` < 2000 o > 2100
   - ❌ `month` < 1 o > 12
   - ❌ Valores no numéricos

3. **`is_applicable` = FALSE:**
   - Si el CSV tiene columna `is_applicable` con valor 'FALSE', '0', 'NO', etc., la fila se salta

### PASO 4: Verificar Formato del CSV

El CSV debe tener este formato (ejemplo):

```csv
country,city,lob_base,segment,year,month,trips_plan,active_drivers_plan,avg_ticket_plan,revenue_plan
PE,Lima,Delivery,b2b,2026,1,1000,50,25.50,263428.97
CO,Bogotá,Delivery,b2c,2026,1,2000,100,30.00,600000.00
```

**IMPORTANTE:**
- `segment` debe ser **minúsculas**: 'b2b' o 'b2c' (NO 'B2B', 'B2C')
- `year` y `month` deben ser **números** (NO texto)
- No debe haber espacios extra antes/después de valores

### PASO 5: Si el CSV Está Correcto pero Sigue Fallando

**Verificar restricción UNIQUE:**

La tabla tiene un constraint UNIQUE en:
- `(plan_version, country, city, park_id, lob_base, segment, month)`

Si hay duplicados exactos, solo se inserta el primero y los demás se ignoran (pero no debería dar 0 si hay al menos una fila única).

## 🎯 ACCIÓN INMEDIATA

**1. Revisar la consola del backend** donde se ejecutó la ingesta para ver errores detallados.

**2. Si no hay errores en consola**, ejecutar:
```powershell
cd c:\cursor\controltower\controltower\backend
python scripts\test_csv_ingestion.py "<ruta_al_csv_subido>"
```

**3. Si el CSV tiene problemas de formato**, corregirlo y reingestar.

## 📝 NOTA IMPORTANTE

El fix del contador está aplicado, pero **si `inserted_count = 0`, significa que ninguna fila pasó las validaciones**. Los errores se están capturando en la lista `errors` pero pueden no mostrarse si el endpoint no los retorna.

**Solución temporal:** Revisar directamente la consola del backend donde corre uvicorn para ver los prints del script.
