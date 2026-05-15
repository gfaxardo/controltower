# YEGO Control Tower — Límites y Contratos de Cada Motor

**Versión:** 1.0.0
**Fecha:** 2026-05-15
**Propósito:** Definir responsabilidades, inputs, outputs, exclusiones y ejemplos para cada motor arquitectónico. Este documento es vinculante para cualquier nueva implementación.

---

## 1. Control Foundation

### Responsabilidad
Centralizar la **verdad operacional** del negocio:
- Mostrar **Real** (lo que ocurrió): viajes, revenue, margen, km, conductores.
- Mostrar **Plan** (lo que se planeó): targets mensuales/semanales/diarios.
- **Comparar Plan vs Real** en todos los grains (monthly, weekly, daily).
- Garantizar **freshness** de datos (pipeline, watchdog, staleness alerts).
- Proveer **Omniview** (visión matricial unificada de métricas × dimensiones).
- Asegurar **grains consistentes** (daily → weekly → monthly auditables).
- Proveer **KPIs auditables** (trazabilidad fuente → vista → API → UI).

### Inputs
- Fuentes de datos operacionales: `trips_2026`, `v_trips_real_canon_120d`, `trips_2025`.
- Planes subidos: Excel/CSV con targets mensuales.
- Dimensiones: parks, cities, countries, LOB groups, service types.
- Taxonomy: segmentos (B2B/B2C), tipos de servicio, estados de viaje.

### Outputs
- Vistas y MVs en schema `ops`: `mv_real_*`, `v_plan_*`, `v_plan_vs_real_*`.
- Endpoints REST bajo `/ops/`, `/plan/`, `/real/`, `/core/`.
- UI: Executive Snapshot, Monthly/Weekly Plan vs Real, Real Operational, Omniview Matrix.
- Dashboards de freshness e integridad.

### Qué NO debe hacer
- **NO** predecir escenarios futuros sin base confiable. Eso es Forecast Engine.
- **NO** decidir campañas o intervenciones operativas. Eso es Decision Engine.
- **NO** ejecutar acciones automáticamente. Eso es Action Engine.
- **NO** aprender con IA ni optimizar con ML. Eso es Learning Engine / AI Copilot.
- **NO** generar sugerencias proactivas. Eso es Suggestion Engine.

### Ejemplos de Features Permitidas
- Agregar un nuevo KPI al Omniview Matrix (ej. `avg_driver_rating`).
- Migrar una vista legacy a fuente canónica hourly-first.
- Añadir un filtro por park_id en Real LOB Drill.
- Mejorar el pipeline de refresh para reducir staleness.
- Auditoría de integridad: trip loss, B2B, LOB mapping, duplicates.

### Ejemplos de Features Prematuras
- "Predecir viajes de la próxima semana basado en tendencia" → Debe esperar a Forecast Engine.
- "Sugerir aumentar flota en ciudad X porque el Plan vs Real muestra gap" → Debe esperar a Suggestion Engine.
- "Activar campaña automática de recuperación para conductores con baja actividad" → Debe esperar a Action Engine.
- "Entrenar modelo ML para optimizar asignación de conductores" → Debe esperar a AI Copilot + Learning Engine.

---

## 2. Diagnostic Engine

### Responsabilidad
**Explicar por qué** ocurren las desviaciones:
- Identificar **gaps** entre Plan y Real y explicar sus causas.
- **Descomponer** variaciones en drivers causales (precio, volumen, mix, estacionalidad).
- **Priorizar** causas por impacto (qué explica más % de la desviación).
- Proveer **explicabilidad** operativa (no solo "hay un gap", sino "el gap viene de...").

### Inputs
- Métricas de Control Foundation (Plan vs Real, KPIs, grains).
- Datos de dimensiones y segmentos.
- Baseline histórica para comparación.

### Outputs
- Informes de descomposición de gaps.
- Rankings de drivers causales por impacto.
- Vistas de diagnóstico (ej. waterfal de variación).
- API de diagnóstico (`/ops/diagnostics/*` o similar).

### Qué NO debe hacer
- **NO** ejecutar acciones correctivas. Eso es Action Engine.
- **NO** automatizar campañas basadas en diagnóstico.
- **NO** reemplazar la lógica de control. El diagnóstico explica, no corrige.
- **NO** predecir. El diagnóstico mira hacia atrás; Forecast mira hacia adelante.

### Ejemplos de Features Permitidas
- "El gap de -8% en revenue de Lima se explica 60% por caída de volumen B2C y 40% por mix desfavorable."
- Waterfall chart de variación Plan vs Real por dimensión.
- Detección de anomalías estructurales (cambio de tendencia sostenido).

