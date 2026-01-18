# Diagnóstico: Ingesta con 0 Registros

## 🔍 PROBLEMA DETECTADO

Después de reingestar con `replace_all=true`, la tabla `ops.plan_trips_monthly` está **completamente vacía** (0 versiones, 0 registros).

## ⚠️ CAUSAS POSIBLES

### 1. CSV Vacío o Solo Headers
- El archivo CSV no tiene filas de datos
- Solo tiene la fila de encabezados

### 2. Validaciones Rechazan Todas las Filas
El script rechaza filas si:
- ❌ `segment` no es 'b2b' o 'b2c'
- ❌ `year` < 2000 o > 2100
- ❌ `month` < 1 o > 12
- ❌ `is_applicable` = 'FALSE' o '0' (si existe la columna)

### 3. Errores Silenciosos
- Errores de conversión de tipos (int/float)
- Errores de formato de fecha
- Errores que se capturan pero no se reportan en la respuesta del endpoint

### 4. Bug en Contador
- `inserted_count` se incrementaba incluso cuando `ON CONFLICT DO NOTHING` no insertaba
- **FIX APLICADO**: Ahora solo cuenta si `cursor.rowcount > 0`

## 🔧 VERIFICACIONES NECESARIAS

### 1. Verificar Contenido del CSV

Ejecutar:
```bash
cd backend
python scripts/test_csv_ingestion.py <ruta_al_csv>
```

Esto mostrará:
- Columnas presentes
- Formato de primeras filas
- Errores de validación

### 2. Verificar Logs del Backend

Revisar la consola del servidor backend donde se ejecutó la ingesta. Debería mostrar:
```
INGESTA COMPLETADA
Plan Version: ruta27_v2026_01_17
Registros insertados: 0

Errores encontrados: X
  - Fila 2: segment inválido 'xxx'
  - ...
```

### 3. Verificar Formato del CSV

El CSV debe tener estas columnas:
- `country`
- `city`
- `lob_base`
- `segment` (valores: 'b2b' o 'b2c')
- `year` (formato numérico: 2026)
- `month` (formato numérico: 1-12)
- `trips_plan`
- `active_drivers_plan`
- `avg_ticket_plan`
- `revenue_plan` (opcional, pero recomendado)

## ✅ SOLUCIÓN

### Opción A: Verificar CSV Manualmente
1. Abrir el CSV en Excel o editor de texto
2. Verificar que tenga filas de datos (no solo headers)
3. Verificar que `segment` sea 'b2b' o 'b2c'
4. Verificar que `year` sea 2026 y `month` sea 1-12

### Opción B: Ejecutar Diagnóstico
```bash
cd backend
python scripts/test_csv_ingestion.py <ruta_al_csv>
```

### Opción C: Reingestar con Logs Detallados
Modificar temporalmente el endpoint para retornar errores detallados.

## 📝 NOTA

El fix aplicado (`cursor.rowcount > 0`) asegura que el contador sea correcto, pero si sigue en 0, significa que **ninguna fila pasó las validaciones** o hay otro problema.
