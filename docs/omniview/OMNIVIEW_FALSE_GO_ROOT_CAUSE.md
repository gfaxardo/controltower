# OMNI-P0 — FALSE GO ROOT CAUSE ANALYSIS

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Estado:** ANÁLISIS COMPLETADO

---

## 1. ¿POR QUÉ O4.1 DIO GO FALSO?

El GO de O4.1 (2026-06-03) fue emitido bajo el marco OMNI-GOV-001, que validó exclusivamente:

| Validado | No validado |
|----------|------------|
| DOM tokens prohibidos (F1) | Utilidad operativa real para el usuario |
| Build del frontend PASS | Coherencia semántica de los datos |
| Screenshots 15/15 capturados | Revenue con datos reales en todos los grains |
| Endpoints sirviendo datos | Que Evolution es la vista por defecto y confunde |
| Trust score numérico (B1 fixed) | Que hay 2 modos que generan confusión (Evolution vs Vs Proy) |
| COALESCE revenue (B2 fixed) | Que el periodo actual es identificable <2s en modo Evolution |
| UI/Serving Reconciliation: 14 PASS | Que las métricas renderizan con lógica inconsistente |

El framework OMNI-GOV-001 fue diseñado como validación de integridad técnica (tokens, build, endpoints), no como validación de utilidad operativa.

---

## 2. ¿QUÉ VALIDÓ REALMENTE CHROMIUM?

Chromium/Playwright (o el script de captura de screenshots) validó:

1. **Existencia de elementos DOM**: que las celdas de la matriz no contenían `[object Object]`, `NaN`, `undefined`, `null`, `Infinity`.
2. **Render superficial**: que los números aparecían formateados (enteros, decimales, con formato de moneda).
3. **Presencia de datos en la matriz**: que al menos 60% del viewport mostraba datos (F2).
4. **Build saludable**: que `npm run build` no fallaba.
5. **Backend health**: que el backend en puerto 8001 respondía.
6. **Trust badge numérico**: que el score de confianza era un número, no un objeto (B1 fix).

---

## 3. ¿QUÉ NO VALIDÓ?

Chromium NO validó:

1. **Revenue con datos reales en daily/weekly**: La validación F7 dice "Métrica sin datos mientras fact tiene datos → FAIL", pero B2 se declaró "FIXED" cuando en realidad solo se aplicó COALESCE en el código. El serving layer diario/semanal seguía con `revenue_yego_net` NULL porque los datos fueron perdidos (`day_fact data loss`).

2. **Que Evolution es la vista por defecto**: El default es `viewMode = 'evolucion'` (`BusinessSliceOmniviewMatrix.jsx:309`). El usuario que abre Omniview ve Evolution, no Vs Proy. Evolution:
   - No muestra CLOSED/PARTIAL/CURRENT/FUTURE de forma clara
   - No tiene el modelo L1-L4 de Vs Proy
   - No muestra DoD/WoW/MoM consistente en todas las métricas
   - Usa lógica de render diferente a Vs Proy
   - El foco temporal se va a noviembre o periodos no operativos (Evolution no tiene `resolveClosedPeriodAnchor`)

3. **Inconsistencia cross-métrica de renderizado**: Las reglas FAIL no detectan que:
   - Evolution renderiza con `fmtValue` + `signalColorForKpi` (simple)
   - Vs Proy renderiza con `buildProjectionCellDisplay` (L1-L4 complejo)
   - Algunas métricas colorean con señal, otras no
   - DoD/WoW/MoM aparece en unas métricas y en otras no
   - No hay un contrato único de celda

4. **Coherencia de alertas con datos**: Las reglas F5 y F10 validan que haya remediation y que freshness no contradiga datos, pero NO validan que:
   - Un trust OK + alerta crítica coexistan sin explicación
   - Las alertas vengan de Evolution (datos incompletos) o Vs Proy (datos más completos)
   - Los mismatches de rollup sean reales vs artefactos

5. **Periodo actual correcto**: F3 valida "identificable <2s" pero NO valida que:
   - El auto-scroll realmente vaya al periodo correcto en modo Evolution
   - El periodo actual sea junio 2026 y no noviembre (foco erróneo)

6. **Revenue vacío en grillas**: F7 se declaró PASS con el B2 fix, pero los datos reales de day_fact/week_fact estaban perdidos (CF-H1L.1 → CF-H1L.5). El fix fue en código, no en datos.

---

## 4. ¿QUÉ REGLAS OMNI-GOV-001 FUERON INSUFICIENTES?

