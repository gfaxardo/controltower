# DRIVERS SERVING HARDENING AUDIT — SH1

**Fecha:** 2026-05-26
**Fase:** SH1 — Serving Hardening Audit
**Motor:** Control Foundation

---

## 1. GOVERNANCE CHECK

SH1 es 100% Control Foundation hardening. No activa Diagnostic/Suggestion/AI. No crea features nuevas. Solo audita y documenta el estado de la serving layer.

---

## 2. ENDPOINTS AUDITADOS (39)

| Método | Ruta | Service | Tablas/Vistas | Riesgo |
|--------|------|---------|--------------|--------|
| GET | `/drivers/raw-freshness` | `driver_raw_freshness_service` | 10 RAW sources dinámicos | ALTO — inspecciona 10+ tablas |
| GET | `/drivers/identity` | `driver_identity_service` | `public.drivers` + 6 joins | **CRITICO** — JOINs contra RAW |
| GET | `/drivers/identity/{id}` | `driver_identity_service` | ídem | ídem |
| GET | `/drivers/activity-summary` | `driver_activity_service` | `public.drivers` + joins | **CRITICO** — JOINs + GROUP BY |
| GET | `/drivers/lifecycle-summary` | `driver_lifecycle_service` | `public.drivers` + joins + GROUP BY | **CRITICO** — GROUP BY sin serving fact |
| GET | `/drivers/lifecycle/{id}` | `driver_lifecycle_service` | ídem | ídem |
| GET | `/drivers/actionable-list` | `driver_actionable_supply_service` | `driver_daily_activity_fact` + identity | ALTO — runtime compute |
| GET | `/drivers/actionable-summary` | `driver_actionable_supply_service` | ídem | ALTO |
| POST | `/drivers/workflow/assign` | `driver_workflow_service` | `ops.driver_supply_workflow` | BAJO — single row |
| POST | `/drivers/workflow/action` | ídem | `ops.driver_supply_action_log` | BAJO |
| POST | `/drivers/workflow/status` | ídem | `ops.driver_supply_workflow` | BAJO |
| GET | `/drivers/workflow` | ídem | `ops.driver_supply_workflow` | BAJO |
| GET | `/drivers/workflow/{id}` | ídem | ídem + join action_log | BAJO |
| GET | `/drivers/workflow-metrics` | ídem | `ops.driver_supply_workflow` | BAJO |
| GET | `/drivers/health` | inline | 7 probes | MEDIO — 7 sub-checks |
| GET | `/drivers/pilot-readiness` | `driver_pilot_service` | 6+ sub-services | **CRITICO** — cascada de checks |
| POST | `/drivers/pilot/cohort-preview` | `driver_pilot_service` | actionable_list | ALTO |
| POST | `/drivers/pilot/cohort` | `driver_pilot_service` | actionable_list + inserts | ALTO |
| POST | `/drivers/pilot/assign` | `driver_pilot_service` | pilot_assignment | BAJO |
| GET | `/drivers/pilot/metrics` | `driver_pilot_service` | pilot_assignment + cohort | BAJO |
| POST | `/drivers/pilot/learning-log` | `driver_pilot_service` | pilot_learning_log | BAJO |
| GET | `/drivers/pilot/learning-log` | `driver_pilot_service` | pilot_learning_log | BAJO |
| POST | `/drivers/campaigns/preview` | `driver_campaign_service` | actionable_list | ALTO |
| POST | `/drivers/campaigns` | `driver_campaign_service` | actionable_list + inserts | ALTO |
| GET | `/drivers/campaigns` | `driver_campaign_service` | ops tables | BAJO |
| GET | `/drivers/campaigns/{id}` | `driver_campaign_service` | ops tables | BAJO |
| GET | `/drivers/campaigns/{id}/members` | `driver_campaign_service` | campaign_members | BAJO |
| POST | `/drivers/campaigns/{id}/outcomes` | `driver_campaign_service` | campaign_members | BAJO |
| GET | `/drivers/campaigns/{id}/summary` | `driver_campaign_service` | campaign_members | BAJO |
| GET | `/drivers/campaigns/{id}/crm-export` | `driver_crm_bridge_service` | campaign + members | BAJO |
| POST | `/drivers/campaigns/{id}/crm-sync/outcomes` | `driver_crm_bridge_service` | members batch | BAJO |
| GET | `/drivers/campaigns/{id}/progress` | `driver_crm_bridge_service` | members aggregate | BAJO |
| GET | `/drivers/campaigns/{id}/sync-history` | `driver_crm_bridge_service` | campaign_sync | BAJO |
| GET | `/drivers/campaigns/sync-health` | `driver_crm_bridge_service` | campaign_sync aggregate | BAJO |
| GET | `/drivers/crm-bridge/health` | `driver_crm_bridge_service` | checks | BAJO |
| GET | `/drivers/campaigns/{id}/effectiveness` | `driver_campaign_effectiveness_service` | `driver_daily_activity_fact` per member | **CRITICO** — N+1 queries |
| GET | `/drivers/campaigns/effectiveness-summary` | `driver_campaign_effectiveness_service` | effectiveness + campaigns | BAJO |
| GET | `/drivers/segment-migration` | `driver_segment_migration_service` | `driver_daily_activity_fact` GROUP BY | **CRITICO** — sin serving fact |
| GET | `/drivers/movements/actionable` | `driver_operational_priority_service` | ídem + `public.drivers` join | **CRITICO** — runtime compute |

