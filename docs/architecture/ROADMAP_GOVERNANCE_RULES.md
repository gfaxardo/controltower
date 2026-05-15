# YEGO Control Tower — Reglas de Gobierno del Roadmap

**Versión:** 1.0.0
**Fecha:** 2026-05-15
**Propósito:** Reglas vinculantes para toda implementación futura. Cualquier PR, feature request o prompt de desarrollo debe cumplir estas reglas.

---

## Regla 1: Declaración Obligatoria de Feature

Toda nueva feature, endpoint, vista, componente o migración debe declarar explícitamente:

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| **Motor arquitectónico** | A qué motor pertenece (CF, DX, RH, FC, SG, DC, AC, AI, LN) | `Motor: Control Foundation` |
| **Fase** | Si es parte de una fase legacy, indicarlo | `Fase legacy: Phase 2B (traducido a CF)` |
| **Inputs** | Qué datos consume (tablas, vistas, endpoints) | `Inputs: ops.mv_real_lob_month_v3` |
| **Outputs** | Qué produce (vistas, endpoints, componentes UI) | `Outputs: GET /ops/real-lob/new-metric` |
| **Fuente de verdad** | Cuál es la fuente canónica de los datos | `Source: v_trips_real_canon_120d` |
| **Criterio de cierre** | Cómo se verifica que la feature está completa y correcta | `Cierre: KPI cuadra con fuente ±0.5%` |
| **Riesgo de deuda** | Si introduce deuda técnica o arquitectónica | `Riesgo: BAJO — aditivo, no modifica vistas existentes` |
| **¿Es prematura?** | Si la feature corresponde a un motor que no está ACTIVE o READY NEXT | `Prematura: NO (CF está ACTIVE)` |

### Template

```markdown
## Feature: [nombre]

| Campo | Valor |
|-------|-------|
| Motor | [CF/DX/RH/FC/SG/DC/AC/AI/LN] |
| Fase legacy | [N/A o Phase 2A/2B/2C/2C+] |
| Inputs | [tablas, vistas, endpoints] |
| Outputs | [vistas, endpoints, componentes] |
| Fuente de verdad | [fuente canónica] |
| Criterio de cierre | [condición verificable] |
| Riesgo de deuda | [BAJO/MEDIO/ALTO] + justificación |
| Prematura | [SI/NO] + justificación |
```

---

## Regla 2: Clasificación de Motor en Todo Requerimiento

Ningún prompt futuro de implementación puede procesarse sin indicar explícitamente:

> ¿Esta feature cae en Control, Diagnostic, Reachability, Forecast, Suggestion, Decision, Action, AI Copilot o Learning?

Si el prompt no lo especifica, el arquitecto debe:
1. Clasificarlo según [ENGINE_BOUNDARIES.md](./ENGINE_BOUNDARIES.md).
2. Validar que el motor correspondiente esté en estado ACTIVE o READY NEXT.
3. Si el motor está en BACKLOG, rechazar la implementación o marcarla como **PREMATURE** con justificación.

---

## Regla 3: Nombres Legacy en Código

1. Los identificadores `phase2a`, `phase2b`, `phase2c` en archivos, endpoints, tablas y vistas SQL **permanecen inalterados**. Son nombres técnicos legacy.
2. Estos nombres **no deben usarse como roadmap de producto** ni en nueva documentación de arquitectura.
3. Las etiquetas visibles al usuario que contengan "Fase 2B", "Fase 2C", etc. deben migrarse progresivamente a nombres funcionales (ej. "Plan vs Real Semanal", "Accountability", "Universo LOB"). No es obligatorio inmediato, pero sí recomendado.
4. Toda nueva feature debe usar nombres funcionales, no de fase.

---

## Regla 4: Validación de Control Foundation Antes de Motores Superiores

Si una feature toca **sugerencias, decisiones, acciones o aprendizaje**, primero debe validar que Control Foundation esté estable:

### Checklist de Validación
- [ ] KPIs cuadran entre daily/weekly/monthly (±1%).
- [ ] Grains son consistentes y auditables.
- [ ] Freshness pipeline funciona (no MVs stale > threshold).
- [ ] Omniview Matrix sin celdas vacías inexplicables.
- [ ] Plan vs Real sin diferencias de fuente.
- [ ] Joins Plan↔Real documentados y verificables.

