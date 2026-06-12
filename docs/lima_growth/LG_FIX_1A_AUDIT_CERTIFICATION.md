# LG_FIX_1A_AUDIT_CERTIFICATION — Audit Certification

**Generated:** 2026-06-12T19:36  
**Auditor:** opencode  
**Fase:** LG-FIX-1A — TAB / ENDPOINT / FACT AUDIT  
**Alcance:** Diagnóstico completo, sin modificaciones de código.

---

## 1. Estado Real por Tab

| Tab | Backend Status | Data | UI Display | Root Cause |
|-----|---------------|------|-----------|------------|
| **FreshnessBanner** | CRITICAL (real) | correcta | CRITICAL, 12 broken | TRUE_CRITICAL: pipeline no ejecutado |
| **Overview** | 200 OK | parcial | Drivers=148167 ✓, Con Programa=0 ✗, Activos=0 ✗ | PAYLOAD_MISMATCH |
| **Programs** | 200 OK | data exists (17K, 7K, 2K, 0) | Eligible=0 ✗, Priorizados=0 ✗ | PAYLOAD_MISMATCH |
| **Segments** | 200 OK | total_drivers=0 (date mismatch) | "No hay datos" ✗ | DATE_MISMATCH + PAYLOAD_MISMATCH |
| **Movement** | 200 OK (summary/stats/matrix), 404 (records), 500 (winners/losers) | stats OK, summary=0s | KPIs OK, Records vacío, Winners/Losers error | DATE_MISMATCH + ENDPOINT_ERROR |
| **RNA** | 200 OK (loyalty), 500 (priority/pilot) | loyalty data OK (wrong domain) | Total=0 ✗, sin prioridad | WRONG_ENDPOINT + ENDPOINT_FAILING |
| **Driver Explorer** | 200 OK (21s!) | OK con filtro | "Use filtros" (by design) | NEEDS_FILTER + SLOW |
| **Effectiveness** | 500 | N/A | Error 500 ✗ | MISSING_TABLE + 500 |

---

## 2. Endpoints que Fallan

| Endpoint | HTTP | Categoría |
|----------|------|-----------|
| `GET /yego-lima-growth/movement/records` | **404** | Ruta no registrada |
| `GET /yego-lima-growth/movement-analytics/winners` | **500** | Tabla v2_movement_fact vacía |
| `GET /yego-lima-growth/movement-analytics/losers` | **500** | Tabla v2_movement_fact vacía |
| `GET /yego-lima-growth/rna-priority/summary` | **500** | Tabla rna_priority_fact no existe |
| `GET /yego-lima-growth/rna-priority/drivers` | **500** | Tabla rna_priority_fact no existe |
| `GET /yego-lima-growth/rna-pilot/summary` | **500** | Tabla rna_pilot_measurement_fact no existe |
| `GET /yego-lima-growth/effectiveness/summary` | **500** | Tabla effectiveness casi vacía + sin error handling |

**7 de 27 endpoints fallan (26%).**

---

## 3. Endpoints Lentos (>5s)

| Endpoint | Latencia | Severidad |
|----------|----------|-----------|
| `/drivers/activity-summary` | 21,163ms | CRITICAL |
| `/operational-truth` | 9,469ms | HIGH |
| `/programs/status` | 4,455ms | MEDIUM |

---

## 4. Facts Vacías o con Datos Insuficientes

| Tabla | Estado | Rows | Último Dato |
|-------|--------|------|------------|
| `yego_lima_v2_effectiveness_fact` | **VACÍA** | 0 | NULL |
| `yego_lima_v2_movement_fact` | **VACÍA** | 0 | NULL |
| `yego_lima_impact_tracking` | **VACÍA** | 0 | NULL |
| `program_effectiveness_fact` | **CASI VACÍA** | 10 | 2026-06-10 |
| `driver_movement_fact` | STALE | 68,473 | 2026-06-10 (faltan 11/12) |
| `yego_lima_driver_lifecycle_daily` | STALE | 273,908 | 2026-06-10 (faltan 11/12) |
| `yego_lima_driver_taxonomy_v2_daily` | STALE | 273,908 | 2026-06-10 (faltan 11/12) |
| `rna_priority_fact` | **NO EXISTE** | — | — |
| `rna_pilot_measurement_fact` | **NO EXISTE** | — | — |

---

