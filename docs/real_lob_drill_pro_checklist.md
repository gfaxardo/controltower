# Real LOB Drill PRO — Checklist de validación

## 1) Países
- [ ] PE aparece arriba, CO abajo en la pantalla.

## 2) Colombia parks
- [ ] En CO aparecen parks incluso si no existen en `public.parks` (se muestran como `UNKNOWN_PARK (id)`).
- [ ] Para asignar país a parks huérfanos: insertar en `ops.park_country_fallback(park_id, country)`.

## 3) Nombres nunca vacíos
- [ ] No aparecen "—" como park/city: si falta, se muestra `SIN_PARK` / `SIN_CITY`.

## 4) Calendario completo
- [ ] Feb 2026 (y mes actual) aparece aunque con 0 viajes, con estado "Falta data" o "Vacío" según cobertura.
- [ ] Semanal usa semana ISO (lunes como inicio; `date_trunc('week', ...)` en PostgreSQL).

## 5) Margen y distancia
- [ ] `margen_total` y `margen_trip` se muestran en positivo (comision_empresa_asociada viene negativa; se usa `-SUM` / `-AVG`).
- [ ] `km_prom` = AVG(distancia_km)/1000 (distancia_km en metros en `trips_all`).

## 6) B2B
- [ ] Segmento B2B: viajes con `pago_corporativo IS NOT NULL`.
- [ ] Selector Segmento: Todos / B2C / B2B.
- [ ] En filas: viajes_b2b y pct_b2b visibles cuando segmento = Todos.

## 7) Performance
- [ ] Primera carga &lt; 2 s con MV (`ops.mv_real_lob_drill_agg`).
- [ ] Expand children &lt; 1 s.

## 8) Navegación
- [ ] Por defecto solo "Real LOB" y "Legacy" en la barra.
- [ ] Con `VITE_CT_LEGACY_ENABLED=true` se muestran todos los tabs.
- [ ] Dentro de Legacy están Plan Válido, Expansión, Huecos, Fase 2B, Fase 2C, Universo & LOB.

## Refresh MVs
```bash
cd backend && python -m scripts.refresh_real_lob_drill_pro_mv
```
Recomendado: cron diario tras carga de datos en `trips_all`.
