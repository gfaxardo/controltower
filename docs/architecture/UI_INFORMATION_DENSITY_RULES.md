# YEGO Control Tower — Reglas de Densidad de Información en UI

**Versión:** 1.0.0
**Fecha:** 2026-05-15
**Propósito:** Definir qué información pertenece a cada nivel de la UI y cómo evitar saturación en la vista principal.

---

## Principio Rector

> **La Omniview Matrix es una vista de Control Foundation. Debe permitir lectura rápida del estado operacional, no convertirse en pantalla de decisión ni ejecución.**

---

## Niveles de Información

| Nivel | Vista | Motor | Densidad |
|-------|-------|-------|----------|
| **1. Control** | Omniview Matrix (inline) | Control Foundation | Compacta — KPIs, estado, alertas breves |
| **2. Diagnóstico** | Inspector / Drawer lateral | Diagnostic Engine | Media — explicación de gaps, causas probables |
| **3. Oportunidades** | Oportunidades Operativas (subtab) | Diagnostic Engine | Completa — sugerencias, prioridades, impacto |
| **4. Decisión** | Futuro (no visible en prod) | Decision Engine | — |
| **5. Acción** | Futuro (no visible en prod) | Action Engine | — |

---

## Qué Pertenece a la Omniview Matrix (Inline)

Solo elementos de **Control Foundation** y **diagnóstico compacto**:

### Permitido (INLINE_COMPACT)
- KPIs de la matriz con deltas y señales de color.
- Barra de contexto (freshness, comparativos, cobertura, avance de periodo).
- Banner ejecutivo de Data Trust (estado, confianza, problema principal).
- Banner de integridad de proyección (íconos de estado).
- YTD summary bar compacta.
- Resumen compacto de oportunidades operativas (conteo, top 3 problemas, link a detalle).
- Panel de prioridades del periodo (tabla compacta, 2 columnas).
- Insights panel (tarjetas compactas con severidad y causa).
- Drawer lateral al hacer clic en celda (Inspector / ProjectionDrill).

### NO Permitido (mover a subtab o drawer)
- Bloques extensos de sugerencias operativas con rationale largo.
- Bloques de recomendaciones priorizadas con textos de decisión.
- Colas estratégicas globales.
- Botones de "Aceptar orden", "Enviar a operaciones", "Enviar a planeación".
- Textos de "Decision Engine" o "Action Engine" visibles al usuario.
- Listados completos de todas las sugerencias (solo resumen compacto).

---

## Qué Pertenece a Oportunidades Operativas (Subtab)

La subtab `/operacion/oportunidades` puede mostrar contenido completo:

### Permitido
- Sugerencias operativas con prioridad, confianza, impacto, owner, canal.
- Sugerencias contextualizadas con pools, segmentos, estimaciones de recuperación.
- Agrupación por país/ciudad/LOB.
- Explicación de cálculo y trazabilidad.
- Conductores afectados (si el endpoint existe).

### Lenguaje Permitido
- "Oportunidad operativa"
- "Orden sugerido"
- "Requiere validación manual"
- "Ejecución no habilitada"
- "Ver trazabilidad"

### Lenguaje NO Permitido en Producción
- "Decision Engine"
- "Action Engine"
- "Ejecutar"
- "Aceptar prioridad global"
- "Enviar automáticamente"
- "Campaña creada"

---

## Qué Pertenece al Drawer Contextual

Al hacer clic en una celda o en "Ver diagnóstico":

### Inspector (Evolución)
- Datos de la celda seleccionada (KPI, delta, periodo).
- Estado de Data Trust específico.
- Diagnóstico: causas probables, evidencia.
- Acción sugerida con prioridad (lenguaje informativo).
- Botones de tracking: "Registrar acción ejecutada", "Marcar como resuelto" (logging, no ejecución automática).

### ProjectionDrill (Vs Proyección)
- Detalle de proyección: confianza, método de curva, ajuste de conservación.
- Root Cause Analysis: factores, barras, main driver.
- Acción sugerida con priority band, target team, rationale.

---

## Reglas de Implementación

1. **Ninguna sugerencia extensa debe vivir inline dentro de la matriz.**
2. **Toda explicación larga debe ir a drawer o subtab.**
3. **Los bloques de Decision/Action solo se muestran en desarrollo** (`import.meta.env.DEV` o `VITE_SHOW_DEV_MODULES=true`).
4. **El resumen compacto de oportunidades** (conteo + top 3 + link) es el máximo nivel de detalle permitido inline.
5. **"Ir a Oportunidades Operativas"** es el único CTA visible desde la matriz hacia sugerencias/detalle.

---

## Arquitectura de Información Visual

```
┌─────────────────────────────────────────────────────────┐
│ OMNIVIEW MATRIX (inline)                                │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Banner Data Trust (1 línea)                         │ │
│ ├─────────────────────────────────────────────────────┤ │
│ │ Contexto: freshness · comparativo · avance · cobert.│ │
│ ├─────────────────────────────────────────────────────┤ │
│ │ Oportunidades: "12 detectadas · Ir a Oportunidades→"│ │ ← COMPACTO
│ │  ● Gap revenue Lima B2C          [Ver diagnóstico]  │ │
│ │  ● Baja productividad Cali       [Ver diagnóstico]  │ │
│ ├─────────────────────────────────────────────────────┤ │
│ │ MATRIZ DE DATOS (tabla principal)                   │ │
│ │                                                     │ │
│ └─────────────────────────────────────────────────────┘ │
│                                        ┌──────────────┐ │
│                                        │ INSPECTOR    │ │ ← DRAWER
│                                        │ (al hacer    │ │
│                                        │  clic)       │ │
│                                        └──────────────┘ │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ OPORTUNIDADES OPERATIVAS (subtab separada)              │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Operacionales (8) │ Contextuales (4)                │ │ ← TABS
│ ├─────────────────────────────────────────────────────┤ │
│ │ ┌─────────────────────────────────────────────────┐ │ │
│ │ │ Oportunidad 1 (tarjeta completa)                │ │ │
│ │ │ Prioridad · Confianza · Impacto · Owner · Canal │ │ │
│ │ │ Racional · Trazabilidad                         │ │ │
│ │ │ "Requiere validación manual"                    │ │ │
│ │ └─────────────────────────────────────────────────┘ │ │
│ │ ... más tarjetas ...                                │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

---

## Referencias Cruzadas

- [ARCHITECTURE_CANONICAL_ROADMAP.md](./ARCHITECTURE_CANONICAL_ROADMAP.md) — Estados de motores.
- [ENGINE_BOUNDARIES.md](./ENGINE_BOUNDARIES.md) — Límites de cada motor.
- [UI_PRODUCTION_VISIBILITY_RULES.md](./UI_PRODUCTION_VISIBILITY_RULES.md) — Reglas de visibilidad.
- [ROADMAP_GOVERNANCE_RULES.md](./ROADMAP_GOVERNANCE_RULES.md) — Reglas de gobierno.
