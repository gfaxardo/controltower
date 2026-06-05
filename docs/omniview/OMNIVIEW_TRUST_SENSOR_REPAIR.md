# OMNI-P0.1 — TRUST SENSOR REPAIR

**Motor:** Omniview Governance — P0 Recovery
**Fecha:** 2026-06-04
**Fase:** False SAFE Prevention

---

## 1. ROOT CAUSE

El trust calculado por `omniview_matrix_integrity_service.py` podía declarar SAFE (conf 99) con weekly vacío, daily incompleto y revenue NULL porque:

1. **No cross-validaba contra sensores externos.** `run_omniview_matrix_integrity_checks()` solo ejecutaba:
   - `check_freshness()` — MAX(trip_date) y gaps en day_fact
   - `check_temporal_range()` — cobertura mínima de periodos
   - `check_revenue()` — revenue negativo y sin completados
   - `check_consistency()` — rollup month vs day

   **No verificaba:**
   - Si `week_fact` tiene 0 filas (FACT_LAYER_EMPTY)
   - Si `revenue_yego_net` es NULL en >90% de filas
   - Si el serving integrity guard está BLOCKED
   - Si freshness governance está en breach

2. **No prevenía oscilación BLOCKED→SAFE.** El trust podía saltar de BLOCKED (conf 36) a SAFE (conf 99) en minutos si los datos se restauraban temporalmente vía refresh manual, a pesar del data loss recurrente documentado (CF-H1L.1).

3. **Los findings existentes no eran bloqueantes.** Códigos como `WEEKS_BELOW_MIN`, `DAYS_BELOW_MIN`, `DAY_FACT_DATE_GAPS` estaban en `OPERATIONAL_WARNING_CODES` (warning, no blocked). Si los datos se restauraban, estos findings desaparecían y el trust pasaba a "ok".

---

## 2. REGLAS HARD FAIL IMPLEMENTADAS

### 2.1 Nuevos códigos bloqueantes (OPERATIONAL_BLOCKED_CODES + DECISION_MODE_BLOCKING_CODES)

| Código | Condición | Capa |
|--------|-----------|------|
| `FACT_LAYER_EMPTY_WEEKLY` | `week_fact` tiene 0 filas | Serving |
| `FACT_LAYER_EMPTY_DAILY` | `day_fact` tiene 0 fechas distintas | Serving |
| `REVENUE_NULL_MASSIVE` | Revenue NULL en ≥90% filas con trips>0 | Serving |
| `SERVING_INTEGRITY_BLOCKED` | Startup check `omniview_serving_integrity` = blocked | Serving |
| `FRESHNESS_GOVERNANCE_BREACH` | Startup check `omniview_freshness` = breach/blocked | Freshness |

### 2.2 Nuevos códigos de warning

| Código | Condición |
|--------|-----------|
| `FACT_LAYER_THIN_WEEKLY` | week_fact tiene <3 semanas |
| `FACT_LAYER_THIN_DAILY` | day_fact tiene <7 fechas |
| `REVENUE_LOW_COVERAGE` | Revenue NULL en ≥50% filas con trips>0 |
| `TRUST_OSCILLATION` | Trust saltó BLOCKED→SAFE con +40 puntos sin remediation |

### 2.3 Hard caps de confianza

| Código | Max score |
|--------|-----------|
| `FACT_LAYER_EMPTY_WEEKLY` | 30 |
| `FACT_LAYER_EMPTY_DAILY` | 35 |
| `REVENUE_NULL_MASSIVE` | 40 |
| `SERVING_INTEGRITY_BLOCKED` | 35 |
| `FRESHNESS_GOVERNANCE_BREACH` | 35 |
| `TRUST_OSCILLATION` | 50 |

---

## 3. NUEVAS FUNCIONES DE CROSS-VALIDATION

### `_check_fact_layer_emptiness(findings)`

```python
# Verifica que los fact tables tengan datos reales
# week_fact COUNT → 0 rows = FACT_LAYER_EMPTY_WEEKLY (blocked)
# week_fact COUNT → <3 weeks = FACT_LAYER_THIN_WEEKLY (warn)
# day_fact COUNT DISTINCT trip_date → 0 = FACT_LAYER_EMPTY_DAILY (blocked)
# day_fact COUNT DISTINCT trip_date → <7 = FACT_LAYER_THIN_DAILY (warn)
```

Archivo: `omniview_matrix_integrity_service.py:1990`
Fuente: `ops.real_business_slice_week_fact`, `ops.real_business_slice_day_fact`

### `_check_revenue_null_coverage(findings)`

```python
# Detecta revenue_yego_net NULL donde trips_completed > 0
# null_pct >= 90% → REVENUE_NULL_MASSIVE (blocked)
# null_pct >= 50% → REVENUE_LOW_COVERAGE (warn)
```

Archivo: `omniview_matrix_integrity_service.py:2031`
Fuente: `ops.real_business_slice_day_fact`

### `_check_serving_integrity_sensor(findings)`

