# FASE 0 — Scan y mapeo: coherencia estructural del módulo REAL

**Objetivo:** Mapear punta a punta filtros, drill por park, fuentes de datos y causas del 500 y de incoherencias, sin implementar hasta cerrar el scan.

---

## A. FRONTEND

### Componentes que renderizan

| Componente | Rol |
|------------|-----|
| **RealLOBDrillView.jsx** | Contenedor: filtros (país implícito, periodo mensual/semanal, desglose LOB/Park/Tipo servicio, **dropdown Park**, segmento), tabla drill por país/periodo, expansión de filas (children). |
| **API llamadas** | `getRealLobDrillPro` → GET /ops/real-lob/drill (payload principal). `getRealLobDrillProChildren` → GET /ops/real-lob/drill/children (subfilas al expandir). `getRealLobDrillParks` → GET /ops/real-lob/drill/parks (lista para dropdown Park). |

### Cómo se construye el label de park

- **Dropdown Park (RealLOBDrillView ~líneas 410–421):**  
  `label = city ? `${name} — ${city}` : name` con `name = p.park_name || p.park_id || '—'`.  
  **No se muestra país.** No se usa formato `{park_name} — {city} — {country}`.

- **Children por park:** El backend devuelve `dimension_key` (usado como park_name), `dimension_id` (park_id), `city`. En frontend se muestra lo que viene en la fila (dimension_key / park_name). No hay construcción explícita de etiqueta “nombre — ciudad — país” en subfilas.

### Valor usado como key de selección

- Dropdown: `value={parkId}` con `park_id` (o `id`) del ítem; `key={id}` con `p.park_id ?? p.id`. La selección se envía al backend como `park_id` en los params del drill y de children.

### Endpoints que alimentan filtros vs drill

- **Filtros (países, ciudades, parks, LOB, tipo_servicio, años):**  
  **GET /ops/real-lob/filters** → `real_lob_filters_service.get_real_lob_filters(country, city)`.  
  **Fuente de parks en filters:** `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2` (DISTINCT country, city, park_id, park_name). Si `parks` queda vacío, fallback a `get_drill_parks()` (real_drill_dim_fact).

- **Lista de parks del dropdown del drill:**  
  **GET /ops/real-lob/drill/parks** → `real_lob_drill_pro_service.get_drill_parks(country)`.  
  **Fuente:** `ops.real_drill_dim_fact` WHERE breakdown = 'park' → `dimension_id AS park_id`, `dimension_key AS park_name`, `country`, `city`.

- **Drill principal:** GET /ops/real-lob/drill → `get_drill(period, desglose, segmento, country, park_id)`. Fuente: `ops.mv_real_drill_dim_agg` (= vista sobre `real_drill_dim_fact`).

- **Children (subfilas al expandir):** GET /ops/real-lob/drill/children → `get_drill_children(country, period, period_start, desglose, segmento, park_id)`. Fuente: misma MV (y en caso SERVICE_TYPE+park_id, `ops.mv_real_drill_service_by_park`).

### Transmisión del filtro park al backend

- Params de drill: `park_id` (opcional). Params de children: `park_id` (opcional). Se envían en query string / body según definición de los endpoints.

---

## B. BACKEND

### Servicios implicados

| Servicio | Uso |
|----------|-----|
| **real_lob_filters_service** | GET /ops/real-lob/filters. Parks desde mv_real_lob_month_v2 + mv_real_lob_week_v2; fallback get_drill_parks. |
| **real_lob_drill_pro_service** | GET /ops/real-lob/drill (get_drill), GET /ops/real-lob/drill/children (get_drill_children), GET /ops/real-lob/drill/parks (get_drill_parks). |

### Fuente exacta del catálogo de parks

- **Filtros:** `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2` (UNION DISTINCT country, city, park_id, park_name).  
- **Drill dropdown:** `ops.real_drill_dim_fact` WHERE breakdown = 'park' → dimension_id (park_id), dimension_key (park_name), country, city.

### Fuente exacta del drill por park

- **Drill principal con desglose PARK o filtro park_id:** `ops.mv_real_drill_dim_agg` (real_drill_dim_fact) con breakdown = 'park' y opcional `dimension_id = park_id`.  
- **Children por PARK:** misma tabla, misma MV, query con breakdown = 'park'.

### Joins para city/country/park_name

- **real_drill_dim_fact:** ya almacena `country`, `city`, `dimension_key` (nombre de park para breakdown=park), `dimension_id` (park_id). No hay join en tiempo de consulta; la dimensión viene del populate (desde day_v2/week_v3 que a su vez vienen de v_real_trip_fact_v2 con park_name/city/country).  
- **Filtros (MVs):** month_v2/week_v2 tienen columnas park_id, park_name, city, country directamente en la MV.

