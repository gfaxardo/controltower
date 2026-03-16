# Fix runtime: drill children 500 y margin-quality 404

## Objetivo
Dejar estable el drill REAL y eliminar errores activos en runtime:
- `/ops/real-lob/drill/children` → 200 (sin uso de columna `cancelled_trips`)
- `/ops/real/margin-quality` o `/ops/real-margin-quality` → 200 o consumo desactivado en UI

## FASE A — Cambios realizados (cancelled_trips eliminado)

### 1. `backend/app/services/real_lob_drill_pro_service.py`

- **get_drill()**  
  - Eliminado el `try/except` que intentaba usar `SUM(COALESCE(cancelled_trips, 0))`.  
  - Query única que **no** usa `cancelled_trips`; se asigna `cancelaciones = 0` en los agregados por periodo.

- **get_drill_children()**  
  - Rama principal (LOB, PARK, SERVICE_TYPE; week y month):  
    - Una sola query a `ops.mv_real_drill_dim_agg` **sin** `cancelled_trips`.  
    - Se rellena `cancelaciones = 0` en cada fila.  
  - Query del periodo anterior (WoW/MoM): misma query sin `cancelled_trips` y `cancelaciones = 0`.  
  - Rama SERVICE_TYPE + park_id: usa `MV_SERVICE_BY_PARK`, que ya no referencia `cancelled_trips`.

- No se usa `information_schema` ni `try/except` como lógica principal; la query base es siempre la que no incluye `cancelled_trips`.

### 2. `backend/app/routers/ops.py`

- Ruta de margin-quality:  
  - Se mantiene `GET /ops/real/margin-quality`.  
  - Se añade **alias** `GET /ops/real-margin-quality` (misma función) para evitar 404 si hay conflicto con el path `/real/...`.

### 3. `frontend/src/services/api.js`

- `getRealMarginQuality` llama a **`/ops/real-margin-quality`** en lugar de `/ops/real/margin-quality` para usar la ruta estable.

### 4. Script de verificación

- **`backend/scripts/verify_drill_and_margin.ps1`**  
  - Comprueba con requests reales (Invoke-WebRequest) que devuelvan 200:  
    - drill week LOB  
    - drill/children week LOB PE  
    - drill/children month LOB PE  
    - drill/children month PARK PE  
    - drill/children month SERVICE_TYPE PE  
    - real-margin-quality  

## Cómo validar en tu entorno (runtime-first)

1. **Reiniciar el backend** (para cargar el código nuevo):
   ```bash
   # En la terminal donde corre uvicorn: Ctrl+C
   cd backend
   uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

2. **Opcional:** Limpiar caché de Python antes de reiniciar:
   ```powershell
   Get-ChildItem -Path app -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
   ```

3. **Ejecutar el script de verificación** (con el backend levantado):
   ```powershell
   cd backend
   .\scripts\verify_drill_and_margin.ps1
   ```
   Debes ver `[OK] ... -> 200` en las rutas listadas.

4. **Comprobar manualmente** (ejemplos con PowerShell):
   ```powershell
   # Children week LOB
   Invoke-WebRequest -Uri "http://127.0.0.1:8000/ops/real-lob/drill/children?country=pe&period=week&period_start=2026-03-09&desglose=LOB&segmento=all" -UseBasicParsing -TimeoutSec 120

   # Margin-quality (ruta alternativa)
   Invoke-WebRequest -Uri "http://127.0.0.1:8000/ops/real-margin-quality?days_recent=90&findings_limit=20" -UseBasicParsing -TimeoutSec 30
   ```

5. **UI:**  
   - Abrir la pestaña Real, drill por LOB/PARK/SERVICE_TYPE.  
   - Expandir children: no debe haber 500 ni spinner infinito.  
   - Si margin-quality sigue fallando, la card mostrará error o “no se pudo obtener”; el drill debe seguir funcionando.

## Lista exacta de archivos modificados

| Archivo | Cambio |
|--------|--------|
| `backend/app/services/real_lob_drill_pro_service.py` | Eliminado todo uso de `cancelled_trips` en get_drill y get_drill_children; query base sin esa columna; `cancelaciones = 0` en payload. |
| `backend/app/routers/ops.py` | Añadido alias `@router.get("/real-margin-quality")` para el mismo handler de margin-quality. |
| `frontend/src/services/api.js` | getRealMarginQuality usa `/ops/real-margin-quality`. |
| `backend/scripts/verify_drill_and_margin.ps1` | Nuevo script de verificación por requests. |
| `docs/RUNTIME_FIX_DRILL_AND_MARGIN_QUALITY.md` | Este documento. |

## Si sigue fallando en tu máquina

- Confirma que el proceso de uvicorn se reinició **después** de guardar los cambios.  
- Comprueba que no haya otro proceso usando el puerto 8000 con código viejo.  
- Ejecuta el script de verificación y pega la salida (qué rutas dan OK y cuáles FAIL) para diagnosticar.
