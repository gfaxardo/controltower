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

## Rules

- No borrar codigo deprecated de golpe. Mantener con sufijo `_deprecated`.
- Agregar comentario `DEPRECATED:` con explicacion.
- Endpoints productivos NUNCA deben usar logica deprecated.
- Nuevo codigo usa solo fuentes canonicas (360_daily + history_weekly).