### Dónde puede romperse con cancelled_trips

- **get_drill:** Hay un bloque try/except que hace `SUM(COALESCE(cancelled_trips, 0))`; si falla por columna inexistente se hace `conn.rollback()` y se re-ejecuta la misma agregación **sin** cancelled_trips y se rellena `cancelaciones = 0`. Correcto.
- **get_drill_children:** Las dos queries que agregan por dimension_key/dimension_id/city (líneas ~790 y ~843) incluyen `SUM(COALESCE(cancelled_trips, 0))` y **no** tienen try/except ni rollback. Si la columna no existe (o la migración 103 no está aplicada / el populate no ha corrido con la columna), la query falla y se propaga → **500**.  
  **Causa raíz del 500 en drill por park:** fallo en **get_drill_children** al expandir una fila (o al cargar children con desglose PARK) cuando `real_drill_dim_fact` no tiene la columna `cancelled_trips` o la transacción queda abortada.

---

## C. SQL / MODELO

### Vistas/tablas usadas

| Objeto | Uso | Grain | Dimensiones park |
|--------|-----|-------|-------------------|
| **ops.real_drill_dim_fact** | Drill principal y children; lista de parks (get_drill_parks). | (country, period_grain, period_start, segment, breakdown, dimension_key, dimension_id, city) | dimension_id = park_id, dimension_key = park name, city, country |
| **ops.mv_real_drill_dim_agg** | Vista `SELECT * FROM real_drill_dim_fact`. Misma fuente. | Idem | Idem |
| **ops.mv_real_lob_month_v2** | Filtros: parks (y countries, cities, LOB, tipo_servicio). | month_start, country, city, park_id, … | park_id, park_name, city, country |
| **ops.mv_real_lob_week_v2** | Filtros: parks (y countries, cities, …). | week_start, country, city, park_id, … | park_id, park_name, city, country |
| **ops.mv_real_drill_service_by_park** | Children cuando desglose = SERVICE_TYPE y hay park_id. | period_start, country, park_id, tipo_servicio_norm | park_id (filtro) |

### Si nombres vienen de dim.dim_park o transaccional

- **real_drill_dim_fact:** Se puebla con `populate_real_drill_from_hourly_chain` desde `mv_real_lob_day_v2` y `mv_real_lob_week_v3`; city, park_name (dimension_key para park) y country vienen de esas MVs (a su vez de v_real_trip_fact_v2 → parks / lógica geo). No se usa explícitamente `dim.dim_park` en el flujo del drill.  
- **Filtros (month_v2/week_v2):** Las MVs se construyen desde v_real_trip_fact_v2; park_name/city/country son los de la capa hourly-first.  
- No hay una única “dimensión canónica” documentada tipo dim.dim_park para todo REAL; la resolución es vía capa fact/MVs.

### Diferencias entre weekly y monthly

- Misma tabla `real_drill_dim_fact`; `period_grain` = 'week' o 'month' y `period_start` distinto. Son dos rollups del mismo dataset poblado por el mismo script (day_v2 para día → semana/mes según grain). Reconciliables en principio si el populate es consistente.

---

## D. RESULTADO DEL SCAN

### 1. Causa raíz del error 500 por park

- **Causa:** En **get_drill_children** (real_lob_drill_pro_service) se ejecutan dos queries que usan `SUM(COALESCE(cancelled_trips, 0))` sobre `ops.mv_real_drill_dim_agg` (real_drill_dim_fact) **sin** try/except. Si la columna `cancelled_trips` no existe (migración 103 no aplicada) o la transacción previa quedó abortada, la query falla y el endpoint devuelve 500.  
- **Mitigación correcta:** Aplicar el mismo patrón que en get_drill: try/except, en caso de error por `cancelled_trips` hacer `conn.rollback()`, re-ejecutar la query sin cancelled_trips y rellenar `cancelaciones = 0` en las filas.

### 2. Causa de que algunos parks aparezcan en filtros pero no en drill

- **Filtros:** Parks = DISTINCT de **mv_real_lob_month_v2** y **mv_real_lob_week_v2** (ventana/grain de esas MVs).  
- **Drill:** Parks = DISTINCT de **real_drill_dim_fact** (breakdown=park), poblado por **populate_real_drill_from_hourly_chain** desde **day_v2** y **week_v3** (otra ventana/config).  
- Si el populate del drill no se ha ejecutado o tiene otra ventana (días/semanas), habrá parks en las MVs que no están en real_drill_dim_fact. A la inversa, si las MVs están desactualizadas, puede haber parks en el drill que no aparezcan en el filtro. **Desalineación de universo:** dos fuentes (MVs vs tabla drill) y posible distinta ventana o momento de refresh.

