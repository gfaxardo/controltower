# Debug forense: regresión módulo REAL

## FASE 0 — Last known good state vs current state

### Fuente de verdad
- **HEAD (last commit):** `b1e3b0e` — "Real vs projection, hourly-first, real operational hardening y documentación"
- **Current:** Working tree con cambios sin commitear de este chat

### Tabla last_known_good_state vs current_state

| Área | Last known good (HEAD) | Current (working tree) |
|------|------------------------|-------------------------|
| **Backend get_drill** | Query a MV_DIM sin campo cancelaciones; sin normalización abs(margen) en agg_detail | Query sin cancelled_trips; agg_detail con cancelaciones=0; normalización abs(margen) |
| **Backend get_drill_children** | Sin park_label; sin cancelaciones en filas; posiblemente query con cancelled_trips (si existía en otro branch) | park_label; cancelaciones=0; query sin cancelled_trips; normalización margen |
| **Backend margin-quality** | No existía | Rutas GET /ops/real-margin-quality y /ops/real/margin-quality; POST /run; import real_margin_quality_service |
| **Frontend REAL tab** | Sin getRealMarginQuality; sin RealMarginQualityCard; sin marginQualityAffected; sin columnas Cancel./badge cobertura | getRealMarginQuality en api.js; RealMarginQualityCard en App; useEffect margin-quality en RealLOBDrillView; park_label en dropdown; columnas cancelaciones y badge "Cobertura incompleta" |
| **Drill loading** | loadSummary + comparatives + parks + periodSemantics | Igual + getRealMarginQuality (2 llamadas: card + drill badges) |

### Qué funcionaba en HEAD
- Drill base (getRealLobDrillPro), parks, period-semantics, comparatives.
- Sin dependencia de margin-quality ni de cancelaciones en payload.

### Qué no estaba en HEAD y no rompía
- Margin-quality, card de calidad de margen, badge cobertura incompleta, cancelaciones en tabla, park_label canónico.

---

## FASE 1 — Inventario de cambios sospechosos

| Categoría | Archivo | Función / zona | Propósito original | Riesgo regresión | Sospecha |
|-----------|---------|----------------|--------------------|------------------|----------|
| **A. Backend drill** | real_lob_drill_pro_service.py | get_drill: agg_detail query | Quitar cancelled_trips; añadir cancelaciones=0 | Bajo (evita 500) | Baja |
| | real_lob_drill_pro_service.py | get_drill_children: query principal + prev_ps | Quitar cancelled_trips; cancelaciones=0; park_label | Bajo (evita 500) | Baja |
| | real_lob_drill_pro_service.py | _add_row_comparative / _add_child_comparative | Campos cancelaciones_prev, cancelaciones_delta_pct, cancelaciones_trend | Medio (payload nuevo) | Media |
| **B. Backend quality** | ops.py | GET /real-margin-quality, /real/margin-quality | Nuevo endpoint | Alto (404 si ruta no registrada; 500 si servicio falla) | **Alta** |
| | ops.py | Import get_margin_quality_full | Carga real_margin_quality_service | Alto (si el módulo falla al importar, router puede no registrar rutas) | **Alta** |
| **C. Frontend REAL** | RealLOBDrillView.jsx | useEffect getRealMarginQuality | Badge "Cobertura incompleta" | Alto (request en mount; timeout 15s o 404 puede dejar percepción de carga lenta) | **Alta** |
| | App.jsx | RealMarginQualityCard | Card calidad de margen | Alto (otra llamada getRealMarginQuality; loading hasta respuesta) | **Alta** |
| | api.js | getRealMarginQuality | Llama /ops/real-margin-quality | Medio (si 404, catch en componentes; si cuelga, 15s timeout) | Media |
| | RealLOBDrillView.jsx | Columnas cancelaciones, colspan 15 | UI depende de row.cancelaciones, row.cancelaciones_trend | Bajo (backend ya envía 0) | Baja |
| **D. DB/populate** | (no modificado en diff de este chat para lógica crítica) | — | — | — | — |

---

## FASE 2 — Debug runtime (instrumentación)

Se añaden logs para:
1. Secuencia de requests al abrir REAL y al cargar drill.
2. Qué request sale, cuándo entra, cuánto tarda, si responde o catch.
3. Request(s) que dejan la UI en "cargando".

(Ver instrumentación en código.)

---

## FASE 3–8 — Por completar tras evidencia de logs

- FASE 3: Bisección por bloques (drill solo, +parks, +children, +margin-quality, +badges).
- FASE 4: Causa raíz.
- FASE 5: Estrategia de recuperación mínima.
- FASE 6: Validación post-fix.
- FASE 7: Reintroducción controlada (solo si estable).
- FASE 8: Entrega final.