| Regla | Problema |
|-------|----------|
| **F1** (Token prohibido) | Necesaria pero no suficiente. Un número bien formateado puede ser operacionalmente inútil. |
| **F2** (Matriz vacía >40%) | No distingue entre "datos reales" y "placeholder Proy sin sentido". |
| **F3** (Periodo actual identificable) | Valida highlight visual pero no que el periodo sea correcto semanticamente. |
| **F7** (Métrica sin datos) | Declarada PASS con fix de código, pero los datos seguían ausentes en serving. No se re-ejecutó en serving real post-fix. |
| **F10** (Freshness vs datos) | No detecta que "Trust OK" + "Revenue vacío" es una contradicción. |
| **W4** (Inconsistencia cross-métrica) | Declarada PASS sin evidencia real. La inconsistencia existe y es estructural (Evolution vs Vs Proy usan paths de render diferentes). |
| **W6** (Temporal tier) | Declarada PASS, pero Evolution no usa `temporalTiers` engine de la misma forma que Vs Proy. |

### Lo que FALTÓ en el framework:

1. **Regla de modo canónico**: No existe regla que exija que una sola vista sea la canónica.
2. **Regla de coherencia semántica**: No existe validación de "lo que veo significa lo que creo que significa".
3. **Regla de revenue serving**: No existe validación de que `revenue_yego_final` tenga datos en todos los grains antes de declarar GO.
4. **Regla de cross-view deprecation**: No existe mecanismo para deshabilitar vistas legacy que generan confusión.

---

## 5. ¿QUÉ SCREENSHOTS DEL USUARIO CONTRADICEN EL GO?

(Nota: los screenshots referenciados aquí son los que el usuario reportó en la validación visual real. No se accedió a los archivos de screenshot en este análisis.)

Según el reporte del usuario:

1. **Revenue vacío en daily/weekly**: Las grillas de Revenue mostraban celdas vacías o `—` donde deberían aparecer valores de `revenue_yego_final`.

2. **Evolution activo como vista por defecto**: La UI mostraba el modo "Evolución" con datos incompletos y sin indicadores CLOSED/PARTIAL.

3. **Foco temporal en noviembre**: En modo Evolution, el scroll/viewport mostraba periodos no operativos (noviembre) en lugar de junio 2026.

4. **-30% sin contexto**: Una caída de -30% en "Auto Regular" se mostraba sin indicar si era un periodo CLOSED, PARTIAL, o CURRENT.

5. **Alertas coexistiendo con Trust OK**: El banner de confianza mostraba "OK" mientras alertas de rollup/mismatch/freshness aparecían sin explicación.

6. **Inconsistencia cross-métrica**: Cambiar entre Viajes, Revenue, Conductores mostraba diferentes formatos, colores, y presencia/ausencia de DoD/WoW/MoM.

---

## 6. ¿QUÉ DEBE CAMBIAR PARA QUE NO VUELVA A PASAR?

### Cambios estructurales:

1. **Certificación semántica, no solo de tokens**: Toda certificación futura debe validar que los datos son operacionalmente útiles, no solo que están bien formateados.

2. **Una sola vista canónica**: Vs Proy debe ser la única vista operativa. Evolution debe ser deprecado/oculto. No puede haber dos modos que compitan.

3. **Contrato canónico de celda**: Cada celda debe seguir el mismo contrato (real_value, plan_value, delta, status, freshness, trust, color, tooltip). No puede cada métrica renderizar con lógica distinta.

4. **Validación de serving pre-GO**: Antes de declarar GO, verificar que los datos existen en serving para TODOS los grains × métricas. No basta con que el código esté correcto.

5. **Regla de revenue serving**: `revenue_yego_final` debe tener cobertura >80% en daily, weekly, y monthly antes de GO.

6. **Regla de modo único**: La UI operacional debe tener un solo modo. Si existen modos legacy, deben estar ocultos por flag (`VITE_OMNIVIEW_EVOLUTION_LEGACY=false`).

7. **Validación de periodo actual**: El foco temporal debe estar en el periodo operativo actual (junio 2026), no en periodos históricos o futuros.

8. **Coherencia alertas-trust**: No puede coexistir Trust OK con alertas críticas sin una explicación explícita. Si coexisten → FAIL automático.

---

## 7. CONCLUSIÓN

El GO de O4.1 fue inválido porque:

> **Validó existencia/render superficial (tokens, build, endpoints), no utilidad operativa ni coherencia semántica.**

El framework OMNI-GOV-001 es necesario pero insuficiente. La certificación debe ampliarse para incluir:
- Validación semántica de datos (no solo formato)
- Verificación de cobertura serving real (no solo código)
- Regla de vista canónica única
- Contrato de celda uniforme cross-métrica
- Coherencia alertas ↔ trust ↔ datos

---

## 8. PRÓXIMO PASO

OMNI-GOV-002: Framework de certificación semántica V2 que reemplace/amplíe OMNI-GOV-001 con las reglas faltantes identificadas aquí.

---

**END OF ROOT CAUSE ANALYSIS**
