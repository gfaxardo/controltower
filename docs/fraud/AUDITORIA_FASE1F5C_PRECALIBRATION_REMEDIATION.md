# AUDITORIA FASE 1F-5C — PRE-CALIBRATION REMEDIATION

**Fecha**: 2026-05-20
**Estado**: PENDIENTE EJECUCION (script listo)

---

## 1. Script

`backend/scripts/fraud_remediate_precalibration_cases.py`

### Modo de uso

```bash
# Dry run (preview)
python backend/scripts/fraud_remediate_precalibration_cases.py --dry-run true --config-version trip_behavior_v1_calibrated

# Commit por chunks
python backend/scripts/fraud_remediate_precalibration_cases.py --dry-run false --config-version trip_behavior_v1_calibrated --batch-size 25

# Resume desde batch fallido
python backend/scripts/fraud_remediate_precalibration_cases.py --dry-run false --batch-size 10 --resume-from 3
```

## 2. Resultados estimados

| Metrica | Valor |
|---|---|
| pre_calibration_cases | ~223 (open, no calibration_status) |
| repeated_origin solo | ~180 (downgraded) |
| repeated_route solo | ~15 (downgraded) |
| long_trip solo | ~10 (downgraded) |
| combo cases (kept) | ~43 (bank cluster + behavioral combos) |
| downgraded | ~205 |
| closed | ~205 |
| kept | ~43 |
| errors | 0 (esperado) |

## 3. Que hace la remediacion

1. **Marca** todos los casos pre-calibration con `calibration_status = 'pre_calibration'` y `calibration_version = 'trip_behavior_v1_calibrated'`
2. **Downgrade** casos repeated_origin solo (con repeat_count < 5):
   - `calibration_status = 'recalibrated_downgraded'`
   - `status = 'closed'`
   - `severity = 'low'`
   - `review_decision = 'rejected'`
   - `reviewed_by = 'system_calibration_1f5c'`
3. **Downgrade** casos repeated_route solo y long_trip solo (similar)
4. **Keep** casos con evidencia combinada (2+ rule codes):
   - `calibration_status = 'recalibrated_kept'`

## 4. Que NO hace

- NO borra registros
- NO toca casos bancarios sinteticos (a menos que sean pre-calibration)
- NO modifica casos ya calibrados
- NO ejecuta acciones reales
- NO modifica Omniview ni Plan vs Real

## 5. Batching

Para evitar timeout DB:
- `--batch-size 25` es el default
- Si falla, reducir a `--batch-size 10`
- `--resume-from N` para continuar desde el batch N

## 6. Verificacion post-remediation

```sql
-- Verificar casos downgraded
SELECT COUNT(*) FROM fraud.risk_cases
WHERE calibration_status = 'recalibrated_downgraded';

-- Verificar casos kept
SELECT COUNT(*) FROM fraud.risk_cases
WHERE calibration_status = 'recalibrated_kept';

-- Verificar total marcados
SELECT calibration_status, COUNT(*) FROM fraud.risk_cases
WHERE calibration_status IS NOT NULL
GROUP BY calibration_status;
```
