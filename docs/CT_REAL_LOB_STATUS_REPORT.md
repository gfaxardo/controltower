# CT REAL LOB — STATUS REPORT (Fase 0 Auditoría)

**Fecha:** 2025-03-13  
**Objetivo:** Diagnóstico de la iteración previa de canonicalización antes de aplicar cambios.

---

## 1. Componentes ya implementados

| Componente | Ubicación | Estado |
|------------|-----------|--------|
| **Función SQL canónica** | `canon.normalize_real_tipo_servicio(raw text)` | Migración **080_real_lob_canonical_service_type_unified**. Unaccent, +→_plus, espacios/guiones→_; mapeo a comfort, comfort_plus, tuk_tuk, delivery, etc. |
| **Catálogo canónico** | `canon.dim_real_service_type_lob` | Semilla en 080 (comfort_plus, tuk_tuk, delivery, economico, minivan, premier, …). ON CONFLICT DO UPDATE. |
| **Desactivación variantes antiguas** | 080 | UPDATE dim_real_service_type_lob SET is_active=false WHERE service_type_norm IN ('confort', 'confort+', 'tuk-tuk', 'mensajería', 'express', …). |
| **Normalizador Python** | `backend/app/services/real_service_type_normalizer.py` | `canonical_service_type()`, `normalized_service_type()`, `_normalized_key()`, `_CANONICAL_MAP` alineado con 080. |
| **Script de cierre** | `backend/scripts/close_real_lob_governance.py` | Inspección Alembic, objetos BD, refresh MVs (mv_real_lob_month_v2, week_v2), validaciones (dims, vista, canonical_no_dupes). |
| **Vistas que consumen canon** | `ops.v_real_trips_service_lob_resolved`, `ops.v_real_trips_with_lob_v2` | Definidas en 064/044/090; usan `canon.normalize_real_tipo_servicio` (090) o lógica equivalente. |
| **MVs v2** | `ops.mv_real_lob_month_v2`, `ops.mv_real_lob_week_v2` | Leen de v_real_trips_with_lob_v2 → columnas real_tipo_servicio_norm, lob_group. |
| **Documentación existente** | `docs/CT_REAL_LOB_CANONICALIZATION_MAP.md`, `docs/CT_REAL_LOB_CANONICALIZATION_ENTREGABLES.md` | Mapa técnico, fuentes, vistas, servicios, queries de diagnóstico. |

---

## 2. Componentes faltantes o por consolidar

| Componente | Observación |
|------------|-------------|
| **Enumeración oficial en contrato** | `data_contract.py` tiene `TIPO_SERVICIO_MAPPING` (Plan/legacy) pero no `REAL_SERVICE_TYPES` ni mapeo canónico→display (CONFORT_PLUS, TUK_TUK, DELIVERY) para UI. |
| **Uso explícito del normalizador Python en servicios** | Los servicios REAL (real_lob_v2_data_service, real_lob_filters_service, real_lob_drill_pro_service) leen **de MVs/vistas** que ya exponen `real_tipo_servicio_norm`; no llaman a `canonical_service_type()` en tiempo de request. La normalización ocurre en **capa SQL** (canon.normalize_real_tipo_servicio) al poblar vistas/MVs. No hay duplicación de lógica en Python para lecturas. |
| **Display label en UI** | El prompt pide que en UI aparezca CONFORT_PLUS, TUK_TUK, DELIVERY. Hoy las vistas devuelven `comfort_plus`, `tuk_tuk`, `delivery`. Falta una capa de **display** (mapeo canonical → label) si se desea mostrar en mayúsculas. |
| **Governance script: detección de variantes nuevas** | `close_real_lob_governance` valida `canonical_no_dupes` (que no reaparezcan confort+, tuk-tuk, etc. en v_real_trips_with_lob_v2). No ejecuta un query tipo “variantes nuevas en trips_all que no mapean a canon”. Se puede añadir un check opcional. |

---

## 3. Posibles duplicaciones

| Ubicación | Riesgo |
|-----------|--------|
| **Migraciones antiguas (043, 047, 050, 053)** | Contienen CASE WHEN inline con 'confort+', 'mensajería', 'express'. Esas definiciones fueron **reemplazadas** por vistas posteriores (064, 080, 090) que usan `canon.normalize_real_tipo_servicio`. No se deben volver a tocar esas migraciones. |
| **ops.normalized_service_type (070, 072, 073)** | Función en esquema `ops`; en 080 la fuente de verdad es `canon.normalize_real_tipo_servicio`. Algunas vistas podrían seguir referenciando ops.normalized_service_type; verificar que la ruta activa (v_real_trips_with_lob_v2 → MVs v2) use solo canon. |
| **data_contract.TIPO_SERVICIO_MAPPING** | Usado para Plan/LOB; no reemplazar por el canon REAL. Añadir junto a él `REAL_SERVICE_TYPES` y opcionalmente `REAL_SERVICE_TYPE_DISPLAY` para REAL. |

---

## 4. Riesgos de doble normalización

- **Si se añade normalización en frontend:** Riesgo de que el usuario vea valores distintos a los de la API o que se aplique dos veces (raw → canon en BD, luego canon → “display” en frontend). Mitigación: **no normalizar en frontend**; solo mostrar el valor que viene del API. Si se quiere label “CONFORT_PLUS”, usar un **mapeo de visualización** (canonical_key → display_label) en un solo lugar (contrato o frontend).
- **Si se cambia la clave canónica de comfort_plus a CONFORT_PLUS en BD:** Requeriría migración que actualice `canon.dim_real_service_type_lob` y posiblemente datos ya materializados. Riesgo alto. Recomendación: **mantener claves internas** (comfort_plus, tuk_tuk, delivery) y exponer display (CONFORT_PLUS, TUK_TUK, DELIVERY) solo en contrato/UI.

---

## 5. Conclusión Fase 0

- La **capa canónica ya está implementada** en migración 080 y en `real_service_type_normalizer.py`.
- La **cadena de datos** (trips → canon.normalize_real_tipo_servicio → v_real_trips_with_lob_v2 → MVs v2) está definida; falta **aplicar** `alembic upgrade head` y ejecutar refresh MVs + opcional backfill.
- **Faltan:** (1) Enumeración y display en `data_contract.py` para REAL; (2) opcional refuerzo del script de governance para detectar variantes nuevas; (3) mapeo de visualización en frontend (canonical → CONFORT_PLUS/TUK_TUK/DELIVERY) si se desea que la UI muestre esas etiquetas.