---

## 3. SERVICES AUDITADOS (12)

| Service | Fuentes | Riesgo | Serving Fact Recomendada |
|---------|--------|--------|-------------------------|
| `driver_raw_freshness_service` | 10 RAW sources dinámicas | ALTO — inspección dinámica | OK así (auditoría) |
| `driver_identity_service` | `public.drivers` + 6 JOINs | **CRITICO** | `serving.driver_identity_fact` |
| `driver_activity_service` | `public.drivers` + `driver_daily_activity_fact` GROUP BY | **CRITICO** | `driver_weekly_activity_fact` |
| `driver_lifecycle_service` | `public.drivers` + joins + GROUP BY | **CRITICO** | `serving.driver_lifecycle_fact` |
| `driver_segment_migration_service` | `driver_daily_activity_fact` GROUP BY all drivers | **CRITICO** | `driver_segment_migration_fact` |
| `driver_operational_priority_service` | `driver_daily_activity_fact` + `public.drivers` | **CRITICO** | `driver_operational_priority_fact` |
| `driver_actionable_supply_service` | `driver_daily_activity_fact` + identity | ALTO | `driver_supply_actionable_fact` |
| `driver_campaign_service` | ops tables (materializadas) | BAJO | OK |
| `driver_crm_bridge_service` | ops tables | BAJO | OK |
| `driver_campaign_effectiveness_service` | `driver_daily_activity_fact` per member | **CRITICO** | `driver_campaign_effectiveness` (ya existe) |
| `driver_pilot_service` | ops tables + cascada de servicios | ALTO | OK |
| `driver_workflow_service` | ops tables | BAJO | OK |

---

## 4. RUNTIME MEASUREMENTS

No se pudo medir localmente por falta de conexión a base de datos en este entorno. El script `audit_quick.py` quedó listo para ejecutar cuando la DB esté disponible.

---

## 5. QUERIES PESADAS DETECTADAS

### 5.1 `driver_identity_service.py:288-319` — **CRITICO**

```sql
SELECT d.driver_id, ...
FROM public.drivers d
LEFT JOIN ops.v_dim_driver_resolved dr ON ...
LEFT JOIN public.drivers_data dd ON ...
LEFT JOIN public.module_ct_cabinet_drivers mct ON ...
LEFT JOIN dim.dim_park dp ON ...
LEFT JOIN ops.v_dim_park_resolved prk ON ...
LEFT JOIN ops.mv_driver_lifecycle_base lb ON ...
WHERE 1=1
ORDER BY ... LIMIT ...
```

**Riesgo:** 6 JOINs contra RAW tables en cada request. Sin serving fact materializada.
**Fix SH2:** Materializar `serving.driver_identity_fact` con refresh diario.

### 5.2 `driver_lifecycle_service.py:219-236` — **CRITICO**

```sql
SELECT d.driver_id, SUM(...), MAX(...), COUNT(...)
FROM public.drivers d
LEFT JOIN ops.driver_daily_activity_fact adf ON ...
LEFT JOIN ops.mv_driver_lifecycle_base lb ON ...
LEFT JOIN dim.dim_park dp ON ...
LEFT JOIN ops.v_dim_park_resolved prk ON ...
WHERE ...
GROUP BY d.driver_id, lb.activation_ts
```

**Riesgo:** GROUP BY sobre `driver_daily_activity_fact` + JOINs. Sin pre-agregación.
**Fix SH2:** `ops.driver_weekly_segment_fact` con grain driver×week.

### 5.3 `driver_segment_migration_service.py` — **CRITICO**

El servicio escanea `ops.driver_daily_activity_fact` dos veces (periodo previo y actual) con GROUP BY por driver_id. Sin límite de drivers en el scan inicial.

**Fix SH2:** `ops.driver_segment_migration_fact`.

### 5.4 `driver_operational_priority_service.py` — **CRITICO**