### Ejemplos de Features Prematuras
- "Como el diagnóstico muestra caída en B2C, activar campaña de captación." → Action Engine.
- "Predecir que la caída continuará 3 semanas más." → Forecast Engine.

---

## 3. Reachability Engine

### Responsabilidad
Determinar **a qué conductores se puede llegar** y por qué canal:
- Mapear canales de contacto disponibles por conductor (push, SMS, email, in-app).
- Calcular **reachability score** (probabilidad de que un conductor vea/responda).
- Segmentar por canal óptimo según historial de engagement.
- Proveer infraestructura de contacto (sin ejecutar envíos).

### Inputs
- Registro de conductores con canales de contacto.
- Historial de engagement por canal.
- Preferencias y restricciones legales (opt-out, GDPR).

### Outputs
- Vista de reachability por conductor/segmento.
- API de canales disponibles.
- Scores de reachability.

### Qué NO debe hacer
- **NO** ejecutar envíos ni campañas. Eso es Action Engine.
- **NO** decidir qué mensaje enviar. Eso es Suggestion/Decision Engine.
- **NO** operar sin Control Foundation estable (necesita datos de conductores confiables).

### Estado Actual
**BACKLOG.** No iniciado. Depende de Control Foundation cerrado.

---

## 4. Forecast Engine

### Responsabilidad
**Proyectar escenarios futuros** con base en datos históricos:
- Proyectar viajes, revenue, margen por ciudad/segmento/día.
- Calcular **velocity** (ritmo de avance vs plan).
- Detectar **tendencias** (aceleración, desaceleración).
- Evaluar **plausibilidad** de alcanzar el plan (forecast vs target).
- Proyecciones semanales/diarias desde plan mensual (estacionalidad, smoothing).

### Inputs
- Historial de Control Foundation (Real histórico).
- Planes vigentes.
- Curvas de estacionalidad.
- Factores externos (festivos, eventos, clima — si están disponibles).

### Outputs
- Forecast diario/semanal/mensual por dimensión.
- Velocity metrics (run rate vs target).
- Confidence intervals de proyección.
- Alertas de desviación forecast vs plan.

### Qué NO debe hacer
- **NO** decidir acciones basadas en forecast. Eso es Decision Engine.
- **NO** modificar metas automáticamente. El plan lo define el negocio.
- **NO** reemplazar el Plan. Forecast proyecta; Plan es el target.

### Ejemplos de Features Permitidas
- "Al ritmo actual (velocity), el mes cerrará a 94% del plan de viajes."
- "La proyección semanal ajustada por estacionalidad estima 12,500 viajes para la semana 3."
- Confidence band: "El forecast tiene alta confianza para semana 1-2, baja para semana 4."

### Ejemplos de Features Prematuras
- "Como el forecast muestra gap, aumentar targets de adquisición." → Decision Engine.
- "Ajustar automáticamente el plan semanal según forecast." → No es rol del Forecast Engine.

### Nota sobre Implementación Parcial
El **Projection Integrity Engine** existente (`projection_integrity_service.py`, `seasonality_curve_engine.py`) es un **piloto técnico** de Forecast. No debe considerarse Forecast Engine completo hasta que:
1. Control Foundation esté cerrado.
2. Las proyecciones tengan validación de backtesting.
3. La confianza de proyección esté calibrada contra realidad.

---

## 5. Suggestion Engine

### Responsabilidad
**Proponer acciones trazables** basadas en evidencia:
- Generar sugerencias con **racional operativo** explícito (por qué esta acción).
- **Estimar impacto** esperado de cada sugerencia (viajes, revenue, margen).
- Ligar cada sugerencia a un **gap o diagnóstico** concreto.
- Mantener **trazabilidad**: gap → causa → sugerencia → impacto estimado.

### Inputs
- Gaps y diagnósticos (de Diagnostic Engine).
- Forecast y proyecciones (de Forecast Engine).
- Datos operacionales de Control Foundation.
- Catálogo de acciones posibles y sus impactos históricos.

### Outputs
- Lista de sugerencias con prioridad, racional e impacto estimado.
- API de sugerencias trazables.
- UI de recomendaciones (no ejecutables directamente).

### Qué NO debe hacer
- **NO** ejecutar acciones. Solo propone.
- **NO** priorizar globalmente sin Decision Engine. La sugerencia propone; Decision prioriza.
- **NO** usar IA como fuente única de verdad. Toda sugerencia debe tener trazabilidad determinística.
- **NO** generar sugerencias sin Forecast confiable.

