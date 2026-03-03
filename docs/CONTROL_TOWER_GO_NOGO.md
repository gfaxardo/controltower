# Control Tower (Driver Lifecycle) — GO / NO-GO

**Fecha certificación:** 2026-03-02 18:03:42 UTC
**Log:** `backend/logs/ct_go_nogo_20260302_1758.log`

## 1) Resumen ejecutivo

- **Veredicto:** NO-GO
- Check completo: PASS.
- Freshness: columna=None, MAX(ts)=None.
- Park null share: NO MEDIBLE.
- Parks distintos: NO MEDIBLE.

## 2) Evidencia

### Comando ejecutado
```
cd backend && python -m scripts.check_driver_lifecycle_and_validate
```

### Resultado del check
```
Before SET:
  statement_timeout = 15s
  lock_timeout = 0
  maintenance_work_mem = 64MB
ENV: DRIVER_LIFECYCLE_REFRESH_MODE = concurrently
     DRIVER_LIFECYCLE_TIMEOUT_MINUTES = 60
     DRIVER_LIFECYCLE_LOCK_TIMEOUT_MINUTES = 5
     DRIVER_LIFECYCLE_FALLBACK_NONC = True
After SET:
  statement_timeout = 1h
  lock_timeout = 5min

MVs driver lifecycle en ops: ['mv_driver_lifecycle_base', 'mv_driver_lifecycle_monthly_kpis', 'mv_driver_lifecycle_weekly_kpis', 'mv_driver_monthly_stats', 'mv_driver_weekly_stats']

OK: refresh (concurrently) completado
  Modo usado: concurrently | Duración: 311.5 s

--- Validaciones ---
  ops.mv_driver_lifecycle_base: 33,277 filas
  ops.mv_driver_lifecycle_weekly_kpis: 57 filas
  ops.mv_driver_lifecycle_monthly_kpis: 14 filas
  ops.mv_driver_weekly_stats: 266,930 filas
  ops.mv_driver_monthly_stats: 100,011 filas
  Unicidad base (driver_key): OK (total=33277, distinct=33277)
  Freshness (last_completed_ts): 2026-02-01 01:05:52
  Parks distintos (weekly_stats): 22
  park_id NULL: 0/266,930 (0.00%)
  Top 5 parks por activations (últimos 28 días):

Listo.


```

### MVs detectadas (schema ops)

- ops.mv_cabinet_financial_14d
- ops.mv_claims_payment_status_cabinet
- ops.mv_driver_lifecycle_base
- ops.mv_driver_lifecycle_monthly_kpis
- ops.mv_driver_lifecycle_weekly_kpis
- ops.mv_driver_monthly_stats
- ops.mv_driver_name_index
- ops.mv_driver_weekly_stats
- ops.mv_drivers_park_08e20910d81d42658d4334d3f6d10ac0
- ops.mv_drivers_park_08e20910d81d42658d4334d3f6d10ac0_active90d
- ops.mv_payment_calculation
- ops.mv_payments_driver_matrix_cabinet
- ops.mv_real_financials_monthly
- ops.mv_real_lob_drill_agg
- ops.mv_real_lob_month_v2
- ops.mv_real_lob_week_v2
- ops.mv_real_rollup_day
- ops.mv_real_tipo_servicio_universe_fast
- ops.mv_real_trips_by_lob_month
- ops.mv_real_trips_by_lob_week
- ops.mv_real_trips_monthly
- ops.mv_real_trips_monthly_old
- ops.mv_real_trips_monthly_old_margin
- ops.mv_real_trips_monthly_old_signed
- ops.mv_real_trips_weekly
- ops.mv_yango_cabinet_claims_for_collection
- ops.mv_yango_cabinet_cobranza_enriched_14d
- ops.mv_yango_payments_ledger_latest
- ops.mv_yango_payments_ledger_latest_enriched
- ops.mv_yango_payments_raw_current

### Columnas detectadas (mv_driver_lifecycle_base, mv_driver_weekly_stats)

- (ninguna o error de conexión)

### Señales

| Señal | Query / Nota | Resultado |
|-------|--------------|-----------|
| A Freshness | MAX(N/A) FROM ops.mv_driver_lifecycle_base | None |
| B Park null share | COUNT FILTER park_id IS NULL / COUNT(*) | n_null=None, total=None, share=None |
| C Distinct parks | COUNT(DISTINCT park_id) FROM ops.mv_driver_weekly_stats | None |

## 3) Recomendación inmediata

- **Acciones correctivas sugeridas (no destructivas):**
  1. Revisar conectividad y credenciales de BD; ejecutar `python -m scripts.check_driver_lifecycle_and_validate --diagnose`.
  2. Revisar timeouts/locks (statement_timeout, lock_timeout) y ejecutar refresh en ventana de bajo uso.
  3. Si park_id NULL es alto, revisar calidad de datos en origen (trips_all, drivers) y pipeline de asignación de park.

---
*Generado por scripts/certify_control_tower_go_nogo.py — 2026-03-02 18:03:42 UTC*