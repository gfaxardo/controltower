# REVENUE DETAIL PAYLOAD AUDIT

**Motor:** Control Foundation  
**Fecha:** 2026-05-31  

---

## 1. Endpoint Auditado

`GET /ops/business-slice/omniview-projection`

### 1.1 Backend Service

Archivo: `backend/app/services/projection_expected_progress_service.py`

| Aspecto | Valor |
|---------|-------|
| KPI key usada | `revenue_yego_net` (no `revenue`, no `revenue_real`) |
| Plan column | `projected_revenue` |
| Real column | `real_revenue` (ABS'd desde `COALESCE(revenue_yego_final, revenue_yego_net)`) |
| Row mode "matched" | `_build_projection_row_monthly` — asigna `revenue_yego_net = actual` |
| Row mode "missing_plan" | `_build_no_plan_row` — asigna `revenue_yego_net = actual` (real sin plan) |
| Row mode "plan_without_real" | Revenue = `None` (no hay real data para esa tajada) |

### 1.2 Campos de Revenue por Fila

Cada fila en `data[]` contiene estos campos para revenue:

```json
{
  "revenue_yego_net": <float | null>,
  "revenue_yego_net_projected_total": <float | null>,
  "revenue_yego_net_projected_expected": <float | null>,
  "revenue_yego_net_attainment_pct": <float | null>,
  "revenue_yego_net_gap_to_expected": <float | null>,
  "revenue_yego_net_gap_pct": <float | null>,
  "revenue_yego_net_gap_to_full": <float | null>,
  "revenue_yego_net_completion_pct": <float | null>,
  "revenue_yego_net_signal": "green" | "warning" | "danger" | "no_data",
  "revenue_yego_net_comparison_basis": "full_month" | "expected_to_date_month" | ...,
  "revenue_yego_net_audit_raw": <float | null>
}
```

### 1.3 Posibles Causas de Revenue Vacío en Detalle

| Causa | Descripción |
|-------|-------------|
| `plan_without_real` | Existe plan pero no real data → `revenue_yego_net = None` |
| Real data con NULL | `revenue_yego_final` y `revenue_yego_net` ambos NULL en serving fact |
| Serving fact ausente | No hay serving fact → runtime fallback solo en scripts |
| `comparison_status = "plan_without_real"` | Fila excluida del TOTAL en display_rows, pero presente en UI |

### 1.4 Totals en Response

El backend también retorna `meta.ytd_summary.total` con revenue agregado. Los totals del frontend no vienen del backend — se computan sumando `raw.revenue_yego_net` de todas las filas en `data[]`.

---

## 2. Verificaciones en Runtime

Ejecutar y verificar:

```bash
curl "http://localhost:8000/ops/business-slice/omniview-projection?plan_version=UNIFIED_V2_TEST&grain=daily&year=2026" | python -m json.tool | head -200
```

Verificar en la respuesta:
1. `data[].revenue_yego_net` no es null para ciudades principales
2. `meta.total_rows` o conteo de filas
3. Cuántas filas tienen `comparison_status = "plan_without_real"` (revenue = None)
4. Cuántas filas tienen `comparison_status = "missing_plan"` (revenue = real sin plan)

---

## 3. Conclusión

El payload del endpoint es correcto en estructura. La clave `revenue_yego_net` es consistente. El problema de "TOTAL muestra revenue pero detalle vacío" se debe a:

1. **Frontend display**: `hasReal = actual > 0` oculta revenue = 0 (corregido en este pack)
2. **Data ausente**: Para algunos city/line, `revenue_yego_net = null` porque el serving fact no tiene `revenue_yego_final` / `revenue_yego_net` para esa combinación. Requiere investigación de DB.