## 5. Date Mismatches

| Endpoint | UI pide | DB tiene | Gap |
|----------|---------|---------|-----|
| taxonomy/summary | 2026-06-12 | 2026-06-10 | 2 días |
| movement/summary | 2026-06-12 | 2026-06-10 | 2 días |
| movement/records | 2026-06-12 | 2026-06-10 | 2 días |

Pipeline V2 no ejecutado para 2026-06-11 y 2026-06-12.

---

## 6. Payload Mismatches

| Tab | Campos con mismatch |
|-----|-------------------|
| Overview | `drivers_with_program`, `active_programs`, `program_distribution`, `channel_utilization` |
| Programs | `eligible_drivers`→`eligible_total`, `prioritized`→`prioritized_total`, `queue_count`→`queued_total` |
| Segments | `lifecycle_distribution`→`distributions`, estructura interna diferente |
| RNA | Dominio equivocado (loyalty vs rna) |

---

## 7. Root Cause por Tab (Resumen)

| Tab | Primaria | Secundaria |
|-----|---------|-----------|
| FreshnessBanner | Pipeline no ejecutado | — |
| Overview | Backend schema drift | Fallbacks a truth rotos |
| Programs | Backend schema drift (rename de campos) | — |
| Segments | Pipeline no ejecutado (date) | Backend schema drift (key rename) |
| Movement | Pipeline no ejecutado (date) | Ruta /records no registrada, v2_movement_fact vacía |
| RNA | Tablas RNA no existen en DB | UI consume endpoint equivocado (loyalty) |
| Driver Explorer | Endpoint lento (21s) | Empty-by-default UX |
| Effectiveness | Tabla effectiveness vacía | Sin error handling en backend |

---

## 8. Fix Plan para LG-FIX-1B

**P0 (Crítico):**
1. Ejecutar Pipeline V2 para 2026-06-11 y 2026-06-12
2. Fix Effectiveness: backend error handling + poblar tabla
3. Fix Movement: agregar ruta /records, poblar v2_movement_fact

**P1 (Alto):**
4. Fix ProgramsTab: `eligible_total`, `prioritized_total`, `queued_total`
5. Fix OverviewTab: `eligible_total`, `by_program[]`
6. Fix SegmentsTab: `distributions.operational_segment`
7. RNA: crear tablas + endpoints + redirigir UI

**P2 (Bajo):**
8. Optimizar Driver Explorer (21s → <3s)
9. Auto-cargar primeras filas en Driver Explorer
10. Usar `program_name` del payload

---

## 9. Veredicto

```
LG_FIX_1A_AUDIT_COMPLETE
```

**La auditoría de diagnóstico está completa.** Se identificaron:

- **3 causas raíz:** Pipeline gap (2 días), Backend↔Frontend schema drift (4 tabs), Tablas/endpoints faltantes (RNA, effectiveness, movement records).
- **7 endpoints fallando** con status 404 o 500.
- **3 endpoints excesivamente lentos** (>5s, uno a 21s).
- **3 tablas completamente vacías** en producción.
- **2 tablas RNA inexistentes.**

**LG-FIX-1B debe proceder con el fix plan en el orden P0 → P1 → P2.**

---

## Audit Trail

| Documento | Path |
|-----------|------|
| Route Audit | `docs/lima_growth/LG_UI_ROUTE_AUDIT.md` |
| Tab-Endpoint Map | `docs/lima_growth/LG_FIX_1A_TAB_ENDPOINT_MAP.md` |
| Endpoint Smoke | `docs/lima_growth/LG_FIX_1A_ENDPOINT_SMOKE.md` |
| Fact Rowcount | `docs/lima_growth/LG_FIX_1A_FACT_ROWCOUNT_AUDIT.md` |
| Date Parameter | `docs/lima_growth/LG_FIX_1A_DATE_PARAM_AUDIT.md` |
| Payload Shape | `docs/lima_growth/LG_FIX_1A_PAYLOAD_SHAPE_AUDIT.md` |
| Root Cause Matrix | `docs/lima_growth/LG_FIX_1A_ROOT_CAUSE_MATRIX.md` |
| Fix Plan | `docs/lima_growth/LG_FIX_1A_FIX_PLAN.md` |
| Certification | `docs/lima_growth/LG_FIX_1A_AUDIT_CERTIFICATION.md` |
