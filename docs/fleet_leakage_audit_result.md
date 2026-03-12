# Auditoría: Fleet Leakage Monitor / Posible robo de drivers

**Proyecto:** YEGO Control Tower  
**Fecha auditoría:** 2025-03-12  
**Regla aplicada:** Si la vista no existe de forma visible y usable en la UI real, para efectos del proyecto NO está implementada.

---

## FASE 0 — BÚSQUEDA GLOBAL

### Términos buscados

- fleet leakage, supply leakage, leakage monitor, poaching, driver leakage  
- high_suspicion_leakage, progressive_leakage, early_leakage, lost_driver  
- driver_tier, historical_stability, leakage_score, recovery_priority  

### Coincidencias reales

| Ubicación | Resultado |
|-----------|-----------|
| **Frontend (src)** | **0 coincidencias.** No hay FleetLeakageView, LeakageMonitorView, fleet_leakage, getLeakage*, ni ninguna referencia a leakage en componentes, rutas o api.js. |
| **Backend (app)** | **0 coincidencias.** No hay leakage_service.py, fleet_leakage_service.py, ni rutas /ops/leakage/ en ops.py ni en ningún router. |
| **Alembic (migrations)** | **0 coincidencias.** No existe migración que cree v_fleet_leakage_snapshot, v_leakage_drivers_weekly ni ninguna vista/MV de leakage. |
| **Docs / markdown** | **1 archivo:** `docs/fleet_leakage_monitor_scan.md`. Contiene el escaneo y plan de implementación (Fase 0 y Fase 1), **no** código ni implementación. |

### Archivos exactos encontrados

- **Único archivo con rastro de Fleet Leakage:** `docs/fleet_leakage_monitor_scan.md`  
  - Es un documento de **planificación y mapeo** (qué fuentes usar, qué endpoints crear, qué componente crear).  
  - Indica explícitamente: "Nueva migración", "Nuevo servicio", "Nuevo componente", "Nueva pestaña".  
  - No existe `docs/fleet_leakage_logic.md` (mencionado en el doc como lugar futuro de documentación).

### Conclusión FASE 0

**No hay coincidencias en código.** Todas las coincidencias están en un único documento de planificación. No hay implementación en frontend, backend ni SQL.

---

## FASE 1 — DIAGNÓSTICO DE ESTADO

**Categoría elegida: B. Solo prompt/documentación, sin implementación.**

### Justificación con evidencia

- El “prompt” o plan (Fleet Leakage Monitor / Posible robo de drivers) **sí se ejecutó en forma de documento**: existe `fleet_leakage_monitor_scan.md` con escaneo de fuentes, endpoints sugeridos, plan de implementación y definición funcional de leakage.
- **No se ejecutó** como implementación de software:
  - No hay tab "Fleet Leakage" en `App.jsx` (tabs existentes: real_lob, driver_lifecycle, supply, behavioral_alerts, driver_behavior, action_engine, snapshot, system_health, legacy).
  - No existe `FleetLeakageView.jsx` ni `LeakageMonitorView.jsx` en `frontend/src/components/`.
  - No existe `getLeakageSummary`, `getLeakageDrivers`, `getLeakageExportUrl`, etc. en `frontend/src/services/api.js`.
  - No existe ruta `GET /ops/leakage/summary`, `/ops/leakage/drivers`, `/ops/leakage/export`, etc. en `backend/app/routers/ops.py`.
  - No existe `backend/app/services/leakage_service.py` ni `fleet_leakage_service.py`.
  - No existe ninguna migración Alembic que cree vistas o MVs de leakage (`v_fleet_leakage_snapshot`, `v_leakage_drivers_weekly`, etc.).

Por tanto: **solo hay documentación/plan; no hay backend parcial, no hay UI parcial, no hay implementación conectada ni visible.**

---

## FASE 2 — SI EXISTE ALGO IMPLEMENTADO, MAPEARLO

**No aplica.** No existe implementación parcial ni completa de Fleet Leakage en el proyecto. No hay ruta frontend, componente, endpoint, servicio backend ni fuente SQL que mapear.

---

## FASE 3 — AUDITORÍA DE PERSISTENCIA VISUAL

No existe vista de Fleet Leakage en la UI. Para cada ítem:

| Ítem | Estado |
|------|--------|
| Nombre visible de la vista | **No existe** |
| Cards KPI superiores | **No existe** |
| Filtros propios | **No existe** |
| Tabla principal | **No existe** |
| Columnas de leakage (status, score, priority, tier, stability) | **No existe** |
| Export | **No existe** |
| Navegación accesible desde el sistema real | **No existe** (no hay tab ni enlace a Fleet Leakage en App.jsx) |

---

## FASE 4 — QUÉ FALTA (NO INVENTAR)

