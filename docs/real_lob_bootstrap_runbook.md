# Real LOB Bootstrap — Runbook operativo

**CT-REAL-LOB-BOOTSTRAP-REFRESH-FIX**

## 1. Antes de bootstrap: estado limpio

### 1.1 Comprobar si hay REFRESH en curso

```bash
cd backend
python scripts/kill_refresh_real_lob_mvs.py
```

- Si hay líneas `[REFRESH EN CURSO]`: anotar `pid` y `duration_seconds`.
- Si quieres terminar esos procesos:  
  `python scripts/kill_refresh_real_lob_mvs.py --kill`
- Comprobar que el reporte final indique estado limpio (no refreshes corriendo, locks aceptables).

### 1.2 Comprobar migraciones

```bash
cd backend
alembic current
alembic heads
```

Debe estar aplicado al menos hasta `096_real_lob_mvs_partial_120d`.

---

## 2. Bootstrap inicial (MVs vacías)

### 2.1 Cuándo usar bootstrap

- Tras `alembic upgrade head` que crea o recrea las MVs con `WITH NO DATA`.
- Cuando `ops.mv_real_lob_month_v2` o `ops.mv_real_lob_week_v2` están vacías y no quieres un REFRESH gigante.

### 2.2 Ejecución

```bash
cd backend

# Ambas MVs (mensual y semanal) por bloques
python scripts/bootstrap_real_lob_mvs_by_blocks.py

# Solo mensual
python scripts/bootstrap_real_lob_mvs_by_blocks.py --only-month

# Solo semanal
python scripts/bootstrap_real_lob_mvs_by_blocks.py --only-week
```

### 2.3 Qué esperar

- Logs por bloque: número de bloque, rango de fecha, filas insertadas, tiempo del bloque.
- Al final: resumen `month_v2: ok=... rows=...` y `week_v2: ...`.
- Si falla: el mensaje debe indicar **en qué bloque** (mes o semana) falló.

### 2.4 Si el bootstrap falla

- Revisar el mensaje de error (bloque concreto).
- Opción: correr de nuevo (el script vuelve a crear staging y rellenar desde cero).
- Si el fallo es recurrente en un bloque, revisar datos fuente o ejecutar diagnóstico:  
  `python scripts/diagnose_real_lob_mv_cost.py`

---

## 3. Flujo normal (MVs ya pobladas)

### 3.1 Governance (recomendado)

```bash
cd backend
python scripts/close_real_lob_governance.py
```

- Si la MV tiene datos → hace **REFRESH MATERIALIZED VIEW CONCURRENTLY** (conexión dedicada).
- Si la MV está vacía → lanza **bootstrap por bloques** (no refresh gigante).

Opciones útiles:

- `--skip-refresh`: solo inspección y validación.
- `--only-month`: solo `ops.mv_real_lob_month_v2`.
- `--only-week`: solo `ops.mv_real_lob_week_v2`.

### 3.2 Solo refresh (sin bootstrap)

Si estás seguro de que las MVs ya tienen datos:

```bash
python -m scripts.refresh_real_lob_mvs_v2
```

---

## 4. Validación post-bootstrap / post-refresh

### 4.1 Conteos

En la base de datos:

```sql
SELECT COUNT(*) FROM ops.mv_real_lob_month_v2;
SELECT COUNT(*) FROM ops.mv_real_lob_week_v2;
```

Deben ser > 0 tras un bootstrap correcto.

### 4.2 Governance

```bash
python scripts/close_real_lob_governance.py --skip-refresh
```

Revisar en el resumen:

- **Objetos OK:** incluir las dos MVs.
- **Validaciones:**  
  - `dims_populated`: True.  
  - `view_select_ok`: True.  
  - `canonical_no_dupes`: True (o diagnóstico si no aplica).

### 4.3 Observabilidad

Si existe `ops.observability_refresh_log`:

```sql
SELECT artifact_name, refresh_started_at, refresh_status, trigger_type, rows_after
FROM ops.observability_refresh_log
WHERE artifact_name LIKE 'ops.mv_real_lob%'
ORDER BY refresh_started_at DESC
LIMIT 10;
```

- `trigger_type = 'bootstrap'` para ejecuciones de bootstrap.
- `trigger_type = 'script'` para refresh vía script/governance.

---

## 5. Resumen de señales

| Señal | PASS | FAIL |
|-------|------|------|
| Refreshes colgados | Ninguno para estas MVs | REFRESH en curso horas |
| Bootstrap | Termina en tiempo razonable, rows > 0 | Timeout o error sin bloque claro |
| MVs pobladas | month_v2 y week_v2 con filas | Vacías tras bootstrap |
| Governance con MV vacía | Usa bootstrap, no refresh gigante | Lanza REFRESH de horas |
| Validaciones | dims_populated, view_select_ok, canonical_no_dupes OK | Alguna en False o error |
| Contratos downstream | APIs que lean de las MVs responden bien | Errores o datos incoherentes |

---

## 6. Scripts relacionados

| Script | Uso |
|--------|-----|
| `scripts/kill_refresh_real_lob_mvs.py` | Ver/terminar REFRESH en curso (FASE A) |
| `scripts/diagnose_real_lob_mv_cost.py` | EXPLAIN y índices (FASE B) |
| `scripts/bootstrap_real_lob_mvs_by_blocks.py` | Bootstrap por bloques (FASE C) |
| `scripts/close_real_lob_governance.py` | Inspección + bootstrap o refresh (FASE D) |
| `scripts/refresh_real_lob_mvs_v2.py` | Solo refresh (no bootstrap) |

Documentación de contexto: `docs/real_lob_bootstrap_refresh_fix.md`, `docs/mv_performance_hardening.md`.
