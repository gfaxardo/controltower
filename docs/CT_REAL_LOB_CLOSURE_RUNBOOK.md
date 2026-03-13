# CT-REAL-LOB-CLOSURE — Runbook

## Comando único recomendado

Desde la raíz del backend:

```bash
cd backend
python -m scripts.close_real_lob_governance
```

Este script:

- Inspecciona estado Alembic (current, heads).
- Comprueba existencia de dimensiones, vistas y MVs REAL LOB.
- **Refresca solo** `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2` **si existen** (si no existen, los omite con aviso y no falla).
- Ejecuta validaciones rápidas (dims pobladas, vista consultable, sin duplicados crudos).
- Imprime un resumen final (OK/FAIL).

## Comandos alternativos manuales

### 1. Solo inspección (sin refresco)

```bash
python -m scripts.close_real_lob_governance --skip-refresh
```

### 2. Solo refresco de MVs (si existen)

```bash
python -m scripts.close_real_lob_governance --refresh-only
```

### 3. Aplicar migraciones hasta el head único (tras merge 093)

```bash
alembic upgrade head
```

Debería quedar un solo head: `093_merge_real_lob_and_observability`.

### 4. Refresco manual de MVs v2 (si existen en tu BD)

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_lob_month_v2;
REFRESH MATERIALIZED VIEW CONCURRENTLY ops.mv_real_lob_week_v2;
```

Si falla por "not been populated", usar sin `CONCURRENTLY` la primera vez:

```sql
REFRESH MATERIALIZED VIEW ops.mv_real_lob_month_v2;
REFRESH MATERIALIZED VIEW ops.mv_real_lob_week_v2;
```

### 5. Backfill drill/rollup (opcional)

Si existen `real_drill_dim_fact` y `real_rollup_day_fact` y quieres repoblar con la capa canónica:

```bash
python -m scripts.backfill_real_lob_mvs --from 2025-01-01 --to 2025-12-01
```

## Cómo interpretar warnings

| Mensaje / situación | Significado | Acción |
|---------------------|-------------|--------|
| `Objetos ausentes: ['ops.mv_real_lob_month_v2', 'ops.mv_real_lob_week_v2']` | En este entorno no están creadas las MVs v2 (rama sin 044/047). | Normal en entornos que solo tienen 079→080→090. Los endpoints que dependen de MVs v2 (filters, v2/data) no tendrán datos hasta que se aplique la rama que crea esas MVs o se use otro backend que no dependa de ellas. |
| `MVs omitidas (no existen): ...` | El script no ha intentado refrescar MVs que no existen. | No hacer nada; el script es tolerante. |
| `MVs fallidas: [...]` | Error al ejecutar REFRESH (timeout, dependencias, etc.). | Revisar logs; comprobar que la vista `v_real_trips_with_lob_v2` existe y que la BD tiene datos. |
| `Un solo head: False` | Siguen existiendo varios heads en Alembic. | Aplicar la migración de merge 093 y volver a ejecutar `alembic upgrade head`. |
| `Validación: dimensiones no pobladas` | `canon.dim_service_type` (o similares) vacías o no existen. | Asegurar que la migración 090 está aplicada en este entorno. |
| `canonical_no_dupes: False` | La vista sigue devolviendo categorías crudas (confort+, tuk-tuk, etc.). | Revisar que 080 y 090 están aplicadas y que las vistas usan `canon.dim_service_type` / `canon.dim_lob_group`. |

## Qué hacer si faltan las MVs v2

1. **Confirmar** con el diagnóstico: `python -m scripts.close_real_lob_governance --skip-refresh` y revisar "Objetos ausentes".
2. **Si faltan** `ops.mv_real_lob_month_v2` y `ops.mv_real_lob_week_v2`:
   - En ese entorno, los endpoints **GET /ops/real-lob/filters**, **GET /ops/real-lob/v2/data**, **GET /ops/real-lob/monthly-v2**, **GET /ops/real-lob/weekly-v2** fallarán o devolverán vacío porque leen de esas MVs.
   - Opciones:
     - **A:** Aplicar en este entorno la rama de migraciones que crea esas MVs (044, 047, etc.) y luego ejecutar el script de cierre (que las refrescará).
     - **B:** Dejar el entorno sin MVs v2 y asumir que la UI REAL que depende de esos endpoints no estará disponible hasta tenerlas.
3. El script **no** crea MVs; solo refresca las que ya existan. La creación de MVs es solo vía migraciones Alembic.

## Criterio de compatibilidad entre entornos

- **Entorno “completo”:** Tiene 044/047/064 (MVs v2, real_drill_dim_fact, vistas). Tras 090 y 093: dimensiones + vistas canónicas; el script puede refrescar MVs v2.
- **Entorno “solo LOB governance”:** Tiene 079→080_real_lob→090 (y 093). Tiene dimensiones y vistas canónicas, pero **no** MVs v2. El script no falla; reporta MVs ausentes y no las refresca.
- En ambos, la ruta canónica (normalize → dim_service_type → vistas) queda fijada por 080 y 090; la diferencia es solo si existen o no las MVs v2 para los endpoints que las usan.
