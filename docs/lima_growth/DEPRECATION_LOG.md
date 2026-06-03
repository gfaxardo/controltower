# Deprecation Log — YEGO Lima Growth Tower

## Active Deprecations

| Archivo/Funcion | Razon | Reemplazo | Fecha | Estado |
|---|---|---|---|---|
| `yego_lima_loyalty_sub50_service.py:_get_lima_driver_universe_deprecated` | Usa raw orders como driver universe | Driver360 daily table natively filters by active_flag | 2026-06-02 | DEPRECATED |
| `yego_lima_loyalty_sub50_service.py:_compute_supply_from_orders_deprecated` | Proxy impreciso (ended_at - created_at) | `growth.yango_lima_driver_360_daily.supply_hours` | 2026-06-02 | DEPRECATED |
| `yego_lima_loyalty_sub50_service.py` (v1 build_loyalty_sub50) | Usaba `ops.driver_daily_activity_fact` + raw orders | Nueva funcion canonica usando solo 360_daily + history_weekly | 2026-06-02 | REPLACED |
| `growth.yango_lima_orders_raw` como fuente de supply | Proxy no autoritativo | Driver360 canonical pipeline | 2026-06-02 | DEPRECATED |
| `ops.driver_daily_activity_fact` en Loyalty | Fuente global no Lima-especifica, sin supply | `growth.yango_lima_driver_360_daily` | 2026-06-02 | DEPRECATED |
| Segmentos hardcodeados SUB50_40_49, etc. | Nombres fijos atados a target=50 | Segmentos dinamicos: NEAR_TARGET, MID_GAP, etc. | 2026-06-02 | REPLACED |
| Clasificacion plana de Loyalty (sin capas) | Sin Lealtad 1/2/3 | Unified Segmentation: L1 lifecycle + L2 loyalty + L3 cohort | 2026-06-02 | REPLACED |

## Fase 2D-R — State-Based Loyalty Architecture Deprecations

### Legacy Tables (PRESERVED - not deleted)

| Tabla | Razon | Reemplazo | Fecha | Estado |
|---|---|---|---|---|
| `growth.yango_lima_driver_segment_snapshot` | Mezcla L1/L2/L3 en misma tabla; segment_level_1/2/3 no son estados canonicos | `growth.yango_lima_driver_state_snapshot` | 2026-06-03 | LEGACY |
| `growth.yango_lima_actionable_list_daily` | Trata listas como estados; usa list_type LEALTAD_1/2/3 | `growth.yango_lima_daily_opportunity_list` | 2026-06-03 | LEGACY |

### Legacy Columns (PRESERVED - backward compat)

| Columna | Razon | Reemplazo | Fecha | Estado |
|---|---|---|---|---|
| `segment_level_1` | Nombres legacy (NEW, ACTIVE, DECLINING, etc.) | `lifecycle_state` (PROSPECT, REGISTERED, ACTIVATED, EARLY_LIFE, ESTABLISHED, REACTIVATED, CHURNED, UNKNOWN) | 2026-06-03 | LEGACY |
| `segment_level_2` | Nombres legacy (LOYALTY_14_90, etc.) | `performance_state` + `retention_state` | 2026-06-03 | LEGACY |
| `segment_level_3` | Cohorts accionables legacy | `program_code` en program_eligibility | 2026-06-03 | LEGACY |
| `LEALTAD_1_14_90` | Nombre de lista legacy | `OPPORTUNITY_14_90` | 2026-06-03 | LEGACY |
| `LEALTAD_2_ACTIVE_GROWTH` | Nombre de lista legacy | `OPPORTUNITY_ACTIVE_GROWTH` | 2026-06-03 | LEGACY |
| `LEALTAD_3_CHURN_PREVENTION` | Nombre de lista legacy | `OPPORTUNITY_CHURN_PREVENTION` | 2026-06-03 | LEGACY |

### Legacy Endpoints (READ-ONLY - preserved)

Endpoints legacy bajo `/yego-lima-growth/control-loop` mantienen compatibilidad backward.
Nuevos endpoints bajo `/yego-lima-growth/state`, `/programs`, `/opportunities` usan taxonomia canonica.

## Rules

- No borrar codigo deprecated de golpe. Mantener con sufijo `_deprecated`.
- Agregar comentario `DEPRECATED:` con explicacion.
- Endpoints productivos NUNCA deben usar logica deprecated.
- Nuevo codigo usa solo fuentes canonicas (360_daily + history_weekly).
- Tablas legacy se preservan para backward compatibility.
- Endpoints legacy se mantienen solo lectura o backward compatibility.
