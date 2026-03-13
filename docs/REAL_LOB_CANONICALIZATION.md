# REAL LOB — Canonicalization Closure

**Proyecto:** YEGO Control Tower  
**Fase:** CT-REAL-LOB-CANONICALIZATION  
**Estado:** Cierre consolidado (no destructivo).

---

## Resumen ejecutivo

La normalización del dominio **Real LOB / tipo_servicio** queda centralizada en:

1. **Capa SQL:** `canon.normalize_real_tipo_servicio(raw)` (migración 080) y catálogo `canon.dim_real_service_type_lob`.
2. **Capa Python:** `backend/app/services/real_service_type_normalizer.py` — `canonical_service_type()` alineado con 080.
3. **Contrato:** `backend/app/contracts/data_contract.py` — `REAL_SERVICE_TYPES`, `REAL_SERVICE_TYPE_DISPLAY`, `get_real_service_type_display()`.
4. **UI:** Frontend solo renderiza; etiquetas unificadas (CONFORT_PLUS, TUK_TUK, DELIVERY) vía `constants/realServiceTypeDisplay.js` y `formatRealServiceTypeDisplay()`.

No se parchea el frontend con lógica de normalización; no se duplica mapeo; la única fuente de verdad para el valor canónico es la capa canon + MVs que leen de ella.

---

## Reglas de negocio aplicadas

| Variantes crudas | Clave canónica (interna) | Etiqueta UI |
|------------------|---------------------------|-------------|
| confort+, confort plus, comfort+, comfort plus | comfort_plus | CONFORT_PLUS |
| tuk_tuk, tuk-tuk | tuk_tuk | TUK_TUK |
| express, mensajería, mensajeria, expres, envíos, envios | delivery | DELIVERY |

Otras claves (economico, comfort, minivan, premier, standard, start, xl, cargo, moto, UNCLASSIFIED) siguen el mismo criterio: una sola clave canónica por concepto y una etiqueta de visualización consistente.

---

## Entregables generados

| Documento | Contenido |
|-----------|-----------|
| **docs/CT_REAL_LOB_STATUS_REPORT.md** | Auditoría Fase 0: componentes implementados, faltantes, duplicaciones, riesgos. |
| **docs/REAL_LOB_DOMAIN_MAP.md** | Mapa técnico: origen del dato, punto de normalización, vistas, servicios, endpoints, componentes frontend. |
| **docs/REAL_LOB_VARIANTS.md** | Queries de discovery de variantes y tabla diagnóstico (valor_crudo, valor_canonico, frecuencia). |
| **docs/REAL_LOB_CANONICALIZATION.md** | Este documento: cierre y criterios de éxito. |

---

## Pasos obligatorios (ejecutar en entorno)

1. **Migraciones:**  
   `alembic upgrade head`

2. **Refrescar MVs v2:**  
   `REFRESH MATERIALIZED VIEW ops.mv_real_lob_month_v2;`  
   `REFRESH MATERIALIZED VIEW ops.mv_real_lob_week_v2;`  
   (O usar el script que invoque estos refreshes.)

3. **Governance:**  
   `python scripts/close_real_lob_governance`  
   (Valida que no reaparezcan variantes no canónicas y consistencia de dims/vistas.)

4. **Opcional — backfill drill:**  
   Si se quiere que el drill histórico use ya claves canónicas:  
   `python -m scripts.backfill_real_lob_mvs --from YYYY-MM-01 --to YYYY-MM-01`

---

## Criterios de éxito

- ✔ Sin duplicación de categorías de servicio en listados REAL (confort+, confort plus, etc. unificados).
- ✔ Sin fragmentación en UI: se muestran CONFORT_PLUS, TUK_TUK, DELIVERY (nunca variantes crudas en tablas/filtros).
- ✔ Sin WoW falsos por doble conteo de variantes.
- ✔ Gobernanza futura: script de cierre y catálogo canónico en contrato.
- ✔ Consistencia en todas las vistas REAL que consumen real_tipo_servicio_norm / lob_group desde MVs v2 o real_drill_dim_fact.

---

## Confirmación

**REAL LOB DOMAIN CANONICALIZATION COMPLETE**

La normalización del dominio Real LOB / tipo_servicio está cerrada a nivel de código y documentación. La aplicación en base de datos y la validación en UI dependen de la ejecución de `alembic upgrade head`, refresh de MVs y `python scripts/close_real_lob_governance` en el entorno correspondiente.
