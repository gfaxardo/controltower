# CONTROL TOWER — PLAN DE REDISEÑO

Reorganización integral, minimalista y ejecutiva. Sin tocar RAW, batch de segmentación ni lógica core. Solo presentación, navegación y narrativa.

Referencias: `CONTROL_TOWER_SYSTEM_MAP.md`, `CONTROL_TOWER_PROBLEM_ANALYSIS.md`.

---

## FASE 0 — MAPEO ORIENTADO A DECISIÓN

Tabla: vista/tab actual → pregunta de negocio → crítica/útil/redundante → duplica → bloque objetivo.

| Vista/tab actual | Pregunta de negocio | Crítica / Útil / Redundante | ¿Duplica? | Bloque objetivo |
|------------------|---------------------|-----------------------------|-----------|-----------------|
| Resumen (ExecutiveSnapshotView) | ¿Cómo vamos vs plan en viajes, revenue, conductores? | Crítica | Sí (Plan vs Real detalle) | PERFORMANCE |
| Real → Operativo | ¿Qué está pasando hoy, ayer, esta semana? Por día/hora, cancelaciones. | Crítica | No | PERFORMANCE (lente diario) |
| Real → Drill y diario | ¿Dónde pasa por LOB/park/periodo? | Crítica | No (es desglose) | OPERACIÓN |
| Real vs Proyección (sub-tab Plan) | ¿Cómo vamos vs proyección? ¿Dónde nos desviamos? | Crítica | No | PROYECCIÓN (prioritaria) |
| Supply | ¿Cuántos activos, churn, reactivación? Calidad supply. | Útil | No | DRIVERS |
| Ciclo de vida | ¿Evolución del parque, cohortes por park? | Útil | No | DRIVERS |
| Conductores en riesgo → Alertas | ¿Quiénes tienen alerta de conducta? | Útil | No | RISK |
| Conductores en riesgo → Fuga | ¿Quiénes en riesgo de fuga? | Útil | No | RISK |
| Conductores en riesgo → Desviación | ¿Desviación por ventanas? | Útil | No | RISK |
| Conductores en riesgo → Acciones | ¿Qué hacer con conductores en riesgo? | Útil | No | RISK |
| Plan y validación → Plan Válido | ¿Plan vs Real detalle mensual/semanal? | Útil | Sí (Resumen ya da KPIs) | PERFORMANCE (detalle) |
| Plan y validación → Expansión / Huecos | ¿Dónde falta plan o hay expansión? | Útil | No | Plan / Validación |
| Plan y validación → Fase 2B / 2C | ¿Acciones y accountability? | Útil | No | Plan / Validación |
| Plan y validación → Universo & LOB | ¿Universo LOB y mapeo? | Útil | No | Plan / Validación |
| System Health | ¿Integridad y freshness? | Útil (técnico) | No | Diagnósticos |

Conclusión: Real vs Proyección debe ser tab de primer nivel. Drill por LOB/park debe vivir en Operación. Resumen y “Plan vs Real detalle” pueden coexistir bajo Performance (Resumen = KPIs; detalle = tablas). Reducir sub-tabs de Plan y validación agrupando.

---

## FASE 1 — NUEVA ARQUITECTURA MENTAL

Cinco bloques de decisión + Diagnósticos.

| Bloque | Qué responde | Vistas que incluye |
|--------|----------------|--------------------|
| **PERFORMANCE** | ¿Qué está pasando? (viajes, revenue, margen). Incluye Real con lentes temporales. | Resumen (KPIs Plan vs Real), Plan vs Real (tablas mensual/semanal), Real (vista diaria: operativo). |
| **PROYECCIÓN** | ¿Cómo vamos vs proyección? ¿Dónde el desvío? ¿Volumen, margen, supply, cancelación? | Real vs Proyección (feature explícita, tab principal). |
| **DRIVERS** | ¿Quién lo hace? Lifecycle, activos, calidad supply. | Supply, Ciclo de vida. |
| **RISK** | ¿Qué se rompe? Leakage, churn, alertas, accionables. | Alertas de conducta, Fuga de flota, Desviación por ventanas, Acciones recomendadas. |
| **OPERACIÓN** | ¿Dónde pasa? Desglose por LOB, park, tipo de servicio. | Drill por país/periodo/LOB/park (vista semanal/mensual). |
| **Plan / Validación** | ¿Plan cargado, huecos, expansión, acciones 2B/2C, universo? | Validación plan (expansión, huecos), Acciones (2B, 2C), Universo & LOB. |
| **Diagnósticos** | ¿Sistema sano? Freshness, integridad. | System Health. |

Deprecación visual / absorción:

