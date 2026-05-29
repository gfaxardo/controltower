# DRIVERS HUMAN GUIDE QA — UX-C2

**Fecha:** 2026-05-28
**Objetivo:** Validar guía humana de Drivers + auditoría de aislamiento de cambios.

---

## 1. MATRIZ DE IMPACTO

### A) ARCHIVOS PERMITIDOS (Drivers)

| Archivo | Motivo del cambio | Relación con Drivers |
|---|---|---|
| `frontend/src/config/driverTabGuideRegistry.js` | NUEVO — Registro de guía humana con 23 entries | Config exclusiva Drivers |
| `frontend/src/components/driver/DriverTabGuide.jsx` | NUEVO — Componente colapsable de guía | Componente exclusivo Drivers |
| `frontend/src/components/driver/DriverOperatingHub.jsx` | Import + render de DriverTabGuide | Hub principal de Drivers |
| `frontend/src/components/driver/CampaignEffectiveness.jsx` | Noise reduction: labels a español | Componente Drivers |
| `frontend/src/components/driver/CampaignIntelligence.jsx` | Import CampaignOperatingBoard + loop-status | Componente Drivers |
| `frontend/src/components/driver/CampaignOperatingBoard.jsx` | NUEVO — Board operativo de campañas | Componente Drivers |
| `frontend/src/components/driver/CrmBridge.jsx` | Noise reduction: labels a español | Componente Drivers |
| `frontend/src/App.jsx` | Tooltips via getTabGuide en subPillSimple | Navegación Drivers (tooltip only) |
| `docs/drivers/DRIVERS_HUMAN_TAB_GUIDE_UX_C1.md` | Documentación UX-C1 | Docs Drivers |
| `docs/drivers/DRIVERS_OPERATIONAL_LOOP_MATURITY_OLM1.md` | Documentación loop maturity | Docs Drivers |
| `docs/drivers/DRIVERS_OPERATOR_HANDOFF_GUIDE.md` | Documentación handoff operador | Docs Drivers |
| `docs/drivers/DRIVERS_SUPERVISOR_RUNBOOK.md` | Documentación runbook supervisor | Docs Drivers |
| `backend/app/routers/drivers.py` | Router Drivers | Backend Drivers |
| `backend/app/services/driver_operational_loop_service.py` | Service loop operativo | Backend Drivers |

### B) REVISAR

| Archivo | Hallazgo | Veredicto |
|---|---|---|
| `frontend/src/App.jsx` | Cambio acotado: solo agrega `import { getTabGuide }` y tooltip en `subPillSimple` | PERMITIDO — cambio exclusivo Drivers |

### C) SOSPECHOSOS — PRE_EXISTING_CHANGE

Todos los siguientes archivos fueron incluidos en el commit `f13ce3f` ("feat: updates generales") que mezcló múltiples iniciativas. **NO fueron creados por UX-C2.** Se reportan como PRE_EXISTING_CHANGE.

**Yango Loyalty:**
- `backend/alembic/versions/157_yango_loyalty_performance_foundation.py`
- `backend/alembic/versions/158_yango_loyalty_metric_definition_registry.py`
- `backend/app/routers/yango_loyalty.py`
- `backend/app/services/yango_loyalty_definition_service.py`
- `backend/app/services/yango_loyalty_performance_service.py`
- `backend/scripts/apply_yango_loyalty_performance_foundation.py`
- `backend/scripts/preview_yango_loyalty_metric_definitions.py`
- `backend/scripts/validate_yango_loyalty_*` (9 scripts)
- `docs/yango_loyalty/*` (2 docs)
- `frontend/src/components/yangoLoyalty/*` (3 componentes)
- `frontend/src/services/api.js` (committed: `getYangoLoyaltyPerformance`)

**Yego Pro Profitability:**
- `REPORTE_YEGO_PRO_PROFIT_SHARING.md`
- `backend/app/routers/yego_pro_profitability.py`
- `backend/app/services/yego_pro_profitability_service.py`
- `backend/sql/yego_pro_profitability_serving_views.sql`
- `docs/fleet-project/yego-pro/*` (3 docs)
- `docs/yego-pro-profitability/*` (3 docs)
- `reports/*` (14 archivos CSV/MD)

**Operational / Global:**
- `backend/alembic/versions/159_yego_operational_flow_internal_kpi.py`
- `backend/alembic/versions/160_yego_historical_presence_operational_flow_v2.py`
- `backend/app/main.py`
- `backend/scripts/*` (19 scripts de discovery/debug/audit)

### D) OUT_OF_SCOPE_FINDING — Uncommitted

| Archivo | Detalle |
|---|---|
| `frontend/src/services/api.js` | Cambio NO commiteado: agrega 8 funciones de Yego Pro Profitability (P2). NO es de Drivers. NO fue creado por UX-C2. Pertenece a otra iniciativa activa. **NO TOCAR.** |

---

## 2. ARCHIVOS REVERTIDOS

**Ninguno.** Los cambios fuera de alcance son PRE_EXISTING_CHANGE del commit `f13ce3f` y NO deben revertirse para no romper trabajo de otros equipos.

---

## 3. QA DE GUIA HUMANA

### Estructura del componente

