# DRIVERS INTELLIGENCE + EXECUTION OS — FASE H3.1

**Fecha:** 2026-05-26
**Fase activa:** 1H.4 — Operational Maturity Governance Layer (Control Foundation)
**Sub-fase:** H3.1 — Reordering into Intelligence + Execution OS

---

## 1. NUEVA VISIÓN

Drivers deja de verse como tabs sueltas y pasa a ser un **Driver Intelligence + Execution Operating System** organizado en 4 capas que conversan:

```
┌─────────────────────────────────────────────────┐
│               COMMAND CENTER                     │
│             Supply Overview                      │
└─────────────────────────────────────────────────┘
          │                        │
          ▼                        ▼
┌────────────────────┐  ┌─────────────────────────┐
│  INTELLIGENCE       │  │  EXECUTION & CAMPAIGNS  │
│  ────────────────   │  │  ─────────────────────  │
│  Analiza y prioriza │  │  Ejecuta y mide         │
│                     │  │                         │
│  Lifecycle Intel    │  │  Action Queues          │
│  Supply Diagnostics │  │  Operational Pilot      │
│  Behavioral Intel   │  │  Workflows              │
│  Behavioral Patterns│  │  Campaign Intelligence  │
│  Fleet & Leakage    │  │  CRM Bridge             │
│  Loyalty & Recov    │  │  Campaign Effectiveness │
│  Operational Intel  │  │                         │
└────────────────────┘  └─────────────────────────┘
          │                        │
          ▼                        ▼
┌─────────────────────────────────────────────────┐
│          FOUNDATION & GOVERNANCE                 │
│     Data Foundation · Health · Governance        │
└─────────────────────────────────────────────────┘
```

---

## 2. QUÉ ES DRIVERS

Un sistema operacional de dos capas que conversan:

- **Analytical Intelligence Layer:** Detecta patrones, segmenta, explica y prioriza conductores.
- **Execution & Campaign Layer:** Convierte prioridades en acciones, campañas y medición de outcomes.

Ambas capas se alimentan de los mismos serving facts y comparten el mismo modelo de datos. La Intelligence Layer genera cohorts accionables; la Execution Layer las ejecuta.

---

## 3. QUÉ NO ES DRIVERS

- No es un CRM
- No es un dashboard de reporting
- No es un motor de IA
- No es un sistema de automatización
- No sustituye a un call center
- No es un módulo aislado del resto del Control Tower

---

## 4. ANALYTICAL INTELLIGENCE LAYER

**Propósito:** Detectar, explicar, segmentar y priorizar.

| Capability | Descripción | Maturity |
|-----------|-------------|----------|
| Lifecycle Intelligence | Ciclo de vida, cohorts, retention, churn | Under Construction |
| Supply Diagnostics | Diagnóstico determinista de riesgo y leakage | Under Construction |
| Behavioral Intelligence | Benchmarking TOP vs DECLINING vs AT_RISK | Ready Next |
| Behavioral Alerts | Alertas de desviación conductual vs baseline | Ready Next |
| Behavioral Patterns | Patrones operativos diferenciales entre grupos | Ready Next |
| Fleet & Leakage Intelligence | Monitoreo de fuga de flota | Under Construction |
| Loyalty & Recoverability | Scoring de recuperabilidad (shadow mode) | Blocked |
| Operational Intelligence | Inteligencia operacional profunda | Future |

---

## 5. EXECUTION & CAMPAIGN LAYER

**Propósito:** Allana ejecución, crea campañas, sincroniza con CRM y mide outcomes.

| Capability | Descripción | Maturity |
|-----------|-------------|----------|
| Action Queues | Colas accionables con quick actions y workflow | Hardening |
| Operational Pilot | Piloto con 5 operadores humanos | Hardening |
| Operational Workflows | Gestión multi-step de casos (placeholder) | Under Construction |
| Campaign Intelligence | Análisis de campañas (placeholder) | Ready Next |
| CRM Bridge | Sincronización con CRM externo (placeholder) | Blocked |
| Campaign Effectiveness | Medición de outcomes de campañas (placeholder) | Future |

---

## 6. COMMAND CENTER

| Capability | Descripción | Maturity |
|-----------|-------------|----------|
| Supply Overview | Dinámicas de supply, segmentación, migración | Hardening |

El Command Center es la vista de control operacional que unifica la visión de ambas capas.

---

## 7. FOUNDATION & GOVERNANCE

| Capability | Descripción | Maturity |
|-----------|-------------|----------|
| Data Foundation | Inspección de fuentes, freshness, phone coverage | Hardening |
| Operational Health | Health checks de servicios Drivers | Hardening |
| Capability Governance | Mapa de madurez, roadmap, dependencias | Hardening |

---

## 8. CÓMO CONVERSA ANALYTICS CON EXECUTION

1. **Intelligence Layer detecta** — Un conductor entra en AT_RISK (lifecycle) o tiene una caída de comportamiento (behavioral alerts).
2. **Action Queues prioriza** — El driver aparece en la cola AT_RISK_DRIVERS con prioridad CRITICAL si tiene teléfono.
3. **Pilot Workboard asigna** — El cohorte se distribuye entre 5 operadores.
4. **Operador ejecuta** — Contacta al driver, registra resultado via quick actions.
5. **Workflow registra** — Cada acción queda en el action log.
6. **CRM Bridge sincroniza** — (futuro) El CRM externo recibe el estado.
7. **Campaign Effectiveness mide** — (futuro) Se calcula recovery rate por campaña.

---

## 9. QUÉ CONSUME EL CRM (FUTURO)

- Lista de drivers con teléfono y prioridad
- Estado del workflow (contactado, no respuesta, recuperado)
- Historial de acciones
- Cohortes activas

---

## 10. QUÉ VUELVE DEL CRM (FUTURO)

- Confirmación de contacto
- Resultado de campaña
- Feedback del driver
- Métricas de efectividad por canal

---

## 11. ROADMAP H3.2-H3.5

| Fase | Objetivo |
|------|----------|
| H3.2 | Campaign Intelligence — análisis de efectividad de campañas piloto |
| H3.3 | CRM Bridge — sincronización bidireccional |
| H3.4 | Campaign Effectiveness — medición de outcomes y ROI |
| H3.5 | Full Execution OS — workflows multi-step, campañas automatizadas |

---

## 12. GO/NO-GO

### GO (reorganización completada):
- [X] Todas las tabs existentes preservadas
- [X] Ninguna ruta rota
- [X] Labels actualizados sin cambiar rutas
- [X] 4 capas visibles en el header
- [X] Capability Group Cards funcionales
- [X] Placeholders gobernados para nuevas capabilities
- [X] Maturity badges preservados
- [X] Backend compile + Frontend build PASS

---

**FIN DEL DOCUMENTO H3**
