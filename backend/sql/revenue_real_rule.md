# Revenue Real YEGO - Regla Canónica

## Definición

**Revenue Real YEGO** es la suma de `comision_empresa_asociada` de todos los viajes completados, por mes y dimensión operativa.

### Fórmula por viaje

```sql
commission_yego_signed := COALESCE(NULLIF(public.trips_all.comision_empresa_asociada, 0), 0)
revenue_real_yego := -1 * commission_yego_signed
```

### Agregación mensual

```sql
commission_yego_signed := SUM(COALESCE(NULLIF(comision_empresa_asociada, 0), 0))
revenue_real_yego := -1 * commission_yego_signed
```

## Reglas de Negocio

### 1. Valores NULL o 0

- Si `comision_empresa_asociada` es `NULL` o `0`:
  - Se considera "sin comisión registrada"
  - Se audita la cobertura (ver validaciones)
  - No se suma al revenue (NULLIF convierte 0 a NULL, que se ignora en SUM)

### 2. Valores Negativos

- `comision_empresa_asociada` viene **negativa por convención contable**.
- Se mantiene el valor signed en `commission_yego_signed` para auditoría.
- `revenue_real_yego` se invierte a positivo: `revenue_real_yego = -commission_yego_signed`.

### 3. Moneda

- La moneda es la misma del país del viaje:
  - Perú (PEN): `comision_empresa_asociada` en soles
  - Colombia (COP): `comision_empresa_asociada` en pesos
- **NO se convierte** entre monedas
- La agregación se hace por país para mantener consistencia monetaria

## Trazabilidad

### Tabla fuente
- `public.trips_all.comision_empresa_asociada`
- Filtro: `condicion = 'Completado'`

### Vista materializada
- `ops.mv_real_trips_monthly.revenue_real_yego`
- Agregado por: `(month, country, city_norm, lob_base, segment)`

### Validación de reconciliación

```sql
-- Debe coincidir exactamente (tolerancia 0)
SELECT 
    SUM(comision_empresa_asociada) as direct_sum,
    SUM(revenue_real_yego) as mv_sum
FROM public.trips_all t
JOIN ops.mv_real_trips_monthly mv ON ...
WHERE t.condicion = 'Completado'
  AND t.fecha_inicio_viaje >= date_trunc('month', now()) - interval '1 month'
```

## Cobertura Esperada

- **Mínimo aceptable:** 95% de viajes completados deben tener `comision_empresa_asociada` no NULL y no 0
- **Ideal:** 100% de cobertura
- Si cobertura < 95%: WARNING (no bloquea, pero se audita)

## Diferencias con Revenue Proxy (Deprecado)

| Métrica | Fuente | Estado |
|---------|--------|--------|
| `revenue_real_proxy` | `SUM(precio_yango_pro)` | ❌ DEPRECADO (Fase 2A) |
| `revenue_real_yego` | `SUM(comision_empresa_asociada)` | ✅ CANÓNICO (Fase 2A+) |

**Nota:** `revenue_real_proxy` era un proxy porque usaba el precio del viaje (GMV) en lugar de la comisión real. `revenue_real_yego` usa la comisión real registrada en la transacción.

## Auditoría

Ver `backend/scripts/validate_phase2a_no_proxy.py` para:
- Validación de cobertura de comisión
- Reconciliación mensual
- Detección de anomalías (valores negativos, NULLs inesperados)
