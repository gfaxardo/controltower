# Real LOB — Validación del plan de ejecución (antes / después)

**CT-REAL-LOB-ROOT-CAUSE-FIX — FASE D**

## Objetivo

Comprobar que, tras la migración 098 (índices + vistas _120d), el plan de ejecución deja de depender de Seq Scan masivo sobre trips_all/trips_2026 y que el volumen leído y los costos mejoran de forma clara.

## Cómo generar los planes

Desde `backend/`:

```bash
python scripts/diagnose_real_lob_mv_cost.py
```

El script ejecuta `EXPLAIN (FORMAT TEXT)` (sin `ANALYZE`) sobre:

1. **Si existe `v_real_trips_with_lob_v2_120d`:**  
   `SELECT * FROM ops.v_real_trips_with_lob_v2_120d LIMIT 1`  
   → Debe mostrar uso de **Index Scan** (o Index Only Scan) sobre `fecha_inicio_viaje` en `trips_all` y `trips_2026`, o al menos un plan con coste y filas estimadas mucho menores que el plan sobre la vista sin _120d.

2. **Vista estándar con filtro 120 días:**  
   `SELECT * FROM ops.v_real_trips_with_lob_v2 WHERE fecha_inicio_viaje >= CURRENT_DATE - INTERVAL '120 days' LIMIT 1`  
   → Referencia de “antes”: suele aparecer Seq Scan + Sort sobre decenas de millones de filas.

3. **Agregación mensual de un mes:**  
   Bloque equivalente a un mes sobre la vista base (para comparar coste de agregación).

## Qué comprobar (después de 098)

| Comprobación | Antes (096) | Después (098) |
|--------------|-------------|----------------|
| Scan en trips_all / trips_2026 | Seq Scan, ~56M filas | Index Scan (o Bitmap Index Scan) sobre `fecha_inicio_viaje`, filas en orden de la ventana 120d |
| Sort antes del filtro de fecha | Sort sobre todo el UNION | Sort solo sobre el resultado ya filtrado por fecha (o inexistente si no hace falta) |
| Coste total estimado | Muy alto (millones) | Orden de magnitud menor |
| Uso de índices | No uso de índice por fecha | Uso de `ix_trips_all_fecha_inicio_viaje` / `ix_trips_2026_fecha_inicio_viaje` (o equivalente) |

## Evidencia recomendada

1. Guardar la salida de `diagnose_real_lob_mv_cost.py` **antes** de aplicar 098 (o usar la salida ya obtenida en diagnóstico previo).
2. Aplicar `alembic upgrade head` (098).
3. Volver a ejecutar `diagnose_real_lob_mv_cost.py` y guardar la salida.
4. Comparar:
   - Desaparición (o fuerte reducción) de Seq Scan masivo en tablas de viajes.
   - Reducción clara del coste estimado y de las filas estimadas en los nodos de scan.
   - Que las consultas que usan `v_real_trips_with_lob_v2_120d` muestren un plan razonable (index-friendly).

## EXPLAIN ANALYZE (opcional y controlado)

Si se quiere medir tiempo y filas reales (con impacto en la BD):

```sql
SET statement_timeout = '60s';
EXPLAIN (ANALYZE, FORMAT TEXT) SELECT * FROM ops.v_real_trips_with_lob_v2_120d LIMIT 1;
```

Solo ejecutar en entorno controlado; no en producción bajo carga sin coordinación.

## Criterio de éxito FASE D

- En el plan sobre `v_real_trips_with_lob_v2_120d` (o sobre la capa que usa la ventana 120d en la definición), **no** debe aparecer un Seq Scan sobre trips_all/trips_2026 sin restricción por fecha a nivel de tabla.
- El volumen leído (filas estimadas o reales) debe corresponder a la ventana de 120 días, no al histórico completo.
- Los costos estimados del plan deben bajar de forma material respecto al plan “antes” documentado en el diagnóstico de causa raíz.
