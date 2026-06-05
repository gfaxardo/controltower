# OMNI-P0 — VEREDICTO FINAL

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Fase:** OMNI-P0 — False GO Recovery & Vs Proy Canonicalization

---

## 1. VEREDICTO

### NO GO

**Omniview no puede declararse operativamente cerrado en este momento.**

**Justificación**: Aunque Vs Proy tiene la arquitectura correcta para ser la vista canónica, los datos subyacentes (day_fact, week_fact) están incompletos por data loss recurrente. Sin datos diarios y semanales completos, certificar cualquier vista como operacional es prematuro.

---

## 2. POR QUÉ EL GO ANTERIOR FUE FALSO

El GO de O4.1/O5 (2026-06-03) declaró Omniview Hardening CLOSED basándose en:

| Lo que validó | Lo que NO validó |
|---------------|-----------------|
| DOM tokens (F1) | Utilidad operativa real |
| Build frontend PASS | Revenue con datos en daily/weekly |
| Screenshots 15/15 | Que Evolution es el default (confunde) |
| Trust score numérico | Que CLOSED/PARTIAL no es visible en celdas |
| COALESCE revenue (B2 fix) | Que -30% sin contexto es inútil |
| 14 PASS UI/Serving | Que Trust OK + alertas activas es contradictorio |

**Error raíz**: El framework OMNI-GOV-001 fue diseñado como validación de integridad técnica, no como validación de utilidad operativa. La certificación validó que el código funciona, no que el usuario puede tomar decisiones.

---

## 3. ESTADO REAL DE OMNIVIEW

| Dimensión | Estado | Detalle |
|-----------|--------|---------|
| **Código frontend** | OK | Build limpio, tokens corregidos (B1, B2), COALESCE revenue implementado |
| **Arquitectura Vs Proy** | OK | Modelo L0-L4, contrato de celda rico, badges de estado, DoD/WoW/MoM canónico |
| **Backend serving** | OK | Endpoints responden, COALESCE `_final`/`_net` correcto |
| **Datos daily** | **FAIL** | day_fact data loss: solo Jun 1-2 con datos, Mayo 26-31 perdido |
| **Datos weekly** | **FAIL** | week_fact data loss: solo 3 de 8 semanas con datos, S18-S22 perdido |
| **Datos monthly** | OK | 100% trips/drivers/ticket/TPD, 50% revenue (gap de `_final` en serving) |
| **Revenue** | **FAIL** | daily 0%, weekly 0%, monthly 50% — datos incompletos |
| **Trust vs Datos** | **FAIL** | Trust OK coexiste con datos incompletos → contradicción |
| **Evolution visible** | **FAIL** | Es el default (`viewMode = 'evolucion'`), confunde al usuario |
| **Foco temporal** | **WARNING** | Evolution no tiene `resolveClosedPeriodAnchor`, puede mostrar noviembre |

---

## 4. PLAN DE DEPRECACIÓN EVOLUTION

**Archivo**: `docs/omniview/OMNIVIEW_EVOLUTION_DEPRECATION_PLAN.md`

**Resumen**:
1. **Fase 1 (AHORA)**: Flag `VITE_OMNIVIEW_EVOLUTION_LEGACY=false`. Default `viewMode` → `'proyeccion'`.
2. **Fase 2 (AHORA)**: Ocultar toggle Evolution/Vs Proy del `OmniviewModeSelector`.
3. **Fase 3 (AHORA)**: Bloquear certificación de Evolution en OMNI-GOV-002.
4. **Fase 4 (P2)**: Cleanup de código Evolution cuando Vs Proy esté estabilizado.
5. **Fase 5 (P2)**: Auditar consumidores de endpoints Evolution antes de eliminar.

**No se elimina código destructivamente. Se depreca/oculta/controla por flag.**

---

## 5. CONTRATO CANÓNICO VS PROY

**Archivo**: `docs/omniview/OMNIVIEW_VS_PROY_CANONICAL_CONTRACT.md`

**Resumen**:
- 10 campos obligatorios por celda: `real_value`, `plan_value`, `projection_value`, `delta_abs`, `delta_pct`, `comparison_label`, `period_status`, `freshness_status`, `trust_status`, `display_value`, `display_badge`, `color_rule`, `tooltip_reason`
- 6 estados de periodo: CLOSED, PARTIAL, CURRENT, FUTURE, NO_PLAN, NO_REAL
- 5 niveles de severidad de color (momentum)
- 3 comparaciones canónicas: DoD (daily), WoW (weekly), MoM (monthly)
- Uniformidad cross-métrica obligatoria

---

## 6. MATRIZ DE COVERAGE VS PROY

**Archivo**: `docs/omniview/OMNIVIEW_VS_PROY_COVERAGE_MATRIX.md`

| Grain | Métricas OK | % Coverage | Bloquea GO? |
|-------|------------|------------|-------------|
| Daily | 0/5 | 25% (0% revenue) | **Sí — P0** |
| Weekly | 0/5 | 37.5% (0% revenue) | **Sí — P0** |
| Monthly | 4/5 | 100% (50% revenue) | WARNING |

**Causa raíz**: Data loss en `day_fact` (Mayo 26-31) y `week_fact` (S18-S22). El código y los COALESCE son correctos.

---

## 7. ROOT CAUSE REVENUE VACÍO

