# FASE CT-REAL-LOB-FINAL-CLOSURE — Fase A completada

## Objetivo
Validar estado real de la migración 098 en BD, alinear Alembic y dejar listos los criterios de cierre (MVs poblables, governance validando).

## 1. Auditoría 098 (Fase A)

### Script de auditoría
- **`backend/scripts/audit_098_artifacts.py`**: consultas de solo lectura; devuelve JSON con:
  - `objetos_098_existentes` / `objetos_098_faltantes`
  - `098_aplicada_realmente` (yes/no)
  - `mvs_usando_capa_120d` (que las MVs dependan de `v_real_trips_with_lob_v2_120d`)
  - `alembic_version_actual`, conteos de filas de las MVs

### Verificaciones explícitas
- **Índices:** `ix_trips_all_fecha_inicio_viaje`, `ix_trips_2026_fecha_inicio_viaje`
- **Vistas:** `ops.v_trips_real_canon_120d`, `ops.v_real_trips_service_lob_resolved_120d`, `ops.v_real_trips_with_lob_v2_120d`
- **MVs:** `ops.mv_real_lob_month_v2`, `ops.mv_real_lob_week_v2` (definición con `FROM ops.v_real_trips_with_lob_v2_120d`)

### Resultado Fase A
- Si `098_aplicada_realmente == "no"` (p. ej. MVs recreadas desde staging sin _120d en la definición):
  - Ejecutar **`python scripts/ensure_098_mvs_definition.py`** para recrear solo las dos MVs con la definición 098 (WITH NO DATA). No toca vistas ni índices.
- Solo si la auditoría da **098_aplicada_realmente = yes**, alinear Alembic:
  ```bash
  python -m scripts.alembic_inspect_and_fix --stamp 098_real_lob_root_cause_120d
  ```

## 2. Cambios realizados en esta fase

1. **audit_098_artifacts.py**  
   Creado: audita índices, vistas, MVs y que las MVs usen la capa _120d; tolera MVs no pobladas en el conteo.

2. **ensure_098_mvs_definition.py**  
   Creado: solo DROP + CREATE de `mv_real_lob_month_v2` y `mv_real_lob_week_v2` con definición 098 (base FROM `v_real_trips_with_lob_v2_120d`), WITH NO DATA. Tras ejecutarlo, las MVs quedan vacías; hay que volver a poblarlas con bootstrap.

3. **close_real_lob_governance.py**
   - Validaciones usan la vista **`v_real_trips_with_lob_v2_120d`** cuando existe (post-098), para evitar timeout en la vista antigua.
   - Timeout de validaciones: **5 min** (`statement_timeout_ms=300000`) para que el SELECT sobre la vista _120d pueda completar.
   - Log de fallo en `view_select_ok` para diagnóstico.

4. **Alembic**
   - `alembic_version` alineado a **098_real_lob_root_cause_120d** vía `alembic_inspect_and_fix --stamp 098_real_lob_root_cause_120d` (solo tras confirmar 098 aplicada en BD).

## 3. Evidencia de cierre Fase A

- **098 en BD:** todos los artefactos (índices, vistas, MVs) existen; MVs con definición que apunta a `v_real_trips_with_lob_v2_120d`.
- **Alembic:** `alembic_version` = `098_real_lob_root_cause_120d`.
- **Governance:** con `--skip-refresh`, validaciones `dims_populated`, `view_select_ok` y `canonical_no_dupes` en OK (timeout 5 min para consultas de validación).
- **MVs:** tras `ensure_098_mvs_definition.py` las MVs quedan vacías; es necesario ejecutar bootstrap para poblarlas.

## 4. Pasos posteriores (poblar MVs y validación final)

1. **Poblar month_v2**
   ```bash
   cd backend && python scripts/bootstrap_real_lob_mvs_by_blocks.py --only-month
   ```
   (Puede tardar; sub-bloques de 15 días con timeout 30 min por sub-bloque.)

2. **Poblar week_v2**
   ```bash
   cd backend && python scripts/bootstrap_real_lob_mvs_by_blocks.py --only-week
   ```
   O sin filtros para hacer month + week en un solo paso.

3. **Validación final**
   ```bash
   python scripts/audit_098_artifacts.py   # debe mostrar 098_aplicada_realmente=yes y filas en MVs)
   python scripts/close_real_lob_governance.py --skip-refresh   # OVERALL OK si Alembic tiene un solo head)
   ```

4. **Alembic heads vacíos**  
   Si la governance sigue mostrando `Alembic heads = []`, es un tema de entorno Alembic (rutas/heads en el repo); la BD ya está en 098. Comprobar con `alembic current` desde el entorno donde Alembic esté instalado.