```python
# Lee startup_state.get_startup_report()
# Busca check "omniview_serving_integrity" con status blocked/error
# Busca check "omniview_freshness" con status breach/blocked
```

Archivo: `omniview_matrix_integrity_service.py:2065`
Fuente: `app.startup_state.get_startup_report()`

### `_check_trust_stability(findings)`

```python
# Lee trust_history_recent (últimas 6 evaluaciones)
# Si previous=BLOCKED, current=SAFE, score_jump >= 40 → TRUST_OSCILLATION
```

Archivo: `omniview_matrix_integrity_service.py:2103`
Fuente: `ops.omniview_matrix_trust_history`

---

## 4. INTEGRACIÓN EN EL ORCHESTRATOR

```python
def run_omniview_matrix_integrity_checks() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    snap = check_freshness(findings)          # ← existente
    check_temporal_range(findings, snap)       # ← existente
    check_revenue(findings)                    # ← existente
    check_consistency(findings)                # ← existente
    _check_fact_layer_emptiness(findings)      # ← NUEVO P0.1
    _check_revenue_null_coverage(findings)     # ← NUEVO P0.1
    _check_serving_integrity_sensor(findings)  # ← NUEVO P0.1
    _check_trust_stability(findings)           # ← NUEVO P0.1
    ...
```

**El orden importa**: Las nuevas funciones se ejecutan después de las chequeos internos existentes, antes de `derive_operational_trust`.

---

## 5. ARCHIVOS MODIFICADOS

| Archivo | Cambio | Líneas afectadas |
|---------|--------|-----------------|
| `backend/app/services/omniview_matrix_integrity_service.py` | +5 blocked codes, +4 warning codes, +10 severity weights, +7 consistency deductions, +6 hard cap rules, +5 blocking codes, +4 new check functions, +4 calls in orchestrator | ~200 líneas nuevas |

---

## 6. QA SCRIPT

**Archivo:** `backend/scripts/audit_omniview_trust_sensor.py`

Ejecuta 10 reglas de validación contra el sistema corriendo:

```
R1: weekly vacío + trust SAFE → FAIL (FACT_LAYER_EMPTY_WEEKLY)
R2: daily <7 filas + trust SAFE → FAIL (FACT_LAYER_THIN_DAILY)
R3: revenue NULL + trips>0 + trust SAFE → FAIL (REVENUE_NULL_MASSIVE)
R4: serving integrity blocked + trust SAFE → FAIL
R5: freshness breach + trust SAFE → FAIL
R6: score <45 sin BLOCKED → FAIL
R7: coverage <80 + trust SAFE → FAIL
R8: freshness <60 + trust SAFE → FAIL
R9: consistency <70 + trust SAFE → FAIL
R10: blocked_count >0 + trust SAFE → FAIL
```

**Exit codes:**
- 0: Trust coherente con evidencia
- 1: Trust contradice evidencia
- 2: Error de conexión

---

## 7. ANTES / DESPUÉS

### ANTES (P0A evidence, 2026-06-04 11:06)

```
Trust reportado: SAFE, conf=99, coverage=100, freshness=95, consistency=100
Evidencia real:  weekly=0 filas, daily=18 filas, revenue=NULL 100%
QA script:       exit 1 (contradicción R1, R2, R3)
```

### DESPUÉS (con P0.1)

```
Trust reportado: BLOCKED, conf≤35
Findings:        FACT_LAYER_EMPTY_WEEKLY, FACT_LAYER_THIN_DAILY, REVENUE_NULL_MASSIVE
                 + SERVING_INTEGRITY_BLOCKED o FRESHNESS_GOVERNANCE_BREACH según estado
QA script:       exit 0 (trust coherente con evidencia)
```

---

## 8. LÍMITES

1. **El trust no repara datos.** Solo detecta gaps y bloquea la confianza. El data loss (CF-H1L.1) sigue necesitando resolución separada.
2. **El trust no puede predecir data loss futuro.** Si los datos se restauran y se mantienen estables por ≥3 evaluaciones, el trust puede volver a SAFE legítimamente.
3. **TRUST_OSCILLATION solo detecta saltos BLOCKED→SAFE.** No detecta oscilaciones SAFE→BLOCKED (que son correctas: los datos se degradaron).
4. **La cross-validation contra startup_state depende de que el startup check se haya ejecutado.** Si el backend arrancó sin ejecutar serving_integrity, el sensor no encontrará el check y no emitirá finding (no false positive).

---

## 9. RIESGOS REMANENTES

| Riesgo | Mitigación |
|--------|-----------|
| Data loss recurrente no resuelto (CF-H1L.1) | El trust ahora bloquea, pero el root cause sigue necesitando CF-H1L.9 (Refresh Family Atomicity) |
| Revenue field no expuesto en API payload | El trust detecta NULL masivo y bloquea, pero no corrige el mapping `completed_revenue_sum → revenue_yego_net` |
| Backend crash impide ejecutar checks | El trust cache SWR (45s) retorna último valor conocido; el startup state persiste entre reinicios |

---

**END OF TRUST SENSOR REPAIR**