### Ejemplos de Features Permitidas
- "Se sugiere campaña de recuperación en Lima B2C: impacto estimado +300 viajes/semana."
- "Se sugiere ajustar target semanal de auto en Cali: gap actual -12%, elasticidad histórica sugiere +8% alcanzable."
- "Se sugieren 3 acciones para cerrar gap de margen: (1) ajustar take rate, (2) incentivar B2B, (3) reducir cancelaciones."

### Ejemplos de Features Prematuras
- Implementar Suggestion Engine sin Forecast Engine validado.
- Usar solo IA generativa para sugerencias sin trazabilidad determinística.

---

## 6. Decision Engine

### Responsabilidad
**Priorizar el portafolio de decisiones** operativas:
- Evaluar sugerencias contra **constraints** (presupuesto, capacidad operativa, timing).
- Aplicar **costo-beneficio** para rankear decisiones.
- Resolver **conflictos** entre sugerencias (dos acciones que compiten por el mismo recurso).
- Emitir **decisiones vinculantes** (no sugerencias) con justificación explícita.
- Gobernar el paso a ejecución (qué se aprueba, qué se rechaza, qué se posterga).

### Inputs
- Sugerencias del Suggestion Engine.
- Constraints operativos (presupuesto, headcount, capacidad de flota).
- Reglas de negocio y políticas.
- Data trust signals (Confidence Engine, integridad de datos).

### Outputs
- Portafolio priorizado de decisiones.
- Decisiones aprobadas/rechazadas/postergadas con justificación.
- API de decisiones.
- Log de decisiones para auditoría.

### Qué NO debe hacer
- **NO** ejecutar directamente las decisiones. Eso es Action Engine.
- **NO** generar sugerencias. Eso es Suggestion Engine.
- **NO** decidir sin que Suggestion Engine haya generado opciones trazables.
- **NO** operar con datos no confiables (debe consultar Data Trust Layer).

### Ejemplos de Features Permitidas
- "De 5 sugerencias, se aprueban 3: campaña Lima B2C (prioridad 1), ajuste take rate Cali (P2), recall drivers inactivos (P3). Se rechaza expansión Bogotá (sin presupuesto). Se posterga incentivo B2B (esperar datos Q2)."
- Matriz de decisión con costo, beneficio esperado, riesgo y plazo.

### Ejemplos de Features Prematuras
- Implementar Decision Engine sin Suggestion Engine trazable.
- Decisiones automáticas sin supervisión humana en etapa temprana.

### Nota sobre Implementación Parcial
El `decision_engine.py` actual es una **capa de gobierno de confianza de datos** (`STOP_DECISIONS`, `LIMIT_DECISIONS`, etc.). Esto es correcto y debe mantenerse. Pero **no es el Decision Engine operacional completo**. La capa actual gobierna si se puede confiar en los datos para decidir; el Decision Engine futuro usará datos confiables para priorizar decisiones de negocio.

---

## 7. Action Engine

### Responsabilidad
**Gestionar la ejecución** de decisiones aprobadas:
- Traducir decisiones en **planes de acción** concretos (quién, qué, cuándo, cómo).
- Asignar **accountability** (owner, deadline, criterios de éxito).
- Soportar **rollback** y corrección de acciones en curso.
- Mantener **trazabilidad completa**: decisión → acción → ejecución → resultado.
- Medir **efectividad** post-ejecución (¿la acción logró el impacto esperado?).

### Inputs
- Decisiones aprobadas del Decision Engine.
- Playbooks de ejecución (cómo ejecutar cada tipo de acción).
- Segmentos de conductores/clientes objetivo.
- Recursos disponibles (equipos, herramientas, presupuesto).

### Outputs
- Plan de acción diario (`ops.action_plan_daily`).
- Log de ejecución (`ops.action_execution_log`).
- Métricas de efectividad post-acción.
- Dashboards de tracking de acciones.

### Qué NO debe hacer
- **NO** decidir por sí mismo qué acciones tomar. Eso es Decision Engine.
- **NO** generar sugerencias. Eso es Suggestion Engine.
- **NO** crear loops peligrosos (acción → efecto → reacción automática sin supervisión).
- **NO** ejecutar sin accountability clara (todo debe tener owner y deadline).

### Ejemplos de Features Permitidas
- Plan diario: "Contactar 50 conductores inactivos en Lima vía push, owner: equipo CRM, deadline: 2026-05-20."
- Tracking: "De 50 conductores contactados, 12 respondieron, 8 reactivados. Efectividad: 16%."
- Rollback: "Campaña de incentivo en Cali pausada por queja de conductores. Acción marcada como `cancelled` con razón."

