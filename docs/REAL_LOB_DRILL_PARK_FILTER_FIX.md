# Real LOB Drill — Filtro Park: diagnóstico y corrección

## 1. Diagnóstico de causa raíz

### Problema
En **Real LOB → Drill por país**, el filtro superior **Park** no se poblaba: solo se mostraba "Todos" y no se listaban parks aunque hubiera datos en el drill. Eso impedía filtrar el desglose por tipo_servicio por park.

### Causa raíz

1. **Fuente de datos distinta al drill**  
   El frontend cargaba opciones de Park con `getRealLobFilters()` → **GET /ops/real-lob/filters**, que obtiene parks de **ops.mv_real_lob_month_v2** y **ops.mv_real_lob_week_v2**.  
   El drill, en cambio, usa **ops.real_drill_dim_fact** (vía `mv_real_drill_dim_agg`) alimentado por **ops.v_trips_real_canon**.  
   Si las MVs v2 no están refrescadas o no tienen datos, el endpoint de filtros devolvía `parks: []` y el dropdown quedaba vacío aunque el drill sí tuviera datos.

2. **Ninguna dependencia incorrecta del desglose**  
   Revisión del código mostró que **no** existía una condición que cargara parks solo cuando `desglose === 'park'`. El problema era únicamente la fuente: filtros (MVs v2) vs drill (real_drill_dim_fact).

3. **Contrato UI**  
   Las opciones del select no usaban una etiqueta unificada tipo "Nombre Park — Ciudad", y el estado de opciones estaba mezclado en `filterOptions` con otros filtros en lugar de una lista dedicada para el drill.

---

## 2. Regla funcional aplicada

- **El filtro Park es de contexto**: debe existir y poblarse **siempre** en Real LOB Drill, con independencia de si el desglose actual es LOB, Park o Tipo de servicio.  
- **Parks del mismo universo que el drill**: la lista de parks del filtro debe provenir de la misma fuente que el drill para garantizar coherencia.

---

## 3. Archivos tocados

| Archivo | Cambio |
|--------|--------|
| `backend/app/services/real_lob_drill_pro_service.py` | Nueva función `get_drill_parks(country=None)` que lee **ops.real_drill_dim_fact** (breakdown=park) y devuelve `[{ country, city, park_id, park_name }]`. |
| `backend/app/routers/ops.py` | Nuevo endpoint **GET /ops/real-lob/drill/parks** (query opcional `country`) e import de `get_drill_parks`. |
| `backend/app/services/real_lob_filters_service.py` | **Fallback**: si la query a las MVs v2 devuelve `parks` vacío, se rellenan con `get_drill_parks()` para que GET /ops/real-lob/filters también devuelva parks cuando las MVs no estén pobladas. |
| `frontend/src/services/api.js` | Nueva función **getRealLobDrillParks(params)** que llama a GET /ops/real-lob/drill/parks. |
| `frontend/src/components/RealLOBDrillView.jsx` | (1) Carga de parks con **getRealLobDrillParks()** en un `useEffect` al montar (sin depender del desglose). (2) Estado dedicado `parks` en lugar de `filterOptions.parks`. (3) Select Park con etiqueta **"Nombre — Ciudad"** (o solo nombre si no hay ciudad válida). (4) Eliminada dependencia de `getRealLobFilters` para el dropdown Park. |

---

## 4. Condición o dependencia que estaba mal

- **Condición errónea**: No había una condición explícita tipo “solo cargar parks si desglose === 'park'”.  
- **Dependencia incorrecta**: La lista de parks del drill dependía del endpoint **GET /ops/real-lob/filters**, que usa MVs distintas (mv_real_lob_month_v2 / week_v2) al drill (real_drill_dim_fact). Cuando esas MVs no tenían datos o no se refrescaban, `parks` llegaba vacío y el filtro no se poblaba.

---

## 5. Comportamiento actual

- **Drill**: El filtro Park se alimenta de **GET /ops/real-lob/drill/parks**, que consulta **real_drill_dim_fact** (breakdown=park). Se puebla siempre al cargar la vista, con independencia del desglose (LOB / Park / Tipo de servicio).  
- **Etiquetas**: Cada opción muestra **"Nombre Park — Ciudad"** (o solo nombre si no hay ciudad o es "sin_city").  
- **Filtrado real**: Con un park seleccionado, las llamadas a drill y drill/children incluyen `park_id`; el backend aplica el filtro en el WHERE (timeline por park y desglose por tipo_servicio filtrado por ese park), tal como se implementó en el cambio anterior.

---

## 6. Confirmación

- **Park se lista**: La lista de parks del dropdown proviene de la misma fuente que el drill (real_drill_dim_fact), por lo que el filtro Park se puebla siempre que existan datos en el drill.  
- **Park filtra correctamente en tipo_servicio**: Al elegir un park y desglose "Tipo de servicio", el request a **GET /ops/real-lob/drill/children** envía `park_id` y el backend limita el desglose por tipo_servicio a ese park (consulta directa a v_trips_real_canon con filtro por park_id).

---

## 7. MV desglose tipo_servicio por park (068)

Para que el desglose por tipo_servicio con filtro Park sea rápido y no cuelgue la UI:

- **Migración 068** crea **ops.mv_real_drill_service_by_park** (country, period_grain, period_start, segment, park_id, city, tipo_servicio_norm, trips, margin_total, …) con la misma lógica y ventana de 90 días que `real_drill_dim_fact`.
- El backend usa esta MV en lugar de consultar `v_trips_real_canon` cuando `desglose=SERVICE_TYPE` y hay `park_id`.
- **Refresco:** incluir esta MV en el mismo pipeline que el resto de Real LOB (p. ej. `scripts/safe_refresh_real_lob.py`). Tras cargar datos en trips, ejecutar refresh para actualizar la MV.

---

## 8. Escenarios sugeridos para validación

- Desglose = **Tipo de servicio** + Park = **Todos**.  
- Desglose = **Tipo de servicio** + Park = **un park concreto** (ver solo tipos de servicio de ese park).  
- Desglose = **LOB** + Park = **un park concreto** (timeline y KPIs de ese park).  
- Desglose = **Park** (dropdown Park sigue siendo filtro de contexto; puede estar en "Todos" o en un park).  
- Cambio de país (si en el futuro se añade filtro país en el drill) y comprobar que la lista de parks se actualice si el endpoint recibe `country`.

**Tras aplicar la migración 068:** el desglose por tipo_servicio con Park seleccionado debe cargar en segundos (lectura desde la MV).
