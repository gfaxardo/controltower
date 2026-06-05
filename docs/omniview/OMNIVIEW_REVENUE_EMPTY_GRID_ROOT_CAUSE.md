# OMNI-P0-T5 — REVENUE EMPTY GRID ROOT CAUSE

**Motor:** Omniview P0 Recovery  
**Fecha:** 2026-06-03  
**Estado:** ANÁLISIS COMPLETADO — PENDIENTE FIX

---

## 1. LA PREGUNTA CENTRAL

> ¿Por qué Revenue aparece vacío/incompleto en varias grillas de Vs Proy?

---

## 2. MAPA DE REVENUE POR ENDPOINT Y GRAIN

| Endpoint | Modo | Grain | Campo expuesto | Fuente real en DB | Cobertura |
|----------|------|-------|---------------|-------------------|-----------|
| `/ops/business-slice/omniview` | Evolution | daily | `revenue_yego_net` | `COALESCE(revenue_yego_final, revenue_yego_net)` de day_fact | Alta (COALESCE) |
| `/ops/business-slice/omniview` | Evolution | weekly | `revenue_yego_net` | `COALESCE(revenue_yego_final, revenue_yego_net)` de week_fact | Alta (COALESCE) |
| `/ops/business-slice/omniview` | Evolution | monthly | `revenue_yego_net` | `COALESCE(revenue_yego_final, revenue_yego_net)` de month_fact | Media (COALESCE, pero `_final` solo en 79%) |
| `/ops/business-slice/omniview-projection` | **Vs Proy** | daily | `revenue_yego_net` | **SIN COALESCE** — solo `revenue_yego_net` raw | **BAJA (9.7%)** |
| `/ops/business-slice/omniview-projection` | **Vs Proy** | weekly | `revenue_yego_net` | **SIN COALESCE** — solo `revenue_yego_net` raw | **BAJA (79.8%)** |
| `/ops/business-slice/omniview-projection` | **Vs Proy** | monthly | `revenue_yego_net` | **SIN COALESCE** — solo `revenue_yego_net` raw | **BAJA (12.4%)** |

---

## 3. ROOT CAUSE #1: EL ENDPOINT DE VS PROY NO HACE COALESCE

### Evolution (sí tiene COALESCE)

`business_slice_omniview_service.py:656`:
```python
sql_revenue_col = "COALESCE(revenue_yego_final, revenue_yego_net)"
```

Esto lee `revenue_yego_final` (que existe en 93.5% de day_fact, 99.3% de week_fact) y solo usa `revenue_yego_net` como fallback. El resultado se expone como `revenue_yego_net`.

### Vs Proy (NO tiene COALESCE)

`projection_expected_progress_service.py` lee directamente `revenue_yego_net` de las fact tables. **No aplica COALESCE con `revenue_yego_final`.**

Resultado: En daily, donde `revenue_yego_net` es NULL en 90.3% de las filas, Vs Proy muestra celdas vacías.

---

## 4. ROOT CAUSE #2: DATOS DE REVENUE EN FACT TABLES

| Fact Table | `revenue_yego_net` non-null | `revenue_yego_final` non-null | Diferencia |
|------------|---------------------------|------------------------------|------------|
| day_fact | 775/8017 (9.7%) | 7498/8017 (93.5%) | **83.8pp** |
| week_fact | 981/1229 (79.8%) | 1221/1229 (99.3%) | **19.5pp** |
| month_fact | 41/331 (12.4%) | 262/331 (79.2%) | **66.8pp** |

`revenue_yego_net` = solo comisión real (NULL si no hay commission para ese slice/período).  
`revenue_yego_final` = `COALESCE(revenue_yego_real, revenue_yego_proxy)` — best-effort con proxy cuando no hay comisión real.

**Conclusión**: `revenue_yego_net` NO es adecuado como campo primario de serving. `revenue_yego_final` debe ser el campo canónico.

---

## 5. ROOT CAUSE #3: EL FRONTEND NO PUEDE RESOLVERLO

El frontend (`projectionMatrixUtils.js`) espera `revenue_yego_net` en el payload de Vs Proy. No hay COALESCE en el frontend porque:

1. `revenue_yego_final` NO se expone en el endpoint de proyección
2. El frontend no tiene acceso a la lógica de COALESCE del backend
3. El campo se llama igual (`revenue_yego_net`) en ambos endpoints pero con valores diferentes

---

## 6. PLAN DE FIX

### Fix 1 — Backend: Unificar revenue en Vs Proy

En `projection_expected_progress_service.py`, donde se lee revenue de las fact tables:

```python
# ANTES: Solo lee revenue_yego_net
SELECT revenue_yego_net FROM ...

# DESPUÉS: COALESCE con _final
SELECT COALESCE(revenue_yego_final, revenue_yego_net) AS revenue_yego_net FROM ...
```

O mejor: exponer `revenue_yego_final` como campo separado y que el frontend lo use.

### Fix 2 — Backend: Exponer `revenue_yego_final` explícitamente

Añadir al payload de `/ops/business-slice/omniview-projection`:

```json
{
  "revenue_yego_final": 123456.78,
  "revenue_yego_net": 123456.78,
  "revenue_yego_final_projected_total": 130000.0,
  ...
}
```

### Fix 3 — Frontend: Leer `revenue_yego_final` si existe

En `projectionMatrixUtils.js`, priorizar `revenue_yego_final` sobre `revenue_yego_net`:

```js
const revenue = row.revenue_yego_final ?? row.revenue_yego_net
```

---

## 7. ¿ES EXPECTED EMPTY O BUG?

| Grain | ¿Expected empty? | Razón |
|-------|-----------------|-------|
| Daily | **BUG** | `revenue_yego_final` existe en 93.5% de day_fact pero no se expone en Vs Proy |
| Weekly | **BUG** | `revenue_yego_final` existe en 99.3% de week_fact pero el endpoint de proyección no lo usa |
| Monthly | **BUG** | `revenue_yego_final` existe en 79.2% de month_fact. El 20.8% restante es expected empty histórico |

**Conclusión: NO es expected empty. Es un bug de wiring entre el endpoint de proyección y las fact tables.**

---

## 8. VERIFICACIÓN POST-FIX

- [ ] `/ops/business-slice/omniview-projection` expone `revenue_yego_final`
- [ ] Revenue visible en daily Vs Proy (no celdas vacías)
- [ ] Revenue visible en weekly Vs Proy (no celdas vacías)
- [ ] Revenue visible en monthly Vs Proy (mejora de 79.2% → ~99%)
- [ ] Frontend prioriza `revenue_yego_final` sobre `revenue_yego_net`
- [ ] Sin regresión en Evolution

---

**END OF ROOT CAUSE**