Al no existir implementación ni persistencia en UI:

- **No está implementado.** No es “casi” ni “listo”.
- **Lo que falta para que exista y sea visible/usable:**

| Capa | Qué falta |
|------|-----------|
| **Navegación** | Añadir en `App.jsx`: botón/tab "Fleet Leakage Monitor" (o "Supply Leakage") y `activeTab === 'fleet_leakage'` con renderizado del componente de la vista. |
| **Frontend** | Crear `FleetLeakageView.jsx` (o `LeakageMonitorView.jsx`) con KPIs, filtros, tabla, columnas de leakage, export. Añadir en `api.js`: getLeakageSummary, getLeakageDrivers, getLeakageExportUrl, getLeakageCohortMetrics (o equivalentes). |
| **Backend** | Crear `leakage_service.py` (o `fleet_leakage_service.py`) con get_leakage_summary, get_leakage_drivers, get_leakage_export, get_leakage_cohort_metrics. Registrar en `ops.py` (o router correspondiente) las rutas GET /ops/leakage/summary, /ops/leakage/drivers, /ops/leakage/export, /ops/leakage/cohort-metrics (y opcional driver-detail). |
| **SQL** | Nueva migración Alembic que cree vista o MV de leakage (ej. `ops.v_fleet_leakage_snapshot` o `ops.v_leakage_drivers_weekly`) con columnas: driver_key, driver_tier, historical_stability, leakage_status, leakage_score, recovery_priority, etc., según el plan en `fleet_leakage_monitor_scan.md`. |
| **Documentación** | Opcional: completar `docs/fleet_leakage_logic.md` con definición de leakage, clasificación, driver_tier, historical_stability, score, cohorte ancla (el scan doc ya esboza esto). |
| **Conexión entre capas** | Conectar frontend a los endpoints /ops/leakage/* y asegurar que la vista se muestre al elegir el tab Fleet Leakage en la navegación real. |

---

## FASE 5 — SALIDA FINAL

### 1. Estado real de Fleet Leakage

**Fleet Leakage no está implementado en la UI real.** Solo existe un documento de planificación y mapeo (`docs/fleet_leakage_monitor_scan.md`). No hay código en frontend, backend ni base de datos que implemente el módulo.

### 2. Evidencia encontrada

- **Documentación:** Un único archivo, `docs/fleet_leakage_monitor_scan.md`, que describe el módulo, fuentes de datos, endpoints a crear, componente a crear y plan de implementación.
- **Código:** Búsqueda global en frontend (rutas, componentes, servicios) y backend (routers, servicios) y en Alembic por "leakage", "fleet_leakage", "FleetLeakage", "LeakageMonitor", "getLeakage", "v_fleet_leakage", "v_leakage": **cero coincidencias** en código.

### 3. Qué sí existe

- El documento de escaneo y plan: `docs/fleet_leakage_monitor_scan.md` (Fase 0 de mapeo y Fase 1 de definición funcional de leakage, estados sugeridos, plan de implementación no destructiva).

### 4. Qué no existe

- Navegación (tab o enlace) a Fleet Leakage en la aplicación.
- Componente de vista Fleet Leakage (FleetLeakageView.jsx o similar).
- Llamadas API de leakage en el frontend (api.js).
- Endpoints `/ops/leakage/*` en el backend.
- Servicio backend de leakage (leakage_service.py o similar).
- Vista o MV SQL de leakage (v_fleet_leakage_snapshot, v_leakage_drivers_weekly, etc.).
- Cualquier persistencia visual o funcional del módulo en la UI que usa el usuario.

### 5. Si persiste o no en UI real

**No persiste.** No hay vista de Fleet Leakage en la UI real. El usuario no puede acceder a ningún pantalla, filtros, tabla ni export de Fleet Leakage desde la aplicación.

### 6. Qué falta para que quede visible y usable

Para que Fleet Leakage esté implementado y sea visible y usable:

1. **Navegación:** Añadir tab (o equivalente) en la barra principal y renderizar la vista cuando se seleccione.
2. **Frontend:** Crear la vista (FleetLeakageView.jsx) y las funciones de API (getLeakageSummary, getLeakageDrivers, getLeakageExportUrl, etc.).
3. **Backend:** Crear el servicio (leakage_service.py) y registrar las rutas GET /ops/leakage/summary, /drivers, /export, /cohort-metrics (y opcional driver-detail).
4. **SQL:** Crear migración con vista o MV de leakage con las columnas definidas en el plan (driver_tier, historical_stability, leakage_status, leakage_score, recovery_priority, etc.).
5. **Conexión:** Conectar la vista frontend a los endpoints y asegurar que los datos se muestren correctamente en la UI.

---

**Conclusión:** Fleet Leakage no está implementado en UI real. Solo existe como plan en documentación.