Si algún ítem falla, la feature se rechaza o se marca como **PREMATURE** hasta que Control Foundation cierre.

---

## Regla 5: Aditividad y No Ruptura de Omniview Matrix

1. Toda feature nueva debe ser **aditiva**: no debe romper vistas, endpoints o componentes existentes.
2. **Omniview Matrix** es la vista canónica de verdad operacional. Ninguna feature puede degradar su integridad.
3. Si una feature requiere modificar una vista compartida, debe:
   - Crear una vista `_v2` o extensión en lugar de modificar la existente.
   - Validar que Omniview Matrix sigue funcionando después del cambio.
   - Documentar el migration path.

---

## Regla 6: Plan y Real No Se Mezclan Incorrectamente

1. **Plan** y **Real** son dominios separados con fuentes de verdad distintas.
2. Plan vs Real los compara, pero no los mezcla en una sola fuente.
3. Toda vista de Plan vs Real debe ser clara sobre:
   - Qué columnas vienen de Plan.
   - Qué columnas vienen de Real.
   - Qué regla de join se aplicó.
   - Qué pasa con filas sin match (unmatched).

---

## Regla 7: La IA Interpreta, No Gobierna

1. Los **algoritmos determinísticos mandan primero**. La IA asiste, no decide.
2. Toda señal, alerta, sugerencia o decisión generada por IA debe:
   - Tener un cálculo determinístico de respaldo que pueda verificarse.
   - Incluir referencia explícita a la fuente de datos.
   - Ser overridable por un operador humano.
3. Ningún loop automático (detección → decisión → acción) puede ejecutarse sin supervisión humana hasta que el sistema tenga al menos 6 meses de operación estable con auditoría de decisiones.

---

## Regla 8: Fases Legacy No Bloquean Nuevas Features

1. Una feature nueva puede implementarse aunque su código toque archivos con nombres legacy (ej. `phase2b.py`), siempre que:
   - La feature en sí pertenezca al motor ACTIVE o READY NEXT.
   - Se declare explícitamente el mapeo (ver Regla 1).
   - No expanda el alcance del motor más allá de sus límites (ver [ENGINE_BOUNDARIES.md](./ENGINE_BOUNDARIES.md)).
2. Ejemplo: añadir un endpoint en `phase2b.py` para mejorar la visualización de Plan vs Real semanal es válido (pertenece a Control Foundation). Añadir lógica de priorización automática de acciones en `phase2b_actions_service.py` **no es válido** (eso es Action Engine, que está en BACKLOG).

---

## Regla 9: Cierre de Motor

Un motor se considera **CERRADO** cuando:

1. Todos sus criterios de cierre (definidos en [ARCHITECTURE_CANONICAL_ROADMAP.md](./ARCHITECTURE_CANONICAL_ROADMAP.md)) se cumplen.
2. No hay bugs P0/P1 abiertos en componentes de ese motor.
3. La documentación del motor está actualizada.
4. El equipo técnico valida el cierre.

Al cerrar un motor:
- El siguiente motor en la cadena pasa de READY NEXT a ACTIVE.
- Se selecciona el siguiente motor del BACKLOG como READY NEXT.
- Se actualiza [ARCHITECTURE_CANONICAL_ROADMAP.md](./ARCHITECTURE_CANONICAL_ROADMAP.md).

---

## Regla 10: Auditoría de Cumplimiento

Cada sprint o ciclo de desarrollo debe incluir una **micro-auditoría arquitectónica**:

1. Revisar features implementadas contra sus declaraciones de motor.
2. Verificar que no se hayan introducido features prematuras.
3. Actualizar el estado de criterios de cierre de Control Foundation.
4. Reportar desviaciones en `docs/architecture/` con fecha y responsable.

---

## Referencias Cruzadas

- [ARCHITECTURE_CANONICAL_ROADMAP.md](./ARCHITECTURE_CANONICAL_ROADMAP.md) — Roadmap maestro.
- [LEGACY_PHASE_TRANSLATION_MAP.md](./LEGACY_PHASE_TRANSLATION_MAP.md) — Mapeo de fases legacy.
- [ENGINE_BOUNDARIES.md](./ENGINE_BOUNDARIES.md) — Límites de cada motor.