**Archivo**: `docs/omniview/OMNIVIEW_REVENUE_EMPTY_ROOT_CAUSE.md`

**Causa primaria (P0)**: Data loss en day_fact y week_fact. Ambos campos (`revenue_yego_net` y `revenue_yego_final`) son NULL porque los datos no están en las fact tables.

**Causa secundaria (P1)**: `revenue_yego_final` existe en `month_fact` (79.2% filas) pero no se expone consistentemente en la serving view mensual.

**No es**: bug de código, COALESCE incorrecto, renderizado frontend, o selección de campo.

---

## 8. ALERTAS / MISMATCH DETECTADAS

**Archivo**: `docs/omniview/OMNIVIEW_ALERTS_ROLLUP_MISMATCH_AUDIT.md`

| Alerta | Estado | Bloquea GO? |
|--------|--------|-------------|
| Freshness day_fact WARNING/BLOCKED | Activo | **Sí** |
| Freshness week_fact WARNING/BLOCKED | Activo | **Sí** |
| Trust OK + datos incompletos | Contradicción | **Sí** |
| MONTH_TRIPS_MISMATCH | Reportado 0 diff (closure) | Verificar |
| Rollup mismatch | Puede reactivarse con data loss | Verificar |

---

## 9. BACKLOG P0/P1

### P0 — Bloquea GO (debe resolverse antes)

| # | ID | Descripción | Motor |
|---|----|-------------|-------|
| 1 | OMNI-P0-D1 | Restaurar day_fact: refresh Mayo 26 - Junio 4, 2026 | Scheduler |
| 2 | OMNI-P0-D2 | Restaurar week_fact: refresh S17 - S23, 2026 | Scheduler |
| 3 | OMNI-P0-D3 | Verificar revenue_yego_final >0 en day_fact y week_fact post-refresh | Backend |
| 4 | OMNI-P0-U1 | Cambiar default viewMode a 'proyeccion' | Frontend |
| 5 | OMNI-P0-U2 | Ocultar toggle Evolution/Vs Proy (flag VITE_OMNIVIEW_EVOLUTION_LEGACY) | Frontend |
| 6 | OMNI-P0-U3 | Asegurar Vs Proy graceful fallback sin plan cargado | Frontend |
| 7 | OMNI-P0-T1 | Re-ejecutar UI/Serving reconciliation → 0 FAIL | QA |
| 8 | OMNI-P0-T2 | Verificar trust score coherente con datos post-refresh | Backend |
| 9 | OMNI-P0-C1 | Ejecutar OMNI-GOV-002 con 18 screenshots → 0 FAIL S1-S10 | QA |

### P1 — No bloquea GO pero necesario post-GO

| # | ID | Descripción | Motor |
|---|----|-------------|-------|
| 10 | CF-H1L.9 | Refresh Family Atomicity (cross-grain data loss) | Infraestructura |
| 11 | CF-H2 | Revenue `_final` en serving view mensual consistente | Backend |
| 12 | CF-H1L.4 | Freshness Confidence Score | Trust |
| 13 | OMNI-P0-U4 | Implementar contrato canónico S4 en todas las métricas de Vs Proy | Frontend |
| 14 | OMNI-P0-U5 | Implementar badges CLOSED/PARTIAL/CURRENT/FUTURE en todas las celdas | Frontend |
| 15 | OMNI-P0-U6 | Alinear trust ↔ freshness (no OK con datos incompletos) | Backend |

### P2 — Mejoras futuras

| # | ID | Descripción |
|---|----|-------------|
| 16 | OMNI-P0-UX | Migrar insights engine a Vs Proy |
| 17 | OMNI-P0-UX | Cleanup código Evolution |
| 18 | OMNI-P0-UX | Optimizar performance Vs Proy |
| 19 | OMNI-QA-001 | Playwright Full F1-F10 + S1-S10 Automation |

---

## 10. PRÓXIMO PROMPT RECOMENDADO

```
OMNI-P0-FIX — RESTAURAR DATOS Y ACTIVAR VS PROY COMO DEFAULT

Ejecutar en orden:
1. Refresh day_fact para recuperar Mayo 26 - Junio 4, 2026
2. Refresh week_fact para recuperar S17 - S23, 2026
3. Verificar revenue_yego_final > 0 en ambos grains
4. Cambiar default viewMode = 'proyeccion' en BusinessSliceOmniviewMatrix.jsx:309
5. Agregar flag VITE_OMNIVIEW_EVOLUTION_LEGACY=false en .env
6. Ocultar toggle Evolution en OmniviewModeSelector.jsx si flag=false
7. Re-ejecutar UI/Serving reconciliation → debe dar 0 FAIL
8. Re-ejecutar OMNI-GOV-002 con 18 screenshots
9. Si 0 FAIL → CONDITIONAL GO
10. Si >0 FAIL → reportar y NO declarar GO

NO activar Diagnostic.
NO tocar Forecast/Suggestion/Decision/Action.
Solo datos + flag + certificación.
```

---

## REGLA FINAL CONFIRMADA

```
NO avanzar Diagnostic.
NO declarar Omniview CLOSED.
NO certificar Evolution.
TODO debe girar alrededor de Vs Proy como vista operacional canónica.
```

---

**END OF VEREDICTO**
