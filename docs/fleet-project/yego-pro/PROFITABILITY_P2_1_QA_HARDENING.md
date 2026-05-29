# Yego Pro Profitability P2.1 — QA & Hardening Report

## Fecha
2026-05-28

## Archivos tocados en esta sesion

| Archivo | Accion |
|---------|--------|
| `frontend/src/components/YegoProProfitabilityPage.jsx` | Reescritura completa (hardening) |
| `docs/fleet-project/yego-pro/PROFITABILITY_P2_1_QA_HARDENING.md` | Creado (este doc) |

## Archivos NO tocados (confirmado)

- Drivers: ninguno
- Yango Loyalty: ninguno
- Omniview: ninguno
- Backend: ninguno
- SQL/MVs: ninguno
- Scripts debug: ninguno
- App.jsx: sin cambios en esta sesion
- api.js: sin cambios en esta sesion
- controlTowerNavigationRegistry.js: sin cambios en esta sesion

## Nota de archivos pre-existentes en git diff

Los siguientes archivos aparecen en `git diff` pero NO fueron tocados en esta sesion P2.1:
- `backend/app/services/yango_loyalty_service.py` (sesion previa)
- `frontend/src/components/yangoLoyalty/YangoLoyaltyView.jsx` (sesion previa)

## Bugs encontrados y fixes aplicados

### BUG-1: Moneda incorrecta (EUR en vez de PEN)
- **Antes:** `€` con locale `es-ES`
- **Fix:** `S/` con locale `es-PE`
- **Severidad:** Alta (confunde al usuario)

### BUG-2: Sin proteccion contra loading infinito
- **Antes:** Sin AbortController, sin cleanup en useEffect
- **Fix:** AbortController en cada fetch, abort en cleanup y al cambiar tab
- **Severidad:** Alta (UX bloqueante)

### BUG-3: Errores tecnicos expuestos al usuario
- **Antes:** Stack traces y mensajes raw de axios visibles
- **Fix:** `friendlyError()` traduce HTTP status codes a mensajes operativos en espanol
- **Severidad:** Media (confusion de usuario no tecnico)

### BUG-4: Empty states genericos
- **Antes:** "Sin datos para esta vista." para todas las tabs
- **Fix:** Mensajes especificos por tab: "Fuente financiera pendiente", "Data operativa disponible, data financiera parcial"
- **Severidad:** Media (usuario no sabe por que no hay datos)

### BUG-5: Sin ordenamiento de tablas
- **Antes:** Datos en orden del endpoint (aleatorio)
- **Fix:** Drivers/Vehicles por mayor perdida primero, Weekly/Daily por fecha mas reciente primero
- **Severidad:** Media (usuario ve datos desordenados)

### BUG-6: Nulls visibles como "—"
- **Antes:** null/undefined/NaN mostrados como "—" o literalmente
- **Fix:** Todos normalizados a "No disponible" via `safeVal()`. Tambien atrapa strings "null", "undefined", "NaN", "None"
- **Severidad:** Media

### BUG-7: Raw JSON fallback
- **Antes:** Si la data no encajaba en un patrón, se mostraba `JSON.stringify(data, null, 2)`
- **Fix:** Siempre muestra EmptyState o tabla estructurada. Nunca JSON crudo
- **Severidad:** Alta (expone estructura interna al usuario)

### BUG-8: Banner de billing hardcoded
- **Antes:** Siempre "1 semana"
- **Fix:** Dinamico: lee `billing_weeks` de overview o quality response. Default 1
- **Severidad:** Baja (correcto para ahora, mejor a futuro)

### BUG-9: Cabeceras de columna en ingles/snake_case
- **Antes:** `driver_id`, `net_profit`, `margin_pct` visibles al usuario
- **Fix:** Diccionario `COLUMN_LABELS` traduce 40+ keys a espanol. Fallback: title case
- **Severidad:** Media

### BUG-10: Sin distincion visual dia/noche en Shifts
- **Antes:** Shift type como texto plano
- **Fix:** Icono sol (dia) / luna (noche) + labels traducidos
- **Severidad:** Baja

### BUG-11: Valores negativos sin señalizacion
- **Antes:** Profit negativo sin color ni badge
- **Fix:** Texto rojo + badge "En perdida" + borde rojo en KPI cards con loss
- **Severidad:** Media (usuario no ve alarma visual)

### BUG-12: Waterfall sin fallback cuando parcial
- **Antes:** Si faltaban datos, JSON crudo
- **Fix:** Banner "Waterfall parcial" + tabla de inputs con fuente/confianza siempre visible debajo de barras
- **Severidad:** Media

### BUG-13: Data Quality sin agrupacion por tipo de fuente
- **Antes:** Lista plana de checks
- **Fix:** Agrupado por REAL / DERIVED / ASSUMPTION / NOT_AVAILABLE con colores diferenciados. Cada check muestra fuente, confianza y observacion
- **Severidad:** Media

### BUG-14: Columnas _source/_confidence visibles en tablas
- **Antes:** Columnas internas como `revenue_source`, `cost_confidence` aparecian como columnas
- **Fix:** Filtradas del display. Solo se muestran como SourceBadge inline
- **Severidad:** Baja

## Endpoints validados (compilacion OK, runtime pendiente)

| Endpoint | Tab | Status |
|----------|-----|--------|
| `GET /fleet-project/yego-pro/profitability/overview` | Overview | Compilacion OK |
| `GET /fleet-project/yego-pro/profitability/weekly` | Weekly Closed | Compilacion OK |
| `GET /fleet-project/yego-pro/profitability/daily` | Last Closed Day | Compilacion OK |
| `GET /fleet-project/yego-pro/profitability/drivers` | Drivers | Compilacion OK |
| `GET /fleet-project/yego-pro/profitability/vehicles` | Vehicles | Compilacion OK |
| `GET /fleet-project/yego-pro/profitability/shifts` | Shifts | Compilacion OK |
| `GET /fleet-project/yego-pro/profitability/input-mapping` | Waterfall | Compilacion OK |
| `GET /fleet-project/yego-pro/profitability/quality` | Data Quality | Compilacion OK |

## Build result

```
vite v5.4.21 building for production...
837 modules transformed.
built in 12.13s — 0 errors, 0 warnings (except chunk size advisory)
```

## Riesgos pendientes

1. **Runtime no probado:** Los 8 endpoints necesitan estar activos en el backend para verificar datos reales
2. **Esquema de respuesta asumido:** El componente acepta multiples formatos (rows/data/items/checks/kpis), pero si el backend devuelve un esquema inesperado, caera en EmptyState (seguro, pero sin datos)
3. **Moneda asumida S/:** Si Yego Pro opera en USD u otra moneda en algun mercado, habria que parametrizar
4. **Chunk size warning:** El bundle total sigue >500KB (pre-existente, no causado por este modulo)

## GO / NO-GO

**GO para prueba humana de Gonzalo.**

Motivos:
- Build limpio
- No hay loading infinito posible (AbortController + friendly errors)
- Todos los empty states cubren el caso "endpoint no disponible"
- Lenguaje operativo en espanol
- Sin JSON crudo expuesto
- Sin contaminacion de otros modulos
- Banner de billing parcial visible y dinamico
