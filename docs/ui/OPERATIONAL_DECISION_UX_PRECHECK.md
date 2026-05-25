# OPERATIONAL DECISION UX PRECHECK

**Date**: 2026-05-25
**Phase**: UX Hardening Stage 4

---

## ACTIVE PHASE

**Phase**: 1H.4 — Operational Maturity Governance Layer
**Motor**: Control Foundation
**Status**: ACTIVE

## READY NEXT

**Phase**: 2A.3 — Behavioral Pattern Diagnosis
**Motor**: Diagnostic Engine
**Status**: READY NEXT

---

## MOTORES PERMITIDOS

- Control Foundation (ACTIVE)
- Diagnostic Engine early (diagnóstico de señales existentes, sin nuevos cálculos)

## MOTORES BLOQUEADOS

- Decision Engine (backlog) — NO activar lógica de decisión automática
- Suggestion Engine (backlog) — NO generar recomendaciones
- Forecast Engine (prototype only) — NO proyectar estados futuros
- AI Copilot (backlog) — NO IA ni ML
- Action Engine (backlog) — NO ejecutar acciones

---

## JUSTIFICACIÓN ARQUITECTÓNICA

Este hardening NO es Decision Engine.

Es una capa de **priorización visual determinística** dentro de Control Foundation + Diagnostic Engine temprano.

Lo que hace:
- Centralizar severities ya existentes
- Normalizar thresholds (hoy dispersos)
- Routear atención visual (ordenar por prioridad)
- Señalizar anomalías con emphasis controlado

Lo que NO hace:
- Decidir acciones automáticas
- Generar recomendaciones
- Proyectar futuro
- Modificar datos
- Introducir IA

---

## RIESGOS

| Riesgo | Mitigación |
|--------|-----------|
| Confundir "Decision UX" con "Decision Engine" | Nombre canónico: Operational Decision Severity |
| Thresholds inconsistentes con backend | Usar thresholds desde serving facts, no inventar |
| Runtime pesado por sorting | Usar memoización, thresholds pre-computados |
| Too many badges overwhelm | Una severidad por entidad, no stacking |

---

## GO / NO-GO

**VERDICT: GO**

- Alineado con Control Foundation + Diagnostic temprano
- Sin motores bloqueados
- Determinístico
- Aditivo (no rompe nada existente)
- Reversible (todo en frontend, sin cambios de backend)
- Sin IA, sin ML, sin recomendaciones
- Sin runtime pesado
