# CT-REAL-LOB-CLOSURE — Validación

## 1. Validación de canonicalización (SQL)

**Objetivo:** No deben existir como categorías visibles las variantes crudas; deben colapsar a canónicas.

```sql
-- Valores distintos de real_tipo_servicio_norm en la vista (solo canónicos)
SELECT real_tipo_servicio_norm, COUNT(*) AS trips
FROM ops.v_real_trips_with_lob_v2
WHERE fecha_inicio_viaje::date >= (current_date - 90)
GROUP BY real_tipo_servicio_norm
ORDER BY trips DESC;
```

**PASS:** No aparecen a la vez `confort+`, `confort plus`, `comfort+` ni `tuk-tuk` junto a `tuk_tuk` ni `express`/`mensajería`/`mensajeria` como categorías distintas. Deben verse solo: `comfort_plus`, `tuk_tuk`, `delivery`, etc.

**FAIL:** Aparecen filas con `real_tipo_servicio_norm` en (`confort+`, `confort plus`, `tuk-tuk`, `mensajería`, `express`) como valores distintos de `comfort_plus`/`tuk_tuk`/`delivery`.

---

## 2. Validación de totales (SQL)

El total de viajes no debe cambiar; solo la redistribución entre categorías equivalentes.

```sql
-- Total viajes en vista (últimos 90d)
SELECT COUNT(*) AS total_trips
FROM ops.v_real_trips_with_lob_v2
WHERE fecha_inicio_viaje::date >= (current_date - 90);
```

Comparar antes/después de cambios de normalización: el total debe ser el mismo (o coherente con el volumen de datos de la fuente).

---

## 3. Validación de dimensiones (SQL)

```sql
SELECT 'dim_lob_group' AS obj, COUNT(*) AS n FROM canon.dim_lob_group WHERE is_active = true
UNION ALL
SELECT 'dim_lob_real', COUNT(*) FROM canon.dim_lob_real WHERE is_active = true
UNION ALL
SELECT 'dim_service_type', COUNT(*) FROM canon.dim_service_type WHERE is_active = true;
```

**PASS:** Las tres tablas existen y devuelven filas (n > 0).

**FAIL:** Alguna no existe o todas tienen 0 filas activas.

---

## 4. Validación de endpoints

Probar como mínimo (sustituir BASE por la URL del API, p. ej. http://localhost:8000):

| Endpoint | Método | Criterio PASS |
|----------|--------|----------------|
| /ops/real-lob/filters | GET | 200; body con `lob_groups` y `tipo_servicio` (listas, pueden estar vacías si no hay MVs v2). |
| /ops/real-lob/v2/data | GET | 200; body con `rows` y `totals`; o 200 con rows vacíos si no hay MVs v2. |
| /ops/real-lob/drill | GET | 200; body con estructura esperada por el drill (countries, rows, etc.). |
| /ops/real-strategy/lob | GET | 200; query param `country` requerido. |

**Nota:** Si en el entorno no existen MVs v2, `/ops/real-lob/filters` y `/ops/real-lob/v2/data` pueden devolver 200 con listas vacías o error controlado; el runbook documenta que en ese caso los endpoints que dependen de MVs no tendrán datos hasta tenerlas.

---

## 5. Validación de no regresión

- **Parks:** Filtros por park siguen devolviendo datos coherentes (o vacío si no hay datos).
- **Countries/Cities:** Filtros por país/ciudad coherentes.
- **B2B/B2C:** Segment_tag o equivalente en respuestas sin valores inesperados.
- **Sin categorías basura:** No aparecen `real_tipo_servicio_norm` o `lob_group` con valores claramente erróneos (ej. cadenas muy largas, caracteres raros) por la normalización.

---

## 6. Checklist UI (persistencia)

A ejecutar por Miguel o quien valide en frontend:

| Paso | Acción | PASS | FAIL |
|------|--------|------|------|
| 1 | Abrir pestaña REAL / Observabilidad. | Carga sin error. | Error de red o 5xx. |
| 2 | Cargar filtros (countries, cities, lob_groups, tipo_servicio). | Listas cargadas; no hay dos opciones equivalentes (ej. "confort+" y "Comfort Plus" por separado). | Duplicados visibles o error. |
| 3 | Tabla/datos REAL (v2 o la que use la vista). | Filas con `lob_group` y tipo de servicio canónicos; no duplicados por variante de nombre. | Aparecen confort+ y comfort_plus como filas distintas, o tuk-tuk y tuk_tuk. |
| 4 | Recargar página (F5). | Mismo comportamiento que en 2 y 3. | Duplicados reaparecen o datos distintos. |
| 5 | Cambiar de pestaña y volver a REAL. | Mismo comportamiento. | Inconsistencia. |
| 6 | Cambiar filtros (país, ciudad, LOB) y volver a solicitar datos. | Filtros aplican; sin duplicados en desplegables ni en tabla. | Duplicados o error. |
| 7 | Drill REAL (si aplica): desglose por LOB o por tipo de servicio. | Una sola categoría por concepto (ej. una "Comfort Plus", una "Tuk Tuk", una "Delivery"). | Varias filas para el mismo concepto. |
| 8 | WoW (semanal) o MoM (mensual). | Porcentajes calculados sobre categorías unificadas (no splits por variante de nombre). | WoW/MoM incoherente o duplicado. |

---

## 7. Criterio PASS/FAIL global

- **PASS:**  
  - Alembic con un solo head (093).  
  - Dimensiones pobladas; vista `v_real_trips_with_lob_v2` consultable.  
  - No existen simultáneamente categorías crudas y canónicas (confort+ vs comfort_plus, etc.).  
  - Endpoints probados responden 200 (o comportamiento documentado cuando faltan MVs).  
  - Checklist UI: sin duplicados en filtros/tablas/drill; persistencia al recargar y cambiar pestaña/filtros.

- **FAIL:**  
  - Varios heads sin resolver, o dimensiones vacías/inexistentes, o vista no consultable.  
  - Duplicados visibles (crudo + canónico) en datos o en UI.  
  - Regresión en filtros parks/countries/cities o en B2B/B2C.  
  - Script de cierre falla de forma no controlada (p. ej. por intentar refrescar MVs que no existen sin avisar).
