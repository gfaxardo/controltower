# Real LOB Bootstrap / Refresh Fix — CT-REAL-LOB-BOOTSTRAP-REFRESH-FIX

**YEGO CONTROL TOWER — Fase CT-REAL-LOB-BOOTSTRAP-REFRESH-FIX**

## Problema original

- Tras `alembic upgrade head` hasta 096, las MVs `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2` se crean vacías (`WITH NO DATA`).
- La primera población con `REFRESH MATERIALIZED VIEW` ejecutaba **una sola query gigante** sobre la vista base (120 días), con:
  - Múltiples CTEs en `v_real_trips_with_lob_v2` (v_trips_real_canon → parks → dimensiones canon).
  - Agregación por mes/semana con GROUP BY sobre muchos atributos.
  - Sin posibilidad de cortar por tiempo ni de reanudar.
- Resultado: refreshes de **horas** o colgados, inaceptables operativamente.
- **No** se quería resolver solo subiendo timeouts ni “esperar más”.

## Por qué el refresh gigante no era aceptable

- Una sola transacción/statement de horas bloquea recursos y no permite progreso visible.
- Si falla por timeout o error, se pierde todo el trabajo.
- No hay señales de avance ni posibilidad de reanudar por bloques.
- Operativamente no es viable depender de una ventana de horas para “arrancar” el módulo.

## Diagnóstico del cuello de botella

- **Vista base:** `ops.v_real_trips_with_lob_v2` es un wrapper sobre `ops.v_real_trips_service_lob_resolved`, que a su vez lee de `ops.v_trips_real_canon` con JOIN a `parks` y a dimensiones `canon.dim_service_type` y `canon.dim_lob_group`. La ventana de 120 días se aplica **en la definición de la MV** (CTE `base`), no en la vista base; por tanto, cada REFRESH ejecuta esa cadena completa sobre 120 días de datos.
- **Agregación:** GROUP BY por country, city, park_id, park_name, lob_group, real_tipo_servicio_norm, segment_tag y month_start/week_start genera muchas filas y requiere ordenación/hash costosos.
- **Índices:** Si en la tabla subyacente de viajes no hay índice adecuado por `fecha_inicio_viaje`, el plan puede hacer full scan sobre la ventana.
- **Conclusión:** El costo viene de (1) leer y transformar 120 días de la vista base en una sola pasada, y (2) una agregación pesada en un solo paso. La ventana de 120 días sí está aplicada en la MV, pero **una sola ejecución** de esa lógica sigue siendo demasiado costosa para usarla como bootstrap.

## Solución elegida: bootstrap por bloques temporales

- **Estrategia:** En lugar de un único REFRESH sobre toda la ventana, se construye la misma semántica **por bloques de fecha**:
  - **Mensual:** una tabla staging se rellena mes a mes (INSERT por cada `month_start` en la ventana de 120 días).
  - **Semanal:** igual por semana (cada `week_start`).
- Cada bloque es una query acotada (un mes o una semana), con la misma agregación y la misma vista canónica, por lo que **no se cambia la semántica** ni los contratos downstream.
- Al terminar todos los bloques, se reemplaza la MV por los datos de staging (DROP MV, CREATE MV AS SELECT * FROM staging, creación de índices) y se elimina la tabla staging.
- **Ventajas:**
  - Progreso visible por bloque (logging, duración, filas).
  - Si falla un bloque, el error indica **en qué bloque** falló.
  - No se depende de una sola espera de horas.
  - El flujo normal posterior sigue siendo REFRESH (normal o CONCURRENTLY) sobre la MV ya poblada.

## Cómo ejecutar el bootstrap inicial

Desde `backend/`:

```bash
# Bootstrap completo (month_v2 y week_v2 por bloques)
python scripts/bootstrap_real_lob_mvs_by_blocks.py

# Solo MV mensual
python scripts/bootstrap_real_lob_mvs_by_blocks.py --only-month

# Solo MV semanal
python scripts/bootstrap_real_lob_mvs_by_blocks.py --only-week

# Solo listar bloques, sin escribir (dry-run)
python scripts/bootstrap_real_lob_mvs_by_blocks.py --dry-run
```

El script registra en `ops.observability_refresh_log` con `trigger_type='bootstrap'` (si existe el servicio de observabilidad).

## Cómo ejecutar el refresh normal posterior

Una vez las MVs están pobladas:

- **Governance (recomendado):**  
  `python scripts/close_real_lob_governance.py`  
  o con opciones `--only-month` / `--only-week` / `--skip-refresh`.
- Si la MV **tiene datos**, el governance usa **REFRESH MATERIALIZED VIEW CONCURRENTLY** (conexión dedicada, autocommit).
- Si la MV **está vacía**, el governance **no** lanza un refresh gigante; invoca el **bootstrap por bloques** (script anterior).

Alternativa para solo MVs v2:

```bash
python -m scripts.refresh_real_lob_mvs_v2
```

(Solo refresha; no hace bootstrap. Usar governance o bootstrap script para primera población.)

## Cómo detectar si se requiere bootstrap vs refresh

- **Bootstrap:** MV recién creada o vacía (p. ej. tras `alembic upgrade head` o tras un DROP/CREATE). El governance lo detecta con `_mv_is_populated` (reltuples o conteo) y llama al bootstrap por bloques.
- **Refresh:** MV ya tiene filas; se usa REFRESH CONCURRENTLY (o REFRESH normal si por alguna razón no se puede CONCURRENTLY).

En ambos casos el flujo queda cubierto por `close_real_lob_governance.py`.

## Señales PASS / FAIL

- **PASS:**  
  - No hay REFRESH colgados para las MVs objetivo (ver FASE A).  
  - Bootstrap termina en tiempo razonable (minutos a ~decenas de minutos, según datos).  
  - `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2` tienen filas.  
  - Governance con `--only-month` / `--only-week` no depende de un refresh gigante cuando la MV está vacía.  
  - Validaciones del governance: `dims_populated`, `view_select_ok`, y (si aplica) `canonical_no_dupes` en estado esperado.  
  - Rowcount consistente y sin ruptura de contratos downstream (APIs que lean de estas MVs).

- **FAIL:**  
  - REFRESH de horas como parte normal del arranque.  
  - Timeout o colgado en la primera población sin usar bootstrap.  
  - Bootstrap falla sin indicar bloque concreto.  
  - MVs siguen vacías tras ejecutar bootstrap o governance.

## Detener un refresh actual (FASE A)

Si sigue vivo un REFRESH de estas MVs:

```bash
cd backend
python scripts/kill_refresh_real_lob_mvs.py          # diagnóstico
python scripts/kill_refresh_real_lob_mvs.py --kill # terminar procesos
```

Ver también `docs/real_lob_bootstrap_runbook.md`.

## Diagnóstico de costo (FASE B)

Para inspeccionar el plan sin ejecutar la query pesada:

```bash
cd backend
python scripts/diagnose_real_lob_mv_cost.py
```

Muestra EXPLAIN (sin ANALYZE) de la vista base con ventana 120 días y de un bloque de agregación mensual/semanal, además de índices en `ops`.

## Causa raíz y guardrails (098+)

A partir de la migración **098** (CT-REAL-LOB-ROOT-CAUSE-FIX) se corrige el cuello de botella en BD (índices + vistas _120d). Ver:

- `docs/real_lob_root_cause_diagnosis.md`
- `docs/real_lob_execution_plan_validation.md`
- `docs/query_performance_guardrails.md`
- `docs/migration_performance_checklist.md`
