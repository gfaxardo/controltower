# CT-REAL-HOURLY-FIRST — Cierre Final

**Fecha**: 2026-03-15
**Estado**: CERRADO ✓

## Governance Final

```
fact_view_ok:              True
dims_populated:            True
canonical_no_dupes:        True
hourly_populated:          True   (599,871 filas)
day_populated:             True   (59,482 filas)
week_populated:            True   (2,322 filas)
month_populated:           True   (746 filas)
cancel_reason_norm_populated: True
trip_duration_reasonable:  True
week_no_raw_deps:          True
month_no_raw_deps:         True
OVERALL:                   OK
```

## Artefactos creados

### Migración
- `backend/alembic/versions/099_real_hourly_first_architecture.py`

### Objetos BD
| Objeto | Tipo | Filas | Propósito |
|--------|------|-------|-----------|
| `canon.normalize_cancel_reason()` | FUNCTION | — | Normaliza motivo_cancelacion |
| `canon.cancel_reason_group()` | FUNCTION | — | Agrupa motivos en categorías |
| `ops.v_trips_real_canon_120d` | VIEW (recreada) | — | Ahora incluye motivo_cancelacion |
| `ops.v_real_trip_fact_v2` | VIEW | — | Capa canónica por viaje |
| `ops.mv_real_lob_hour_v2` | MV | 599,871 | Agregación horaria |
| `ops.mv_real_lob_day_v2` | MV | 59,482 | Agregación diaria (desde hourly) |
| `ops.mv_real_lob_week_v3` | MV | 2,322 | Agregación semanal (desde hourly) |
| `ops.mv_real_lob_month_v3` | MV | 746 | Agregación mensual (desde hourly) |

### Scripts
| Script | Propósito |
|--------|-----------|
| `scripts/bootstrap_hourly_first.py` | Bootstrap hour → day → week → month |
| `scripts/governance_hourly_first.py` | Governance y validación E2E |
| `scripts/validate_fact_v2.py` | Validación rápida de la vista fact |

### Documentación
| Documento | Contenido |
|-----------|-----------|
| `docs/real_hourly_first_architecture.md` | Arquitectura nueva completa |
| `docs/real_hourly_architecture_current_state.md` | Estado actual pre/post migración |
| `docs/real_trip_source_contract.md` | Contrato de fuente para cambio futuro |
| `docs/real_trip_outcome_and_cancellation_semantics.md` | Semántica de outcomes y cancelaciones |
| `docs/real_lob_hourly_first_closure.md` | Este documento |

## Artefactos existentes NO tocados
- `ops.mv_real_lob_week_v2` — sigue existiendo, endpoints actuales siguen funcionando
- `ops.mv_real_lob_month_v2` — sigue existiendo
- `ops.v_real_trips_with_lob_v2_120d` — recreada con misma definición
- `ops.v_real_trips_service_lob_resolved_120d` — recreada con misma definición
- Todos los endpoints backend y frontend — sin cambios

## Validaciones confirmadas
1. ✓ `v_real_trip_fact_v2` consultable
2. ✓ `mv_real_lob_hour_v2` poblada (599,871 filas)
3. ✓ `mv_real_lob_day_v2` poblada (59,482 filas)
4. ✓ `mv_real_lob_week_v3` poblada (2,322 filas)
5. ✓ `mv_real_lob_month_v3` poblada (746 filas)
6. ✓ Governance usable
7. ✓ `canonical_no_dupes = True`
8. ✓ `fact_view_ok = True`
9. ✓ `dims_populated = True`
10. ✓ Análisis horario disponible
11. ✓ cancel_reason_norm poblado
12. ✓ trip_duration_minutes razonable
13. ✓ week/month NO dependen de tablas crudas
