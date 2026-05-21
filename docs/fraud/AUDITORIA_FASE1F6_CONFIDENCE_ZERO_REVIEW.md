# AUDITORIA FASE 1F-6 — CONFIDENCE ZERO REVIEW

**Fecha**: 2026-05-20
**Estado**: **COMPLETO**

---

## 1. Hallazgo

39 de 43 casos abiertos tenian `case_confidence_score = 0` o `NULL`.

## 2. Analisis

| Tipo | Count | Regla unica | Confidence | Razon |
|---|---|---|---|---|
| BANK_ACCOUNT_CLUSTER | ~20 | SI | 0.0 | Regla bancaria sin senales conductuales |
| REPEATED_ORIGIN_PATTERN | ~13 | SI | 0.0 | repeat_count >=5 pero sin combos conductuales |
| REPEATED_ROUTE_SIGNATURE | ~6 | SI | 0.0 | 2 repeats sin low_duration/distance |

### Por que confidence=0 es correcto

El confidence scoring evalua exclusivamente senales **conductuales**:
- `+20` si driver new_or_unproven
- `+20` si 2+ high rules
- `+30` si 1 critical rule
- `+15` si repeated_route + low_duration/distance
- `+15` si short_trip_farming
- `+10` si burst_activity
- `+10` si coordinated_origin con new drivers

Los kept cases de `BANK_ACCOUNT_CLUSTER` no tienen ninguna de estas senales — son casos de clustering bancario evaluados por otro subsistema. Su confidence=0 es legitimo.

Los casos de `REPEATED_ORIGIN_PATTERN` con repeat_count >=5 tienen evidencia fuerte de repeticion pero la funcion `build_signal_bundle` no distingue magnitud (solo presencia de regla). Esto podria refinarse en futuro.

## 3. Accion tomada

- Script `fraud_recompute_case_confidence.py` creado y ejecutado
- 39 casos recalculados: todos quedaron en confidence=0 con `confidence_reason` explicito
- No se cerraron casos (los kept tienen evidencia suficiente desde su propio subsistema)

## 4. Recomendacion

1. Los casos BANK_ACCOUNT_CLUSTER deben mantener su severity original (evaluada por bank cluster logic)
2. Los casos REPEATED_ORIGIN_PATTERN con repeat_count alto podrian beneficiarse de un ajuste en confidence que considere magnitud
3. Considerar `confidence_reason` como filtro adicional en UI: "low_confidence" = requiere mas evidencia

## 5. Veredicto

**GO** — Confidence=0 explicado y justificado. Los casos son legitimos pero debiles desde perspectiva conductual. No requieren accion inmediata.