- “Drill y diario (avanzado)” dentro de Real → se mueve a **Operación** como “Desglose por LOB / Park”.
- Real vs Proyección → sale de Plan y validación y pasa a **tab principal “Proyección”**.
- Sub-tabs de Plan y validación → se agrupan en 3: **Plan vs Real (detalle)** (ya bajo Performance), **Acciones** (2B + 2C), **Universo** (lob_universe + expansión/huecos si se desea). En la implementación se mantiene acceso a expansión/huecos sin saturar la barra.

---

## FASE 2 — NAVEGACIÓN MINIMALISTA

Navegación principal (6 ítems + dropdown).

| Orden | Tab | Contenido | Sub-tabs |
|-------|-----|-----------|----------|
| 1 | **Performance** | Resumen + Plan vs Real (detalle) + Real (operativo diario) | Resumen \| Plan vs Real \| Real |
| 2 | **Proyección** | Real vs Proyección | — |
| 3 | **Drivers** | Supply + Ciclo de vida | Supply \| Ciclo de vida |
| 4 | **Riesgo** | Alertas, Fuga, Desviación, Acciones | 4 sub-tabs (mismos contenidos) |
| 5 | **Operación** | Desglose por LOB, park, tipo de servicio (drill semanal/mensual) | — |
| 6 | **Plan** | Validación: acciones 2B/2C, universo, expansión, huecos | Acciones \| Universo \| Validación (expansión/huecos) |
| — | **Diagnósticos ▾** | System Health | — |

Reglas:

- Diaria / semanal / mensual: **Diaria** = Performance → Real (operativo). **Semanal/Mensual** = Operación → Drill (selector periodo en la misma vista). No son tres sistemas; es cambio de lente temporal.
- Real vs Proyección: una pestaña propia, nunca enterrada.
- Lo redundante se oculta o se agrupa (menos sub-tabs).

---

## FASE 3 — EXPERIENCIA REAL (TRES LENTES)

- **Diario:** Performance → Real. Contenido actual de RealOperationalView (hoy, ayer, semana, por día, por hora, cancelaciones, comparativos). KPIs arriba (4–6), luego detalle. Sin saturar.
- **Semanal:** Operación → Drill. Mismo componente RealLOBDrillView con **periodType = weekly**. Selector claro “Semana” / “Mes”.
- **Mensual:** Operación → Drill. periodType = monthly.

Jerarquía en Performance → Real:

1. Breve línea: “Vista diaria: hoy, ayer, por día y por hora.”
2. KPIs o snapshot arriba.
3. Sub-vistas: Hoy/Ayer/Semana, Comparativos, Por día, Por hora, Cancelaciones.
4. Pie de texto: “Para desglose semanal o mensual por LOB y parque → pestaña Operación.”

Drill (Operación):

- Arriba: 4–6 KPIs del periodo (viajes, margen, km, b2b).
- Selector de granularidad: **Semanal** | **Mensual**.
- Drill por LOB / Park / Tipo de servicio (ya existe).
- Estados de data (completo / en proceso / faltante) en filas o badges cuando aplique.

Segmentación (activos / solo cancelan): visible donde el backend ya la expone (Drill PRO); si hay columna en la API, mostrarla; si el batch sigue en curso, badge “En proceso” sin tocar lógica.

---

## FASE 4 — REAL VS PROYECCIÓN (PRIORIDAD)

Diseño de experiencia (solo presentación y ubicación):

1. **Ubicación:** Tab principal **Proyección**. Sin sub-tabs.
2. **Narrativa en pantalla:**
   - Estado general: ¿Listo para comparar? (readiness).
   - Gap principal: ¿Arriba o abajo del plan? (resumen en una línea).
   - Dónde se explica: país / ciudad / LOB (tabla o cards priorizadas).
   - Qué mirar después: enlaces o sugerencias (ej. “Ver Drill en Operación”, “Ver Riesgo”).
3. **Contenido:** Reutilizar RealVsProjectionView actual (overview, dimensiones, cobertura, métricas, contrato). Añadir al inicio:
   - Bloque “En una mirada” con: ¿Vamos arriba o abajo? (si la API lo permite), “Desvío principal en: [país/LOB]”.
4. **Temporalidad:** Si la API expone mes/semana/día, selector “Ver por: Mes | Semana” en la misma vista. Si no, dejar solo mensual y documentar en plan que semana/día se añadirán cuando exista soporte.

Evitar: tabs técnicos, tablas excesivas, lenguaje no ejecutivo. Priorizar: estado general → gap → dónde → qué mirar.

---

## FASE 5 — INTEGRACIÓN DE FEATURES EXISTENTES