| Criterio | Estado |
|---|---|
| Cada subtab muestra guía | PASS — `DriverTabGuide` renderiza para cualquier `activeSub` con entrada en registry |
| La guía es colapsable | PASS — `useState(false)` + botón toggle "Ver guía" / "Ocultar guía" |
| No ocupa demasiado espacio | PASS — Collapsed: 1 línea con `oneLinePurpose`. Expanded: 5 secciones compactas |
| Tooltips aparecen | PASS — `subPillSimple` en App.jsx agrega `title` con purpose + decision |
| Entendible para operador | PASS — Español claro, sin jerga técnica |
| Entendible para supervisor | PASS — Decisiones y next steps explícitos |
| Sin jerga técnica excesiva | PASS — Todo el copy es accesible |

### Contenido del registry

- **Total entries:** 23
- **Campos por entry:** id, title, oneLinePurpose, whatYouCanDo, howToUse, decisionItSupports, nextStep, dataUnavailableMessage, audience
- **Idioma:** Español completo
- **Audiencias cubiertos:** operator, supervisor, strategy, admin

### Noise reduction aplicado

| Componente | Cambio |
|---|---|
| CampaignEffectiveness | Headers y KPIs traducidos a español (Members→Conductores, Trip Δ→Cambio viajes, etc.) |
| CrmBridge | Descripción simplificada, labels a español, nota de degradación en español |
| CampaignIntelligence | Integración con CampaignOperatingBoard + loop-status endpoint |

---

## 4. PRUEBA DE 5 SEGUNDOS

| Tab | ¿Qué logro? | ¿Cómo lo uso? | ¿Qué decisión tomo? | Resultado |
|---|---|---|---|---|
| **Supply Overview** | Ver evolución semanal del supply | Revisar tendencia de net growth | ¿Base crece o se pierde? | PASS |
| **Segment Composition** | Ver distribución por etapa de vida | Observar % por segmento | ¿Dónde concentrada la flota? | PASS |
| **Driver Migration** | Ver movimientos entre segmentos | Filtrar por prioridad operativa | ¿Quién se deterioró esta semana? | PASS |
| **Action Queues** | Ver qué conductores accionar primero | Filtrar por prioridad y tipo | ¿A quién contacto primero? | PASS |
| **Campaign Intelligence** | Crear campaña desde priorizados | Elegir queues, filtrar, previsualizar | ¿Con quién hago campaña? | PASS |
| **CRM Bridge** | Exportar al CRM y recibir resultados | Verificar, exportar, importar | ¿El CRM recibió la lista? | PASS |
| **Campaign Effectiveness** | Revisar si volvieron a operar | Seleccionar campaña + ventana D+7/14 | ¿La campaña tuvo efecto? | PASS |
| **Data Foundation** | Saber si la data está fresca | Revisar que fuentes estén en verde | ¿Puedo confiar en los datos? | PASS |
| **Operational Health** | Ver si servicios funcionan | Revisar servicios caídos o lentos | ¿El sistema está operativo? | PASS |
| **Capability Governance** | Ver qué capacidades están maduras | Consultar estado de cada capacidad | ¿Qué puedo usar hoy? | PASS |

**10/10 tabs pasan la prueba de 5 segundos.**

---

## 5. BUILD

| Componente | Resultado |
|---|---|
| `python -m compileall backend/app` | PASS — Sin errores |
| `npm run build` (frontend) | PASS — Built in 34.81s, 837 modules |

Nota: Warning de chunk size (>500KB) es preexistente, no relacionado con Drivers.

---

## 6. CHANGE_SCOPE_REPORT

### Archivos modificados por UX-C2
Ninguno (UX-C2 es una auditoría, no modifica código).

### Archivos creados por UX-C2
- `docs/drivers/DRIVERS_HUMAN_GUIDE_QA_UX_C2.md` (este documento)

### Archivos eliminados por UX-C2
Ninguno.

### Archivos fuera de Drivers tocados por UX-C2
**0** (cero)

### Cambios fuera de alcance encontrados
- **PRE_EXISTING_CHANGE:** Commit `f13ce3f` mezcla cambios de Drivers, Yango Loyalty y Yego Pro Profitability en un solo commit "feat: updates generales". Esto es una deuda de gobernanza de commits, pero no fue creado por UX-C2.
- **OUT_OF_SCOPE_FINDING:** `frontend/src/services/api.js` tiene cambios uncommitted que agregan funciones de Yego Pro Profitability. No pertenece a Drivers.

### Cambios revertidos
Ninguno. Los cambios fuera de alcance son preexistentes.

### Cambios preexistentes
Commit `f13ce3f` contiene ~50+ archivos de otras iniciativas bundleados. Detalle en sección 1.C.

### Resultado del build
PASS (backend + frontend).

### QA de tabs
10/10 PASS.

---

## 7. GO / NO-GO

### Veredicto: **GO**

### Justificación:
1. La guía humana de Drivers funciona correctamente (23 entries, colapsable, tooltips)
2. El noise reduction en CampaignEffectiveness, CrmBridge y CampaignIntelligence es correcto
3. **0 archivos fuera de Drivers fueron modificados por UX-C2**
4. Los cambios fuera de scope detectados son PRE_EXISTING_CHANGE del commit `f13ce3f`, no de esta ejecución
5. Build backend + frontend: PASS
6. 10/10 tabs pasan prueba de 5 segundos

### Recomendaciones:
- El commit `f13ce3f` debe separarse en commits por iniciativa en el futuro para evitar contaminación cruzada
- El cambio uncommitted en `api.js` (Yego Pro Profitability) debe ser commiteado por su equipo correspondiente
- Considerar agregar `drivers_operational_priorities` al array `DRIVER_KEYS` en DriverOperatingHub.jsx si se quiere que cuente para métricas de governance