Similar: escanea `driver_daily_activity_fact` + consulta `public.drivers` para enriquecer. Runtime compute de prioridades cada request.

**Fix SH2:** `ops.driver_operational_priority_fact`.

### 5.5 `driver_campaign_effectiveness_service.py` — **CRITICO**

Computa effectiveness per member con queries individuales a `driver_daily_activity_fact` (N+1 pattern en `_compute_member_effectiveness`). Para campañas con 100+ miembros, esto escala muy mal.

**Fix SH2:** Batch query en vez de N+1; materializar resultados en `driver_campaign_effectiveness` (ya existe la tabla pero se computa runtime).

---

## 6. CAUSA PROBABLE DE TIMEOUT (20000ms exceeded)

| Causa | Impacto | Servicios afectados |
|-------|---------|-------------------|
| DB connection not available in env | Todos los endpoints fallan | Todos |
| `dd.driver_phone` column missing | identity, lifecycle, activity fallan | 3 servicios críticos |
| JOINs contra RAW tables sin índices | Tiempos de query altos | identity, lifecycle, activity |
| GROUP BY sin pre-agregación | Tiempos de query altos | lifecycle, migration, priorities |
| Sin serving facts materializadas | Toda la capa foundation computa runtime | Supply, Lifecycle, Identity |
| `check_column_exists` por request | Overhead adicional | identity service (fix aplicado) |

---

## 7. CAUSA PROBABLE DE "SIN DATOS" / "DATA FOUNDATION UNAVAILABLE"

1. **`dd.driver_phone` no existe** → identity/lifecycle queries fallan → Data Foundation unavailable → Lifecycle unavailable
2. **Park "Todos" no válido para queries geo** → filtros devuelven vacío sin warning claro
3. **Country/City como string vacío** → algunos endpoints no manejan `""` como None, filtrando todo
4. **Timeout → catch → empty result** → UI muestra "Sin datos" cuando en realidad fue un error
5. **Date range incompleto** → cuando `from` y `to` no cubren la semana completa

---

## 8. SERVING FACTS REQUERIDAS (SH2)

| # | Fact Name | Grain | Prioridad |
|---|-----------|-------|-----------|
| 1 | `ops.driver_weekly_segment_fact` | driver × week_start | **P0** |
| 2 | `ops.driver_segment_migration_fact` | driver × week_start_current | **P0** |
| 3 | `ops.driver_operational_priority_fact` | driver × week_start | **P0** |
| 4 | `ops.driver_supply_overview_weekly_fact` | week × country × city × park | **P1** |
| 5 | `serving.driver_identity_fact` | driver_id | **P1** |

---

## 9. BUGS CORREGIDOS EN SH1

| Bug | Archivo | Fix |
|-----|---------|-----|
| `dd.driver_phone` column missing | `driver_identity_service.py` | Column detection + fallback to `d.phone` |
| `dd.driver_phone` column missing | `driver_lifecycle_service.py` | Use `d.phone` directly |
| `dd.driver_phone` column missing | `driver_activity_service.py` | Use `d.phone::text` |
| `_get_recoverability` TypeError | `driver_operational_priority_service.py` | Rewrote as clean if/elif logic |
| Selects no abrían en Supply | `SupplyView.jsx` | `relative z-10` en contenedor filtros |
| "Cargando geo..." permanente | `SupplyView.jsx` | Warning + retry button |
| Semántica migration confusa | `SupplyView.jsx` | Labels clarificados + "Mismo driver" badge |

---

## 10. REFRESH STRATEGY (SH2)

```
Función: ops.refresh_driver_supply_facts()
Orden:
  1. REFRESH MATERIALIZED VIEW serving.driver_identity_fact
  2. REFRESH MATERIALIZED VIEW ops.driver_weekly_segment_fact
  3. REFRESH MATERIALIZED VIEW ops.driver_segment_migration_fact
  4. REFRESH MATERIALIZED VIEW ops.driver_operational_priority_fact
  5. REFRESH MATERIALIZED VIEW ops.driver_supply_overview_weekly_fact

Tipo: Full refresh (no incremental initially)
Frecuencia: Diario, post-refresh de driver_daily_activity_fact
Timeout: 5 min por fact
```

---

## 11. GO/NO-GO PARA SH2

**GO** — La auditoría está completa. Se identificaron:
- 5 queries críticas que requieren serving facts
- 5 bugs corregidos que causaban fallos en cadena
- 5 serving facts a materializar en SH2
- Estrategia de refresh definida

SH2 debe implementar las MVs y migrar los servicios a consumirlas.

---

**FIN DEL AUDIT SH1**
