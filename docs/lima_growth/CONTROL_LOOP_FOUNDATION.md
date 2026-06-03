# Control Loop Foundation — YEGO Lima Growth Tower

## 1. Lista Diaria

Cada dia se genera una lista accionable desde `growth.yango_lima_driver_segment_snapshot`
organizada en 3 tipos:
- **LEALTAD_1_14_90**: NEW + REACTIVATED
- **LEALTAD_2_ACTIVE_GROWTH**: ACTIVE + RECOVERED
- **LEALTAD_3_CHURN_PREVENTION**: DECLINING + CHURN_RISK + CHURNED

## 2. Reset Diario

`LIMA_GROWTH_ACTION_LIST_RESET_DAILY = true`:
- Al generar una lista nueva, los items empiezan como `PENDING_ACTION`.
- Al dia siguiente se genera una nueva lista desde el snapshot actualizado.
- Los items del dia anterior que quedaron PENDING_ACTION se cierran como NO_ACTION.
- NO se arrastran pendientes automaticamente.

## 3. Que pasa si no hay accion

Ejecutar `close-unmanaged-items` al cierre del dia:
- Todos los items en `PENDING_ACTION` pasan a `NO_ACTION`.
- Queda registro historico de que no hubo gestion.

## 4. Accion Confirmada

Una accion con `action_confirmed = true`:
- Actualiza `management_status` a `ACTION_CONFIRMED`.
- Registra `confirmation_source` (AGENT_MANUAL, WHATSAPP_LOG, CALL_LOG, etc.).
- Cierra el item de la lista con `closed_at`.

## 5. Accion Intentada

Una accion con `action_confirmed = false`:
- Actualiza `management_status` a `ACTION_ATTEMPTED`.
- Queda registrado el intento aunque no se confirmo exito.
- Util para medir tasa de contacto.

## 6. Como se mide impacto diario

`build-daily-impact` calcula para cada accion:
- `completed_orders_day` y `supply_hours_day` desde 360_daily.
- `baseline_*_7d`: promedio de 7 dias antes de la accion.
- `delta_*_vs_baseline`: diferencia vs baseline.
- `moved_segment_flag`: si cambio de segmento L3.
- `improved_orders_flag`, `improved_supply_flag`: si mejoro vs baseline.
- `reactivated_flag`: si paso de CHURNED/CHURN_RISK a otro estado.
- `reached_target_flag`: si alcanzo el target semanal.

## 7. Como se mide performance de agente

`agent-performance-summary` agrega por agente:
- `assigned_items`: total de acciones asignadas.
- `action_confirmed_count`, `action_attempted_count`.
- `confirmation_rate`: % de acciones confirmadas.
- `contacted_rate`: % de acciones con intento de contacto.
- `avg_delta_orders`, `avg_delta_supply`: impacto promedio.
- `moved_segment_count`, `reactivated_count`.

## 8. Como se mide movimiento de segmento

Cada item de impacto diario tiene `moved_segment_flag = true` si el
segmento L3 del snapshot actual difiere del segmento L3 previo a la accion.
El `driver-impact-timeline` muestra la evolucion dia a dia.
