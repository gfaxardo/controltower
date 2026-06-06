# LG-C1.4-P2 — UX Remediation Plan

**Date:** 2026-06-05

## P0 — Aplicado (rompe operación o confunde verdad operacional)

| # | Issue | Tab | Fix | Status |
|---|-------|-----|-----|--------|
| 1 | Grid de 5 métricas con "—" parece funcional | Impacto | Reemplazado por EmptyState único "No certificada" | **DONE** |
| 2 | 3 sub-cards "Por Agente/Campaña/Iniciativa" parecen navegables | Atribución | Consolidado en EmptyState único "No certificada" | **DONE** |
| 3 | Título vago "Pendiente de serving fact" | Movimiento | Estandarizado "No certificada — Pendiente LC-2" | **DONE** |

## P1 — Funcionalidad importante no visible

| # | Issue | Acción | Esfuerzo |
|---|-------|--------|----------|
| 4 | Botón "Exportar a LoopControl" falta en tab Queue | Agregar botón que llame `POST /assignment-queue/export` | Bajo |
| 5 | Result Sync sin wiring al frontend | Conectar `GET /loopcontrol/results/*` cuando Miguel entregue API | Medio |
| 6 | `today` hardcodeado a `2026-06-02` | Usar `new Date().toISOString().slice(0,10)` | Bajo |

## P2 — Mejora de claridad/usabilidad

| # | Issue | Acción | Esfuerzo |
|---|-------|--------|----------|
| 7 | Programas definidos en 3 lugares (frontend, policy service, registry) | Consolidar en un solo registry (DB o config file) | Medio |
| 8 | Oportunidades tab usa endpoint legacy (`prioritized-opportunities`) | Podría enriquecerse con datos de `operational-summary` | Bajo |
| 9 | Capacidad diaria muestra 0 cuando no hay config para la fecha | Mejorar fallback a NULL-date config | Bajo |

## P3 — Estética/cosmética

| # | Issue | Acción | Esfuerzo |
|---|-------|--------|----------|
| 10 | Tabs "No certificada" podrían tener icono visual | Agregar icono de "pendiente" en sidebar | Bajo |
| 11 | Pipeline bar podría mostrar tooltips | Agregar títulos a cada segmento | Bajo |
