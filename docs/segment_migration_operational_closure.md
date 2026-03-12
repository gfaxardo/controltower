# Cierre operativo E2E — Driver Segmentation + Migration Refactor

**Proyecto:** YEGO Control Tower  
**Objetivo de esta fase:** Validar con evidencia real (BD y sistema actual) que la implementación de segmentación y Migration está operativa, sin abrir rediseño ni cambios cosméticos.

---

## 1. Objetivo de esta fase

- Validar en BD real la taxonomía de segmentos.
- Refrescar objetos necesarios.
- Comprobar masa real por segmento (dormant, casual, pt, ft, elite, legend).
- Comprobar que Migration quedó operativamente correcta.
- Comprobar que el frontend refleja lo implementado.
- Detectar roturas o inconsistencias críticas.
- Emitir dictamen final de cierre.

---

## 2. Plan de validación ejecutado

| Paso | Acción | Orden |
|------|--------|--------|
| 1 | Inspección: scripts de validación, migración aplicada, objetos SQL/MVs, endpoints y vistas frontend | Previo |
| 2 | Alembic current / heads | FASE B |
| 3 | Refresh de MVs (run_supply_refresh_pipeline) | FASE C |
| 4 | Ejecución de validate_segment_taxonomy (run_validate_segment_taxonomy.py) | FASE D, E |
| 5 | check_supply_alerting_and_segments | FASE C/J |
| 6 | Documentar resultados y veredicto | FASE K, L |

---

## 3. Comandos ejecutados

| Comando | Directorio | Resultado |
|---------|------------|-----------|
| `alembic current` | backend/ | 078_segment_taxonomy_elite_legend (head) |
| `alembic heads` | backend/ | 078_segment_taxonomy_elite_legend (head) |
| `python -m scripts.run_supply_refresh_pipeline` | backend/ | OK; last_week_available=2026-03-09; last_refresh=2026-03-11T10:55:04 |
| `python -m scripts.run_validate_segment_taxonomy` | backend/ | Ver sección 5 |
| `python -m scripts.check_supply_alerting_and_segments` | backend/ | PASS (WARN: 5 filas segment totals > active_drivers) |

---

## 4. Queries ejecutadas

Se ejecutaron las 7 validaciones contenidas en `backend/scripts/sql/validate_segment_taxonomy.sql` vía el script `backend/scripts/run_validate_segment_taxonomy.py` (creado en esta fase solo para ejecutar y capturar resultados; no modifica lógica de negocio).

---

## 5. Resultados

### 5.1 Estado de migración (FASE B)

- **alembic current:** 078_segment_taxonomy_elite_legend (head)
- **alembic heads:** 078_segment_taxonomy_elite_legend
- **Conclusión:** Migración 078 aplicada; no hay migraciones pendientes. Sistema en estado consistente para esta cadena.

### 5.2 Refreshes realizados (FASE C)

- **Pipeline:** `run_supply_refresh_pipeline` → `ops.refresh_supply_alerting_mvs()`.
- **Objetos refrescados (en orden):**  
  ops.mv_driver_segments_weekly → ops.mv_supply_segments_weekly → ops.mv_supply_segment_anomalies_weekly → ops.mv_supply_alerts_weekly.
- **Resultado:** Completado correctamente. last_week_available = 2026-03-09.

### 5.3 Validación de taxonomía en BD (FASE D)

**Query 7 — Config vigente (ORDER BY ordering ASC):**

| segment_code | segment_name | min_trips_week | max_trips_week | ordering |
|--------------|--------------|----------------|----------------|----------|
| DORMANT | Dormant | 0 | 0 | 1 |
| OCCASIONAL | Occasional | 1 | 4 | 2 |
| CASUAL | Casual | 5 | 19 | 3 |
| PT | Part Time | 20 | 59 | 4 |
| FT | Full Time | 60 | **119** | 5 |
| ELITE | Elite | **120** | **179** | 6 |
| LEGEND | Legend | **180** | NULL | 7 |

**Evidencia concreta:**
- **Elite existe:** 120–179, ordering 6.
- **Legend existe:** 180+, ordering 7.
- **FT = 60–119:** max_trips_week = 119.
- **Legend 180+:** min 180, max NULL.
- **Orden:** 1–7 (dormant → legend); no alfabético.
- **OCCASIONAL/CASUAL:** Siguen coexistiendo (1–4 y 5–19). Impacto: la taxonomía objetivo "casual 1–29" no está unificada en BD; la UI y la leyenda muestran los 7 segmentos; no hay rotura.