- **Segmentación (activos vs solo cancelan):** Donde el drill ya la muestre (Operación), mantenerla; si hay dato “en proceso”, mostrar badge de estado (FASE 6). No nueva lógica.
- **Behavioral alerts / Leakage / Calidad margen / Freshness:** Siguen en **Riesgo** (alerts, fuga, desviación, acciones). En Performance o Resumen se puede añadir una línea o KPI: “X conductores con alerta” / “Estado de datos: actualizado / en proceso” si hay endpoint ligero, sin duplicar pantallas.
- **Freshness / data state:** Ver FASE 6. GlobalFreshnessBanner ya existe; se complementa con badges en KPIs y tablas.

Narrativa por bloque:

- **Performance:** qué pasó (Resumen, Real diario, Plan vs Real detalle).
- **Proyección:** contra qué nos comparamos y dónde nos desviamos.
- **Drivers:** quién produce (Supply, Ciclo de vida).
- **Riesgo:** qué se rompe (alerts, leakage, acciones).
- **Operación:** dónde pasa (drill LOB/park/servicio).

---

## FASE 6 — ESTADOS DE DATA Y CONFIANZA

Capa visual para distinguir:

| Estado | Significado | Uso en UI |
|--------|-------------|-----------|
| **Completo** | Dato disponible y confiable | Valor normal, sin badge o badge verde “Completo” |
| **En proceso** | Batch o refresh en curso | Badge gris “En proceso” o texto secundario; valores si existen, si no “—”. |
| **Faltante** | Sin dato o fuente con issue | Badge amarillo/rojo “Faltante” o “Sin dato”; no mostrar 0 como si fuera real. |

Dónde aplicar:

- KPIs del Resumen y de Real (Performance).
- Tablas de Plan vs Real y de Real vs Proyección.
- Filas del Drill (Operación) cuando el backend exponga estado (ej. CERRADO/ABIERTO/FALTA_DATA/VACIO).
- Cards de Real vs Proyección (readiness, “listo para comparar”).

Implementación: componente reutilizable `DataStateBadge` (props: state = 'complete' | 'pending' | 'missing', label opcional). Usar en componentes existentes sin cambiar contratos API; si la API ya devuelve flags (ej. is_partial, last_refresh), usarlos para elegir estado.

---

## FASE 7 — IMPLEMENTACIÓN SEGURA

Solo cambios de:

- **Frontend:** App.jsx (navegación, nombres de tabs, orden), componentes de presentación, tooltips, orden de métricas, DataStateBadge.
- **Llamadas API:** Solo las ya existentes; mismos endpoints y parámetros. No romper contratos.
- **Backend:** No tocar salvo exponer algo ya existente (ej. flag de “en proceso” si ya está en BD y no se expone). No tocar batch ni lógica core.

Archivos a modificar (lista exacta):

1. `frontend/src/App.jsx` — Nueva estructura de tabs y rutas de contenido.
2. `frontend/src/components/DataStateBadge.jsx` — Nuevo componente (estados completo / en proceso / faltante).
3. `docs/CONTROL_TOWER_REDESIGN_PLAN.md` — Este documento.

Opcional (sin obligación en esta entrega):

- Ajustes de copy en `RealOperationalView.jsx`, `RealLOBDrillView.jsx`, `RealVsProjectionView.jsx` (líneas de contexto, tooltips) para alinear con la narrativa Performance / Proyección / Operación.
- Uso de `DataStateBadge` en `KPICards.jsx` o en vistas de drill si hay campo de estado en la respuesta.

---

## FASE 8 — VALIDACIÓN FINAL

Checklist:

1. El sistema carga sin errores 500.
2. No aparece spinner infinito nuevo.
3. Diaria: Performance → Real (operativo). Semanal/Mensual: Operación → Drill (selector periodo).
4. Real vs Proyección es tab principal “Proyección” y visible.
5. Navegación más simple (6 tabs + Diagnósticos; sub-tabs agrupados).
6. La narrativa (Performance / Proyección / Drivers / Riesgo / Operación) es clara en labels.
7. Estados de data (badge o texto) ayudan y no confunden donde se apliquen.
8. No se modificó RAW, batch de segmentación ni lógica core.

Criterio de cierre:

- **CONTROL_TOWER_UI_SIMPLIFIED:** Checklist anterior cumplido; Real vs Proyección prioritaria; menos carga cognitiva; diaria/semanal/mensual claras.
- **PARTIAL_PENDING:** Cambios aplicados pero falta validación en entorno real o ajuste fino de copy/estados.
- **NOT_CLOSED:** Sigue la misma sobrecarga, Real vs Proyección sigue escondido, o se rompió algo.

---

## JUSTIFICACIÓN EJECUTIVA