### 3. Si semanal y mensual consultan la misma base o bases distintas

- **Misma base:** Ambos leen de `real_drill_dim_fact` (vía mv_real_drill_dim_agg) con el mismo `country`/segment/breakdown; solo cambia `period_grain` ('week' vs 'month') y `period_start`. Son dos rollups del mismo dataset; reconciliables si el populate es correcto.

### 4. Si park/LOB/tipo servicio son realmente reconciliables hoy

- **Sí, en origen:** Los tres desgloses vienen de la misma tabla (real_drill_dim_fact) con el mismo grain (country, period_grain, period_start, segment) y solo cambia `breakdown` (lob / park / service_type). Por construcción, para un mismo (country, period_start, segment) la suma de viajes por LOB debería coincidir con la suma por park y con la por tipo_servicio, salvo redondeos o filas “unclassified” que se excluyan en uno y no en otro. No hay reconciliación automática instalada; habría que añadir queries/script que comprueben igualdad de totales.

### 5. Propuesta mínima correcta para unificar criterio

- **500:** Añadir en **get_drill_children** el mismo patrón try/except + rollback + query sin cancelled_trips que en get_drill.  
- **Etiqueta park:** Definir etiqueta canónica `{park_name} — {city} — {country}` y usarla en get_drill_parks, en la respuesta de children (park_name_resolved o label), y en frontend (dropdown, chips, subfilas).  
- **Universo filtros vs drill:** Opción A: que el dropdown de parks del drill use **solo** get_drill_parks (misma fuente que el drill). Opción B: que filters siga usando MVs pero que el dropdown del drill siga usando get_drill_parks y se documente que “parks en drill” = real_drill_dim_fact; y opcionalmente marcar en UI los que no tienen data en la ventana actual. Recomendación: **unificar catálogo visible del drill con get_drill_parks** y, si se quiere filtros unificados, que GET /ops/real-lob/filters devuelva parks desde get_drill_parks cuando sea para el mismo contexto (drill).  
- **Dimensión canónica:** Documentar que para REAL la dimensión park/ciudad/país “oficial” en drill y en filtros del drill es la que sale de real_drill_dim_fact (y por tanto del populate desde day_v2/week_v3). Si existe dim.dim_park, usarla como maestro de nombres y cruzar por park_id en el populate o en una vista intermedia para no duplicar lógica.  
- **Reconciliación:** Añadir script o queries que comprueben, para un rango dado, que total por park = total por LOB = total por tipo_servicio (y semanal vs mensual cuando aplique).

---

**No implementar** más allá del fix del 500 hasta validar este scan y la decisión de producto sobre universo filtros vs drill y etiqueta canónica.

---

## FASE 3 – Dimensión canónica park/ciudad/país (documentada)

- **Fuente oficial en el drill:** `ops.real_drill_dim_fact` (y vista `ops.mv_real_drill_dim_agg`). Columnas: `dimension_id` = park_id, `dimension_key` = nombre de park (breakdown=park), `city`, `country`.
- **Origen de los valores:** El script `populate_real_drill_from_hourly_chain` puebla desde `mv_real_lob_day_v2` y `mv_real_lob_week_v3`; city/park_name/country vienen de esa cadena (v_real_trip_fact_v2 → parks/geo). No se usa explícitamente `dim.dim_park` en el flujo actual.
- **Regla:** Para el módulo REAL, la resolución única de park/ciudad/país en el drill es la que está en `real_drill_dim_fact`. Filtros que alimenten el **dropdown del drill** deben usar la misma fuente (get_drill_parks = real_drill_dim_fact) para evitar parks en filtro sin representación en el drill.

## FASE 4 – Coherencia filtros y drill (regla aplicada)

- El **dropdown de Park en RealLOBDrillView** consume **GET /ops/real-lob/drill/parks** (get_drill_parks → real_drill_dim_fact). No usa GET /ops/real-lob/filters para la lista de parks del drill. Por tanto el universo del dropdown y el del drill coinciden.
- GET /ops/real-lob/filters sigue devolviendo parks desde mv_real_lob_month_v2/week_v2 para otros usos (p. ej. vistas que usen esos filtros); si en el futuro se unifica todo el catálogo de parks a real_drill_dim_fact, puede cambiarse el filters service para que parks venga de get_drill_parks.
