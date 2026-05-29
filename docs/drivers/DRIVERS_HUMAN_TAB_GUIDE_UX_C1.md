# Drivers — Human Tab Guide (UX-C1)

## 1. Problema Detectado

Los usuarios (operadores, supervisores) abren pestañas de Drivers sin saber:
- ¿Para qué entro aquí?
- ¿Qué debo mirar?
- ¿Qué hago después?

18 subpestañas sin contexto humano generan confusión y abandono.

## 2. Principio de Guía Humana

Cada pestaña debe responder tres preguntas en menos de 5 segundos:
1. **Propósito**: ¿Qué logro aquí?
2. **Uso**: ¿Cómo lo uso?
3. **Decisión**: ¿Qué puedo decidir con esto?

La guía es:
- Compacta (1 línea visible, expandible)
- Colapsable (no ocupa espacio si no se necesita)
- Contextual (diferente por tab)
- Humana (sin jerga técnica)

## 3. Copy por Subpestaña

### Command Center
| Tab | Propósito |
|-----|-----------|
| Supply Overview | Cómo evoluciona el supply de conductores semana a semana |

### Intelligence
| Tab | Propósito |
|-----|-----------|
| Lifecycle Intelligence | En qué etapa del ciclo de vida está cada conductor |
| Supply Diagnostics | Diagnóstico de brechas en la flota |
| Behavioral Intelligence | Comportamiento vs. benchmark del segmento |
| Behavioral Alerts | Cambios abruptos de comportamiento |
| Fleet & Leakage | Dónde se fuga la flota |
| Behavioral Patterns | Patrones recurrentes de operación |
| Loyalty & Recoverability | Qué tan recuperable es un conductor inactivo |
| Operational Intelligence | Métricas operativas consolidadas |

### Execution
| Tab | Propósito |
|-----|-----------|
| Action Queues | Qué conductores accionar primero y por qué |
| Operational Pilot | Probar estrategias antes de escalar |
| Operational Workflows | Gestionar flujo de trabajo por caso |
| Campaign Intelligence | Crear campañas desde segmentos accionables |
| CRM Bridge | Exportar listas al CRM y recibir resultados |
| Campaign Effectiveness | Resultado observado post-campaña |

### Foundation
| Tab | Propósito |
|-----|-----------|
| Data Foundation | ¿Los datos están frescos y completos? |
| Operational Health | ¿Los servicios funcionan correctamente? |
| Capability Governance | ¿Qué capacidades están maduras? |

## 4. Audiencia por Tab

| Audiencia | Tabs principales |
|-----------|-----------------|
| Operador | Action Queues, Operational Pilot, Workflows, Campaign Intelligence, CRM Bridge |
| Supervisor | Supply, Lifecycle, Action Queues, Campaign Intelligence, CRM Bridge, Effectiveness |
| Estrategia | Supply, Lifecycle, Behavioral, Recoverability, Effectiveness |
| Admin/Data | Data Foundation, Operational Health, Capability Governance |

## 5. Qué Decisión Permite Cada Tab

| Tab | Decisión |
|-----|----------|
| Supply Overview | ¿La base crece o se deteriora? |
| Lifecycle Intelligence | ¿Hay más dormidos que activos? |
| Behavioral Alerts | ¿Hay conductores valiosos que cayeron? |
| Action Queues | ¿A quién contacto primero? |
| Campaign Intelligence | ¿El universo es viable para campaña? |
| CRM Bridge | ¿El CRM recibió la lista? |
| Campaign Effectiveness | ¿La campaña tuvo efecto? ¿Repito? |
| Data Foundation | ¿Puedo confiar en los datos? |

## 6. Implementación Técnica

### Archivos creados
- `frontend/src/config/driverTabGuideRegistry.js` — Registry con copy por tab
- `frontend/src/components/driver/DriverTabGuide.jsx` — Componente reutilizable

### Integración
- Inyectado en `DriverOperatingHub.jsx` antes del contenido
- Aparece automáticamente en TODAS las subpestañas
- No requiere modificar cada componente individual

### Tooltips en navegación
- Cada pill de subtab muestra tooltip con propósito + decisión al hover
- Implementado en `App.jsx` vía `subPillSimple`

### Noise Reduction
- Términos técnicos reemplazados en vistas operativas:
  - "outcomes" → "resultados del contacto"
  - "members" → "conductores en campaña"
  - "effectiveness" → "resultado observado"
  - "freshness" → "actualización de data"
  - "serving fact" → "fuente operativa"

## 7. QA

- [x] Frontend build exitoso
- [x] Todas las tabs siguen visibles
- [x] Cada tab tiene guía humana
- [x] Guía es colapsable
- [x] No se rompió routing
- [x] No se tocaron endpoints
- [x] Supply sigue cargando
- [x] Campaigns intacto
- [x] CRM Bridge intacto