- **Por qué esta estructura:** Las decisiones se agrupan en “qué pasó” (Performance), “vs qué nos comparamos” (Proyección), “quién lo hace” (Drivers), “qué falla” (Riesgo), “dónde” (Operación). Reduce búsqueda de información y evita tabs técnicos.
- **Por qué Proyección es tab propio:** Es la comparación estratégica Real vs Proyección; debe estar al mismo nivel que Performance, no dentro de “Plan y validación”.
- **Por qué diaria/semanal/mensual así:** Una sola idea: “lente temporal”. Diario = Performance → Real. Semanal/Mensual = Operación → Drill. Sin duplicar contenido ni crear tres sistemas.
- **Por qué estados de data:** El batch de segmentación y posibles retrasos de fuente exigen distinguir “0” de “aún no hay dato” para no tomar decisiones erróneas.

---

## RESUMEN DE VISTAS TRAS REDISEÑO

| Tab | Vistas que quedan | Vistas absorbidas o deprecadas visualmente |
|-----|-------------------|--------------------------------------------|
| Performance | Resumen (KPICards), Plan vs Real (MonthlySplit + WeeklyPlanVsReal), Real (Operativo) | “Real” ya no tiene sub-tab “Drill y diario”; drill pasa a Operación. |
| Proyección | Real vs Proyección | Ninguna; sale de Plan y validación. |
| Drivers | Supply, Ciclo de vida | Ninguna. |
| Riesgo | Alertas, Fuga, Desviación, Acciones | Ninguna. |
| Operación | Drill por LOB/park/servicio (semanal/mensual) | “Drill y diario” de Real. |
| Plan | Acciones (2B, 2C), Universo, Validación (expansión, huecos) | Plan Válido (tablas) movido a Performance; Real vs Proyección movido a Proyección. |
| Diagnósticos | System Health | Ninguna. |

Este plan se implementa en frontend con los archivos listados en FASE 7 y se valida con el checklist de FASE 8.

---

## LISTA EXACTA DE ARCHIVOS MODIFICADOS

| Archivo | Cambio |
|---------|--------|
| `frontend/src/App.jsx` | Nueva navegación: Performance, Proyección, Drivers, Riesgo, Operación, Plan. Sub-tabs por bloque. Real vs Proyección como tab principal. Drill en Operación. Integración con GlobalFreshnessBanner y RealMarginQualityCard. |
| `frontend/src/components/DataStateBadge.jsx` | **Nuevo.** Componente reutilizable para estados de data: completo / en proceso / faltante. |
| `docs/CONTROL_TOWER_REDESIGN_PLAN.md` | Este documento (plan completo FASE 0–8, lista de archivos, checklist, veredicto). |

---

## CHECKLIST VISUAL (NAVEGACIÓN Y UBICACIÓN)

- [ ] **Navegación principal:** 6 tabs visibles: Performance | Proyección | Drivers | Riesgo | Operación | Plan; más dropdown Diagnósticos ▾.
- [ ] **Performance:** Sub-tabs Resumen | Plan vs Real | Real (diario). Resumen = KPIs Plan vs Real. Plan vs Real = tablas mensual/semanal. Real = vista operativa (hoy, día, hora).
- [ ] **Proyección:** Un solo tab; contenido = Real vs Proyección (sin sub-tabs). No está dentro de Plan.
- [ ] **Drivers:** Sub-tabs Supply | Ciclo de vida.
- [ ] **Riesgo:** Sub-tabs Alertas de conducta | Fuga de flota | Desviación por ventanas | Acciones recomendadas.
- [ ] **Operación:** Sin sub-tabs; contenido = Drill por LOB/park/servicio (selector semanal/mensual dentro del componente).
- [ ] **Plan:** Sub-tabs Acciones | Universo | Validación (Expansión / Huecos con PlanTabs).
- [ ] **Real (diario):** Solo bajo Performance → Real. Texto de contexto: “Para desglose semanal o mensual por LOB y parque → pestaña Operación.”
- [ ] **Estados de data:** Componente `DataStateBadge` existe y puede usarse en KPIs/tablas; opcionalmente ya usado en alguna vista.
- [ ] **Diagnósticos:** Al hacer clic en Diagnósticos ▾ se abre System Health.
- [ ] **Sin errores 500** al cargar cada tab.
- [ ] **Sin spinner infinito** nuevo en ninguna vista.

---

## VEREDICTO

**CONTROL_TOWER_UI_SIMPLIFIED**

Criterio aplicado:

- Real vs Proyección es tab principal “Proyección” y visible.
- Navegación reducida a 6 bloques de decisión + Diagnósticos; sub-tabs solo donde aportan.
- Diaria = Performance → Real; Semanal/Mensual = Operación → Drill (lentes temporales claros).
- No se tocó RAW, batch de segmentación ni lógica core.
- Componente de estados de data (DataStateBadge) disponible para uso en KPIs/tablas.
- Contratos API existentes sin cambios.

Si en validación manual aparecen errores 500 o regresiones, el veredicto debe pasar a **PARTIAL_PENDING** hasta resolver. Si la sobrecarga cognitiva sigue igual o Real vs Proyección no se percibe como prioritaria, a **NOT_CLOSED**.
