# AUDITORIA FASE 1F-5D — REMEDIATION COMMIT

**Fecha**: 2026-05-20
**Estado**: **COMPLETO**

---

## 1. Ejecucion

| Metrica | Valor |
|---|---|
| Script | `fraud_remediate_precalibration_cases.py` |
| --dry-run | false |
| --config-version | trip_behavior_v1_calibrated |
| --batch-size | 25 |
| Casos procesados | 256 |
| Batches totales | 11 |
| Errores | 0 |

## 2. Clasificacion

| Tipo | Count |
|---|---|
| repeated_origin only (low count) | ~138 downgraded |
| repeated_route only | 1 downgraded |
| long_trip outlier only | 84 downgraded |
| Combo cases (kept) | 33 |
| **Total downgraded** | **223** |
| **Total kept** | **33** |

## 3. Resultado DB

| calibration_status | status | count |
|---|---|---|
| `recalibrated_downgraded` | closed | 223 |
| `recalibrated_kept` | open | 33 |
| None | closed | 1 (driver003 test data) |

- calibration_version = `trip_behavior_v1_calibrated`: 256 casos
- Casos cerrados totales: 224
- Casos abiertos restantes: 33

## 4. Sin errores

- Sin timeout (batch-size=25 efectivo)
- Sin casos borrados
- Sin casos no relacionados tocados
- Sin modificacion de casos ya calibrados

## 5. Veredicto

**GO** — Remediation completada exitosamente.