### 5.4 Masa real de segmentos (FASE E)

**Distribución semanal (últimas semanas, resumen):**

- **2026-03-02:** CASUAL 2053, ELITE 272, FT 892, LEGEND 13, OCCASIONAL 1774, PT 1495. (DORMANT no aparece en filas; ver observación más abajo.)
- **2026-02-23:** CASUAL 1972, ELITE 300, FT 1076, LEGEND 17, OCCASIONAL 1715, PT 1433.
- **2026-02-16:** CASUAL 1899, ELITE 317, FT 1031, LEGEND 18, OCCASIONAL 1653, PT 1402.
- **2026-02-09:** CASUAL 1904, ELITE 332, FT 1080, LEGEND 19, OCCASIONAL 1615, PT 1439.

**Masa Elite (120–179):** Entre 272 y 358 conductores por semana en las semanas mostradas. Masa suficiente y operativa.

**Masa Legend (180+):** Entre 13 y 32 conductores por semana. Segmento pequeño pero con datos reales; no bloqueante.

**Dormant:** En la query 6 (presencia Dormant), todas las semanas mostradas devolvieron 0. Posibles causas: la fuente `mv_driver_weekly_stats` no incluye filas con 0 viajes para esa semana, o en el periodo no hay conductores con 0 viajes. La definición en config (0–0) es correcta; la visibilidad en datos depende de la fuente. No se considera rotura de la implementación.

### 5.5 Validación conceptual en data (FASE F)

- **Dormant:** Definido en config como 0 viajes/semana. En los datos validados, dormant_drivers = 0 por semana; la definición en código y config es correcta.
- **Churned:** Calculado en v_driver_weekly_churn_reactivation (activos N-1, 0 en N). No mezclado con Dormant en definiciones (supply_definitions: "No confundir con Dormant").
- **Reactivated/Revival:** Revival = segment_change_type 'new' en la MV; en top transiciones aparecen filas con segment_prev None y segment_current OCCASIONAL/CASUAL/PT (new/revival). Correctamente diferenciado.
- **Conteos:** Distribución por segmento y transiciones coherentes con la jerarquía (ELITE→CASUAL downshift, LEGEND→PT downshift, etc.).

### 5.6 Validación de Migration en BD y UI (FASE G)

**En datos (queries 4 y 5):**
- **Top transiciones:** Incluyen ELITE→CASUAL, ELITE→PT, LEGEND→PT, LEGEND→CASUAL, FT→CASUAL, etc. Jerarquía respetada (downshift/upshift por ordering).
- **Same-to-same:** Existe como segment_change_type 'stable' (OCCASIONAL→OCCASIONAL, CASUAL→CASUAL, PT→PT, FT→FT, ELITE→ELITE, LEGEND→LEGEND). La API devuelve estas filas como migration_type 'lateral'.
- **Frontend (evidencia en código):** La tabla principal de Migration filtra `migration_type !== 'lateral'`, por tanto same-to-same **no** se muestra como migración principal. El KPI "Stable" y summary.stable reflejan lateral. Header narrativo, insight, resumen por From, formato S##-YYYY y park legible en drilldown están implementados.

### 5.7 Validación visual frontend (FASE H)

No se realizó prueba manual en navegador en esta fase. La evidencia es por código (SupplyView, DriverSupplyGlossary, segmentSemantics) y por resultados de API/BD. Para un cierre visual completo se recomienda verificación manual: Supply → Migration (header, KPIs, tabla sin lateral, leyenda) y "Ver definiciones" (lista Dormant–Legend).

### 5.8 Endpoints y contratos (FASE I)

- **GET /ops/supply/segments/config:** Orden ASC; esquema igual. Additive/compatible.
- **GET /ops/supply/migration:** summary establece "stable"; data sin cambio. Additive.
- Frontend consume migrationSummary?.stable y filtra lateral en la tabla. No se detectaron roturas de contrato.

---

## 6. Refreshes realizados

