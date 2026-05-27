# DRIVERS OPERATIONAL PILOT — FASE H2

**Fecha:** 2026-05-26
**Fase activa:** 1H.4 — Operational Maturity Governance Layer (Control Foundation)
**Sub-fase:** H2 — Real Operations Pilot Preparation

---

## 1. OBJETIVO DEL PILOTO

Validar si el Driver Operating System permite a operadores humanos gestionar supply de conductores de forma efectiva. 5 personas de operaciones usarán Drivers durante varios días para contactar, recuperar y activar conductores.

**NO es un test de software.** Es una validación operativa del modelo de queues accionables.

---

## 2. ALCANCE RECOMENDADO

El sistema recomienda automáticamente el scope vía `GET /drivers/pilot-readiness`. Basado en datos disponibles:

- **País/Ciudad:** Sin restricción (todos disponibles)
- **Parks:** Todos
- **Queues:** AT_RISK_DRIVERS + REGISTERED_NO_FIRST_TRIP (las de mayor volumen con phone)
- **Máximo:** 100 drivers por cohorte
- **Filtro:** Solo drivers con teléfono (contactables)

Ejemplo de scope recomendado:
```
"Empezar con todos los parks / AT_RISK + REGISTERED_NO_FIRST_TRIP / 100 drivers máx"
```

---

## 3. PERFIL DE LOS 5 OPERADORES

| Operador | Rol sugerido |
|----------|-------------|
| Operador 1 | Prioridad en casos CRITICAL y HIGH |
| Operador 2 | Prioridad en casos CRITICAL y HIGH |
| Operador 3 | Casos MEDIUM, balance general |
| Operador 4 | Casos MEDIUM, balance general |
| Operador 5 | Casos MEDIUM y soporte a follow-ups |

La distribución es automática (`balanced_by_priority`): cada operador recibe una mezcla proporcional de prioridades y queue_types.

---

## 4. RUTINA DIARIA

### Para cada operador, cada día:

1. **Abrir Action Queues** filtrando por tu owner
2. **Revisar casos pendientes** — priorizar CRITICAL > HIGH > MEDIUM
3. **Contactar al siguiente driver**:
   - Llamada telefónica (preferido para AT_RISK y CRITICAL)
   - WhatsApp (para REGISTERED_NO_FIRST_TRIP y MEDIUM priority)
4. **Registrar resultado** usando quick actions:
   - `Contacted` → si respondió
   - `No Response` → si no contestó
   - `Recover` → si el driver aceptó volver/activarse
   - `Close` → si el caso está resuelto o no procede
5. **Si teléfono inválido:** Registrar en Learning Log como `bad_phone`
6. **Si el driver da feedback:** Registrar en Learning Log como `driver_feedback`
7. **Al final del día:** Revisar pendientes, dejar follow-ups

### NO hacer:
- No inventar datos
- No contactar al mismo driver dos veces el mismo día
- No presionar al driver
- No prometer incentivos (a menos que esté autorizado)

---

## 5. REGLAS DE REGISTRO

| Qué registrar | Dónde | Campo |
|---------------|-------|-------|
| Contacto exitoso | Quick Action: `Contacted` | `ops.driver_supply_action_log` |
| No respondió | Quick Action: `No Response` | `ops.driver_supply_action_log` |
| Driver recuperado | Quick Action: `Recover` | `ops.driver_supply_action_log` |
| Caso cerrado | Quick Action: `Close` | `ops.driver_supply_action_log` |
| Teléfono inválido | Learning Log: `bad_phone` | `ops.driver_pilot_learning_log` |
| Cola incorrecta (driver no encaja) | Learning Log: `wrong_queue` | `ops.driver_pilot_learning_log` |
| Feedback del driver | Learning Log: `driver_feedback` | `ops.driver_pilot_learning_log` |
| Problema técnico | Learning Log: `system_issue` | `ops.driver_pilot_learning_log` |

---

## 6. MÉTRICAS

Disponibles en `GET /drivers/pilot/metrics` y en el Pilot Workboard:

| Métrica | Definición | Umbral esperado |
|---------|-----------|-----------------|
| Assigned total | Casos asignados en el cohort | 50-100 |
| Contact rate | % de casos contactados vs no pendientes | > 50% |
| Recovery rate | % de casos recuperados vs contactados | > 20% |
| Invalid phone rate | % de casos bloqueados por teléfono inválido | < 30% |
| Outcomes by owner | Distribución por operador | Balanceado |
| Outcomes by queue | Distribución por tipo de cola | Variado |

**No atribuir causalidad todavía.** Solo observar.

---

## 7. CRITERIOS GO/NO-GO

### GO (el piloto fue útil):
- [ ] Al menos 3/5 operadores completaron la rutina diaria
- [ ] Contact rate > 40%
- [ ] Al menos 5 recoveries reales documentadas
- [ ] Learning log tiene > 10 observaciones útiles
- [ ] Los operadores reportan que las queues son accionables
- [ ] El sistema no tuvo caídas ni bloqueos

### NO-GO (no seguir con el modelo actual):
- [ ] < 20% de los drivers tenían teléfono válido
- [ ] Los operadores no entendieron qué hacer
- [ ] Las queues estaban mayormente vacías o mal clasificadas
- [ ] El sistema falló repetidamente
- [ ] 0 recoveries documentadas

---

## 8. APRENDIZAJES ESPERADOS

1. **¿Son accionables las queues?** ¿Los casos tienen sentido operativo?
2. **¿Phone coverage es suficiente?** ¿Cuántos teléfonos son inválidos?
3. **¿Las prioridades son correctas?** ¿CRITICAL realmente merece prioridad sobre HIGH?
4. **¿Los operadores entienden el flujo?** ¿Necesitan más guía o menos?
5. **¿Qué queues faltan?** ¿Qué tipo de caso no está cubierto?
6. **¿El sistema es estable?** ¿Hay caídas, timeouts o bugs?

---

## 9. QUÉ NO EVALUAR TODAVÍA

- ROI financiero del piloto
- Comparación con grupo de control (sin datos suficientes)
- Scoring probabilístico de recuperabilidad
- Automatización de contactos (email, SMS, bots)
- Forecast de churn
- Efectividad comparativa entre operadores (muestra muy pequeña)

---

## 10. CÓMO DECIDIR LA SIGUIENTE ITERACIÓN

Al finalizar el piloto (5-10 días):

1. **Revisar métricas** en `GET /drivers/pilot/metrics`
2. **Leer Learning Log** completo
3. **Entrevistar a los 5 operadores** (5-10 min cada uno)
4. **Identificar top 3 mejoras** basadas en feedback
5. **Decidir:**
   - Si GO → iterar H3 con mejoras + más operadores + más queues
   - Si NO-GO → ajustar modelo de queues, mejorar phone coverage, simplificar UX
   - Si parcial → mantener queues que funcionaron, eliminar las que no

---

## 11. ENDPOINTS H2

| Método | Ruta | Propósito |
|--------|------|-----------|
| GET | `/drivers/pilot-readiness` | Evaluar readiness del sistema para piloto |
| POST | `/drivers/pilot/cohort-preview` | Previsualizar cohorte sin persistir |
| POST | `/drivers/pilot/cohort` | Crear cohorte congelada en DB |
| POST | `/drivers/pilot/assign` | Distribuir casos entre N operadores |
| GET | `/drivers/pilot/metrics` | Métricas descriptivas del piloto |
| POST | `/drivers/pilot/learning-log` | Registrar observación operativa |
| GET | `/drivers/pilot/learning-log` | Consultar observaciones registradas |

---

## 12. TABLAS CREADAS

| Tabla | Schema | Propósito |
|-------|--------|-----------|
| `ops.driver_pilot_cohort` | Cohorte congelada de drivers para el piloto |
| `ops.driver_pilot_assignment` | Asignación de casos a operadores |
| `ops.driver_pilot_learning_log` | Registro de observaciones operativas |

---

**FIN DEL DOCUMENTO H2**