### Ejemplos de Features Prematuras
- Action Engine sin Decision Engine previo → acciones sin priorización clara.
- Action Engine sin Suggestion Engine → acciones sin racional trazable.
- Automatización completa sin supervisión humana en etapas tempranas.

### Nota Crítica sobre phase2b_actions
**`ops.phase2b_actions` NO es el Action Engine.** Es una tabla de registro manual de seguimiento operacional (Control Foundation). El Action Engine real requiere:
1. Decision Engine operativo (priorización de portafolio).
2. Suggestion Engine trazable (racional de cada acción).
3. Playbooks de ejecución.
4. Ciclo completo: decisión → plan → ejecución → medición → aprendizaje.

El `action_engine_service.py` y `action_orchestrator_service.py` actuales son **prototipos técnicos**. No deben activarse como motor completo hasta que las dependencias estén resueltas.

---

## 8. AI Copilot

### Responsabilidad
Asistir al operador humano con **inteligencia aumentada**:
- Responder preguntas operativas en lenguaje natural ("¿por qué cayó el margen en Lima?").
- Generar resúmenes ejecutivos automáticos.
- Asistir en la navegación e interpretación de datos.
- Sugerir vistas y análisis relevantes según contexto.
- **Siempre con referencia a fuente de verdad determinística.**

### Inputs
- Todos los datos de motores previos (Control, Diagnostic, Forecast, Suggestion, Decision, Action).
- Historial de decisiones y resultados (Learning Engine).
- Consultas del operador en lenguaje natural.

### Outputs
- Respuestas en lenguaje natural con referencias a datos.
- Resúmenes y narrativas automáticas.
- Navegación asistida por contexto.

### Qué NO debe hacer
- **NO** gobernar el sistema. La IA interpreta, no gobierna.
- **NO** tomar decisiones autónomas sin supervisión humana.
- **NO** reemplazar los motores determinísticos. Es una capa de asistencia.
- **NO** ser la fuente única de verdad para ninguna métrica.

### Estado Actual
**BACKLOG.** No iniciado. Depende de que los motores previos estén operativos y estables.

---

## 9. Learning Engine

### Responsabilidad
**Aprender con evidencia histórica** para mejorar el sistema:
- Medir efectividad real de acciones pasadas (¿funcionó?).
- Ajustar parámetros de sugerencias y decisiones basado en resultados.
- Mejorar modelos de forecast con feedback de precisión real.
- Identificar patrones de éxito/fracaso en intervenciones.
- **Nunca alterar reglas críticas automáticamente.**

### Inputs
- Historial completo de: gaps → sugerencias → decisiones → acciones → resultados.
- Métricas de efectividad post-acción.
- Feedback humano sobre calidad de sugerencias y decisiones.

### Outputs
- Scores de efectividad por tipo de acción.
- Parámetros ajustados para Suggestion/Decision Engine.
- Modelos de forecast recalibrados.
- Recomendaciones de mejora de playbooks.

### Qué NO debe hacer
- **NO** alterar reglas críticas de control sin supervisión humana.
- **NO** romper la estabilidad del sistema con ajustes automáticos agresivos.
- **NO** operar sin un volumen suficiente de evidencia histórica.
- **NO** modificar thresholds de seguridad o integridad de datos.

### Estado Actual
**BACKLOG.** Existe `action_learning_service.py` como prototipo técnico. No debe activarse hasta que el ciclo completo (Control → Action) esté operativo y haya evidencia histórica suficiente (mínimo 3 meses de acciones ejecutadas con resultados medidos).

---

## Diagrama de Dependencias

```
Control Foundation ──► Diagnostic Engine ──► Forecast Engine ──► Suggestion Engine
                                                                        │
                                                                        ▼
                                                               Decision Engine
                                                                        │
                                                                        ▼
Reachability Engine ──────────────────────────────────────────► Action Engine
                                                                        │
                                                                        ▼
                                                                 Learning Engine
                                                                        │
                                                                        ▼
                                                                   AI Copilot
```

**Regla:** Las flechas indican dependencia dura. Un motor no puede estar ACTIVE si su predecesor no está cerrado.

---

## Referencias Cruzadas

- [ARCHITECTURE_CANONICAL_ROADMAP.md](./ARCHITECTURE_CANONICAL_ROADMAP.md) — Roadmap maestro con estados actuales.
- [LEGACY_PHASE_TRANSLATION_MAP.md](./LEGACY_PHASE_TRANSLATION_MAP.md) — Mapeo de fases legacy a motores.
- [ROADMAP_GOVERNANCE_RULES.md](./ROADMAP_GOVERNANCE_RULES.md) — Reglas de gobierno para implementaciones.
