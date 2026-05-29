# Yego Pro Profitability P2.5 -- Coverage Audit & Human Guides Report

## Date: 2026-05-29
## Park: 64085dd85e124e2c808806f70d527ea8 (Lima)

---

## Resumen Ejecutivo

P2.5 convierte Profitability en una herramienta de auditoria operativa. Se agregaron:
- 9 guias humanas colapsables (una por subtab + coverage audit)
- Novena subtab "Coverage Audit" con semaforos de cobertura
- Deteccion de gaps operativos
- Mensajes de auditoria deterministicos
- Explicacion de fuentes en Data Quality

---

## 1. Archivos tocados

| Archivo | Accion |
|---------|--------|
| `frontend/src/components/YegoProProfitabilityPage.jsx` | +GuideBlock, +CoverageAuditPanel, +HUMAN_GUIDES, 9na tab, audit messages |
| `docs/fleet-project/yego-pro/PROFITABILITY_P2_5_COVERAGE_AUDIT_GUIDES.md` | Este documento |

## 2. Archivos NO tocados

- Drivers: NINGUNO
- Yango Loyalty: NINGUNO
- Omniview: NINGUNO
- Backend: NINGUNO
- api.js: NINGUNO
- App.jsx: NINGUNO

---

## 3. Guias humanas por subtab (Tarea 1)

Cada subtab tiene un bloque colapsable azul con:
- Que es
- Como usarlo
- Que decision permite tomar
- Siguiente paso recomendado
- Advertencias / data no disponible

| Tab | Guia |
|-----|------|
| Overview | "Aqui ves si Yego Pro gana o pierde dinero." |
| Weekly Closed | "Compara la utilidad entre semanas." |
| Last Closed Day | "Revisa dias con baja produccion." |
| Drivers | "Aqui detectas conductores que destruyen margen." |
| Vehicles | "Revisa estructura de cuotas contra produccion." |
| Shifts | "Si la noche produce mas que el dia, flota subutilizada." |
| Waterfall | "Revisa cuales costos dominan el P&L." |
| Data Quality | "Si faltan fuentes, no tomes decisiones fuertes." |
| Coverage Audit | "Verifica si el equipo esta registrando correctamente." |

---

## 4. Coverage Audit 9na subtab (Tarea 2)

Muestra semaforos con thresholds especificos:

| Metrica | Verde | Amarillo | Rojo |
|---------|-------|----------|------|
| Shift days | >= 7 | 3-6 | < 3 |
| Billing weeks | >= 4 | 2-3 | <= 1 |
| Close driver cov. | >= 90% | 70-89% | < 70% |
| Plate coverage | >= 90% | 70-89% | < 70% |
| Trip days | >= 30 | 7-29 | < 7 |

Valores actuales basados en P2.4:
- Shift days: 26 (VERDE)
- Billing weeks: 1 (ROJO)
- Close driver cov: 14.9% (ROJO)
- Plate coverage: 45.3% (ROJO)
- Trip days: 147 (VERDE)

---

## 5. Deteccion de gaps operativos (Tarea 3)

Gaps detectados desde coverage data:
- **Produccion sin cierre**: Significativo (cierre cov 14.9%)
- **Billing historico insuficiente**: 1 semana (minimo 4)
- **Placas sin asignar**: Significativo (plate cov 45.3%)
- **Cierres sin produccion**: No disponible
- **Vehiculos con uso parcial**: No disponible
- **Cierres manuales incompletos**: No disponible

Los gaps marcados como "No disponible" indican endpoints que no exponen ese dato. Sin joins pesados en frontend.

---

## 6. Mensajes de auditoria (Tarea 4)

Reglas deterministicas evaluadas:
1. **SI** close_driver_coverage < 80%: "Cobertura de liquidaciones insuficiente."
2. **SI** plate_coverage < 80%: "Relacion vehiculo-conductor parcial."
3. **SI** billing_weeks < 4: "No hay suficiente historico financiero."
4. **SI** shift_days > 7 y close_cov < 80%: "Hay produccion registrada pero no todos los cierres estan siendo capturados."

Severidades: high, medium, low.

---

## 7. Data Quality copy (Tarea 5)

Se agrego bloque de fuentes en la tab Quality:
- module_calculated_shifts = produccion diaria / turnos
- module_driver_closes = liquidaciones y pagos al conductor
- module_weekly_billing = cierre financiero semanal

---

## 8. QA

### Build
```
vite v5.4.21 building for production...
838 modules transformed.
built in 10.43s -- 0 errors
```

### Validaciones
- No loading infinito: AbortController preservado
- No NaN: safeVal + num en todas las metricas
- No undefined: Valores nulos formateados a "No disponible" o "N/D"
- No raw JSON: Todas las vistas usan componentes estructurados
- Guias visibles y colapsables: GuiaBlock con useState por tab
- Coverage Audit visible: 9na tab en navegacion
- Drivers intacto: Ningun cambio
- Loyalty intacto: Ningun cambio
- Omniview intacto: Ningun cambio
- Backend intacto: Ningun cambio

---

## 9. Veredicto

### GO/NO-GO para prueba humana

**GO.**

La UI ahora permite a Gonzalo:
1. Auditar si el equipo esta registrando correctamente produccion, cierres y billing
2. Ver el % de cobertura de cada fuente con semaforos
3. Identificar gaps operativos (produccion sin cierre, billing insuficiente)
4. Leer guias breves de como interpretar cada subtab
5. Tomar decisiones informadas sobre si la data es suficiente para actuar

Warnings clave:
- Billing solo 1 semana (ROJO) -- esperar mas semanas
- Close coverage 14.9% (ROJO) -- coordinar registro de cierres
- Plate coverage 45.3% (ROJO) -- mejorar asignacion vehiculo-conductor
