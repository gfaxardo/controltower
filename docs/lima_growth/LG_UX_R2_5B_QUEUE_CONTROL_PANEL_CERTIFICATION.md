# LG-UX-R2.5B — Queue Control Panel Certification

**Date:** 2026-06-08
**Phase:** LG-UX-R2.5B
**Status:** CERTIFIED

---

## 1. EXECUTIVE SUMMARY

**QUEUE CONTROL PANEL: OPERATIONAL.**

The Execution Queue section now has a full control panel with 4 build modes, limit inputs, build preview, TAKE_ALL safety with override_reason, build history, coverage card, and warnings panel. The operator can govern the queue from the UX — deciding how much to take, by what criteria, and with what justification.

---

## 2. QUEUE CONTROL PANEL

### Mode Selector (4 buttons)

| Mode | UX Behavior |
|------|-------------|
| CAPACITY_LIMITED | Respeta daily_action_capacity. Default. |
| TAKE_ALL | Muestra advertencia + textarea obligatorio para override_reason. Botón bloqueado sin justificación. |
| PROGRAM_LIMITED | Muestra 4 inputs (Churn Prevention, Active Growth, 14/90, HVR). |
| CHANNEL_LIMITED | Muestra 5 inputs (CALL_CENTER, SAC, BOT, FIELD, WHATSAPP). |

### Build Preview

| Métrica | Cálculo |
|---------|---------|
| Universo | universe_total |
| Elegibles | eligible_total |
| Capacidad | daily_action_capacity |
| Cola Esperada | Según modo seleccionado |
| Restante | elegibles - esperada |

### TAKE_ALL Safety

- Campo `override_reason` obligatorio
- Botón bloqueado sin texto
- Advertencia visible: "CAPACITY_EXCEEDED_BY_OPERATOR_OVERRIDE"
- Backend valida también

---

## 3. COVERAGE + WARNINGS

- Coverage card: Elegibles, En Cola, Coverage %
- Warnings panel: HELD drivers, capacidad excedida, pendientes sin asignar

---

## 4. BUILD HISTORY

Consume `queue_build_log` (migration 195). Muestra fecha, modo, creados, READY, HELD, override_reason.

---

## 5. FILES MODIFIED

| File | Change |
|------|--------|
| `ExecutionQueueSection.jsx` | Full rewrite: mode selector, limits, preview, TAKE_ALL safety, coverage, warnings, build history |

---

## 6. QA

| Check | Result |
|-------|:---:|
| npm run build | PASS |
| Mode selector visible | YES (4 buttons) |
| PROGRAM_LIMITED inputs | YES |
| CHANNEL_LIMITED inputs | YES |
| TAKE_ALL override required | YES |
| Build preview | YES |
| Coverage card | YES |
| Warnings panel | YES |
| Build history | YES |

---

## 7. FINAL VEREDICT

```
GO
```

### Operador puede:

| Acción | ¿Desde UX? |
|--------|:---:|
| Decidir cuánto atacar | YES — 4 modos + preview |
| Decidir por programa | YES — PROGRAM_LIMITED |
| Decidir por canal | YES — CHANNEL_LIMITED |
| Tomar todo el universo | YES — TAKE_ALL con override |
| Ver trazabilidad | YES — build history |
| Ver cobertura | YES — coverage card |
| Ver riesgos | YES — warnings panel |
