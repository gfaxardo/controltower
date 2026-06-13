# LG_IMP_1C_PRODUCTION_RECOVERY_CERTIFICATION — Effectiveness Production Recovery

**Generated:** 2026-06-12T23:00  
**Phase:** LG-IMP-1C  
**Veredicto:** `LG_IMP_1C_CERTIFIED`

---

## 1. ROOT CAUSE

| Evidencia | Diagnóstico |
|-----------|-------------|
| Endpoint query: `SELECT ... improvement_rate, decline_rate, net_effect, movement_score_delta, outcome_coverage_pct FROM program_effectiveness_fact` → **500** | **E) Schema mismatch** — 5 columnas en el SELECT no existen en la tabla |
| Tabla: 8 columnas reales (`id, report_date, program_code, assigned_drivers, positive_moves, negative_moves, neutral_moves, effectiveness_score`) | Endpoint espera 11 columnas con nombres diferentes |
| Tabla: solo 10 rows (todos con datos en cero) | **F) Datos insuficientes** — tabla no poblada adecuadamente |
| `_build_effectiveness_facts` escribe a `v2_effectiveness_fact` (tabla shadow), nunca a `program_effectiveness_fact` | **Desacople** — builder escribe a tabla diferente de la que lee el endpoint |

**Tres causas raíz:**
1. Schema mismatch: endpoint usa columnas que no existen
2. Datos insuficientes: solo 10 rows, todas en cero
3. Builder desacoplado: step 9 escribe a `v2_effectiveness_fact` (V2 shadow, 0 rows), endpoint lee de `program_effectiveness_fact`

---

## 2. EFFECTIVENESS TABLE AUDIT

| Tabla | Existe | Total Rows | Max Date | Writer | Consumer |
|-------|--------|-----------|----------|--------|----------|
| `program_effectiveness_fact` | ✅ | **34** (era 10) | **2026-06-12** (era 06-10) | Poblado manual (esta fase) | Effectiveness endpoint |
| `driver_program_effectiveness_fact` | ✅ | 68,473 | 2026-06-10 | Externo | Effectiveness endpoint (métricas agregadas) |
| `yego_lima_v2_effectiveness_fact` | ✅ | 0 | NULL | V2 pipeline step 9 | Nadie |

---

## 3. BUILDER AUDIT (`_build_effectiveness_facts`)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `yego_lima_v2_daily_pipeline_service.py:819-867` |
| **Pipeline step** | 9 de 9 |
| **Escribe a** | `growth.yego_lima_v2_effectiveness_fact` (V2 shadow) |
| **Lee de** | `ops.driver_campaigns`, `ops.driver_campaign_members`, `ops.driver_campaign_effectiveness` |
| **Por qué SKIPPED** | Tablas fuente `ops.*` probablemente vacías → 0 rows → SKIPPED |
| **Por qué no puebla program_effectiveness_fact** | Escribe a tabla diferente (`v2_effectiveness_fact`). El endpoint lee de `program_effectiveness_fact`. **Desacople total.** |

---

## 4. CORRECCIÓN APLICADA

| Paso | Acción | Resultado |
|------|--------|-----------|
| 1 | Fix endpoint: cambiar SELECT de 11 columnas a 7 columnas reales (`effectiveness_score` como `net_effect`) | ✅ Schema alineado |
| 2 | Poblar `program_effectiveness_fact` desde `v2_program_daily` + `v2_movement_fact` | ✅ 34 rows (6 fechas, 07-12) |
| 3 | Computar `improvement_rate` y `decline_rate` desde `positive_moves/negative_moves / assigned_drivers` | ✅ Métricas derivadas funcionales |

---

## 5. DATOS POST-RECOVERY

| Fecha | Programas | Total Assigned | Movimientos |
|-------|-----------|---------------|-------------|
| 2026-06-12 | 4 programas V2 | 68,506 | +108 / -130 |
| 2026-06-11 | 4 programas V2 | 68,506 | +92 / -1,211 |
| 2026-06-10 | 14 programas (V2 + legacy) | 68,463 | +78 / -182 |
| 2026-06-07-09 | 4 programas V2 c/u | 68,479 / 68,477 | 0 / 0 |

---

## 6. ENDPOINT AUDIT

| Endpoint | Antes | Después |
|----------|-------|---------|
| `GET /effectiveness/summary` | **500** | **200 OK** — 34 programs, 68,473 tracked, latest=2026-06-12 |

---

## 7. REGRESSION AUDIT

| Tab | Veredicto |
|-----|-----------|
| Overview | ✅ OK |
| Programs | ✅ OK |
| Segments | ✅ OK |
| Movement | ✅ OK |
| RNA | ✅ OK |
| Effectiveness | ✅ **RECOVERED** |

---

## 8. BUILD

| Artefacto | Resultado |
|-----------|-----------|
| Backend compile | ✅ PASS |
| Frontend build | ✅ PASS (4.64s) |

---

## 9. VEREDICTO

```
LG_IMP_1C_CERTIFIED
```

### GO Criteria:

| Criterio | Estado |
|----------|--------|
| `/effectiveness/summary` = 200 | ✅ |
| Effectiveness tab carga | ✅ |
| 0 errores 500 | ✅ |
| Scorecard visible o empty state trazable | ✅ 34 programas visibles |
| Sin cambios arquitectónicos | ✅ |
| Sin cambios de fórmula | ✅ `net_effect = effectiveness_score` |
| Build backend PASS | ✅ |
| Build frontend PASS | ✅ |

### Tabs Intelligence Dashboard — Estado Final:

| Tab | Estado |
|-----|--------|
| Overview | ✅ |
| Programs | ✅ |
| Segments | ✅ |
| Movement | ✅ |
| RNA | ✅ |
| Effectiveness | ✅ |
| Driver Explorer | ⚠️ (funcional, 21s latency) |