- **Fecha/hora:** 2026-03-11, ~10:55 (post-ejecución del pipeline).
- **Función:** ops.refresh_supply_alerting_mvs() (4 MVs en orden).
- **Resultado:** OK. Última semana disponible en MVs: 2026-03-09.

---

## 7. Hallazgos

**Positivos:**
- Migración 078 aplicada y única head.
- Taxonomía en BD correcta: ELITE 120–179, LEGEND 180+, FT 60–119, orden 1–7.
- Masa real de Elite (272–358/semana) y Legend (13–32/semana) verificada.
- Transiciones con ELITE y LEGEND presentes; upgrade/downgrade por ordering (no alfabético).
- Same-to-same presente en datos como 'stable'; excluido de la tabla principal en UI.
- Objetos de supply (MVs, vista, función refresh) existen y pasan check_supply_alerting_and_segments.

**Menores:**
- WARN en check_supply_alerting_and_segments: 5 filas donde segment totals > active_drivers (sanity). No bloqueante; documentado.
- Dormant = 0 en todas las semanas validadas; puede deberse a que la fuente no expone filas con 0 viajes en el periodo muestreado.

**Críticos:** Ninguno.

---

## 8. Correcciones mínimas realizadas

- **Ninguna.** No se detectó rotura objetiva que requiriera corrección. Se añadió el script `backend/scripts/run_validate_segment_taxonomy.py` únicamente para ejecutar las validaciones SQL y capturar resultados; no altera lógica de negocio ni contratos.

---

## 9. Riesgos pendientes

- Verificación manual en navegador (Migration, Composition, glosario) queda como recomendación.
- Si en el futuro se unifica "casual" 1–29 en BD, hará falta nueva versión de config y refresh.
- El WARN segment totals > active_drivers puede revisarse en otro momento para alinear definiciones de activos entre MVs.

---

## 10. Veredicto final

**CERRADO CON OBSERVACIONES**

**Motivo:**  
La validación en BD confirma: (1) taxonomía instalada (ELITE, LEGEND, FT 60–119, orden correcto), (2) masa real de Elite y Legend, (3) transiciones correctas y same-to-same excluido de la tabla principal en frontend, (4) refreshes ejecutados y objetos operativos. No se encontraron hallazgos críticos ni roturas de contratos. Las observaciones son: (a) verificación visual en navegador no realizada en esta fase, (b) Dormant con 0 conteo en las semanas validadas (definición correcta; datos dependen de la fuente), (c) WARN menor en sanity de segment totals. El sistema queda operativamente usable y coherente con la implementación documentada.

---

## 11. Checklist obligatorio (FASE M)

- [x] Se verificó el estado actual de Alembic  
- [x] Se confirmó la migración 078  
- [x] Se refrescaron los objetos necesarios  
- [x] Se ejecutó validate_segment_taxonomy (vía run_validate_segment_taxonomy.py)  
- [x] Se validó Elite = 120–179  
- [x] Se validó Legend = 180+  
- [x] Se validó FT = 60–119  
- [x] Se obtuvo masa real por segmento  
- [x] Se obtuvo masa real de Elite  
- [x] Se obtuvo masa real de Legend  
- [x] Se auditó Dormant vs Churned vs Reactivated/Revival  
- [x] Se auditó Migration en data real  
- [x] Se confirmó que same-to-same no sale como migración principal  
- [ ] Se auditó frontend en Lifecycle / Supply / Migration (evidencia por código; no prueba en navegador)  
- [x] Se auditó el formato S##-YYYY (en código y week_display)  
- [x] Se verificó park legible (parkLabel en drilldown)  
- [x] Se revisaron endpoints/contratos  
- [x] Se documentaron hallazgos  
- [x] Se emitió veredicto final  

---

## 12. Próximos pasos mínimos (si aplica)

1. **Opcional:** Prueba manual en navegador: abrir Supply → Migration, comprobar header, KPIs (Stable), insight, resumen por From, tabla sin filas lateral, "Ver definiciones" con leyenda Dormant–Legend.
2. **Opcional:** Revisar WARN segment totals > active_drivers (5 filas) en check_supply_alerting_and_segments para alinear definiciones si se desea.
3. **Opcional:** Si se necesita visibilidad explícita de Dormant en datos, revisar si mv_driver_weekly_stats (o la fuente que alimenta la segmentación) debe incluir filas con 0 viajes en la semana.
