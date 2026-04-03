# YEGO Control Tower — Source of Truth V2

**Fecha de congelamiento:** 2026-04-02
**Estado:** OPERATIVO CON LIMITACIONES CONOCIDAS
**Versión:** V2 — Post-auditoría, consolidación y hardening

---

## 1. Fuentes oficiales

| Tabla | Rango | Estado | Uso |
|-------|-------|--------|-----|
| `public.trips_2025` | 2025-01-01 a 2025-12-31 | OFICIAL | Auditoría, facts, MVs |
| `public.trips_2026` | >= 2026-01-01 | OFICIAL | Auditoría, facts, MVs |
| `public.trips_all` | Histórico | LEGACY | Solo backward compatibility |

**Regla:** Todo nuevo desarrollo DEBE usar trips_2025 + trips_2026. trips_all NO debe ser fuente de nuevos consumidores.

---

## 2. Semántica: completados vs cancelados

| Estado | Criterio SQL | Universo de métricas |
|--------|-------------|---------------------|
| **Completado** | `condicion = 'Completado'` | revenue, ticket, active_drivers, trips_per_driver, comisión, margen |
| **Cancelado** | `condicion = 'Cancelado' OR ILIKE '%cancel%'` | trips_cancelled, cancel_rate, motivo_cancelacion |
| **Otro** | Todo lo demás | Excluido de métricas operativas |

Completado y cancelado son mutuamente excluyentes. En agregados se usan FILTER separados.

---

## 3. Revenue: real vs proxy

### Arquitectura

```
comision_empresa_asociada (raw) → revenue_yego_real (si disponible)
precio_yango_pro × commission_pct → revenue_yego_proxy (si real no disponible)
COALESCE(real, proxy) → revenue_yego_final (estándar operativo)
```

### Estado de comision_empresa_asociada

| Periodo | Cobertura en completados | Estado |
|---------|-------------------------|--------|
| 2025 (todos los meses) | 0.00% (6 registros de 10.2M) | NUNCA POBLADO |
| 2026 enero | 94.45% | FUNCIONAL |
| 2026 febrero | 49.91% | PARCIAL (quiebre mid-month) |
| 2026 marzo+ | 0.00% | ROTO |

**Diagnóstico de causa raíz:**
- **Clasificación:** Pipeline break — no bug de esquema
- **2025:** El campo EXISTE en la tabla pero NUNCA fue poblado por el pipeline de ingestión
- **2026:** Fue poblado correctamente en enero; se degradó en febrero; murió en marzo
- **Signo:** Todos los valores son NEGATIVOS (avg -131.42, rango -18,456 a -0.10)
- **Acción requerida:** El equipo de ingestión debe reparar el pipeline upstream

### Configuración de comisión proxy

Tabla `ops.yego_commission_proxy_config` con ratios reales calculados de enero 2026:

| Contexto | Comisión % | Confianza | Fuente |
|----------|-----------|-----------|--------|
| **Default global** | 3.00% | ALTA | Mediana exacta = 3.00%, avg = 2.96%, N=848K |
| Peru genérico | 3.00% | ALTA | Mediana = 3.00%, avg = 3.04% |
| Colombia genérico | 3.00% | ALTA | Mediana = 3.00%, avg = 2.86% |
| **Bogotá** | **4.00%** | ALTA | Mediana = 4.00%, avg = 4.00%, stddev = 0.0005 |
| **Cúcuta** | **2.50%** | MEDIA | Mediana = 2.50%, avg = 2.66%, N=384 |
| **Moto** (tipo_servicio) | **2.50%** | ALTA | Mediana = 2.50%, avg = 2.50%, N=96K |
| **Cargo** (tipo_servicio) | **4.00%** | ALTA | Mediana = 4.00%, avg = 3.96%, N=4.9K |
| **Mensajería** (tipo_servicio) | **3.50%** | MEDIA | Mediana = 3.64%, avg = 3.35%, N=12.9K |

**Regla de resolución:** Match más específico gana → priority DESC → valid_from DESC.

### Campos de revenue en el sistema

| Campo | Dónde | Significado |
|-------|-------|-------------|
| `revenue_yego_net` | enriched_base | NULLIF(comision_empresa_asociada, 0) — original sin ABS |
| `revenue_yego_real` | proxy audit view | ABS(comision) si disponible |
| `revenue_yego_proxy` | proxy audit view | ticket × commission_pct |
| `revenue_yego_final` | BS facts, proxy audit | COALESCE(real, proxy) |
| `gross_revenue` | fact_v2 → hour → day | GREATEST(0, COALESCE(real, proxy, 0)) |
| `margin_total` | fact_v2 → hour → day | COALESCE(real, proxy) |
| `revenue_source` | fact_v2 | 'real' \| 'proxy' \| 'missing' |

---

## 4. Cadenas del sistema y estado

| Cadena | Fuente raw | Revenue | Estado |
|--------|-----------|---------|--------|
| **Hourly-first** (canon_120d → fact_v2 → hour → day → week → month) | trips_2025 + trips_2026 | Consolidado (proxy) | OPERATIVO |
| **Business Slice** (enriched_base → resolved → facts) | trips_2025 + trips_2026 | Consolidado (proxy) | OPERATIVO |
| **Drill** (real_drill_dim_fact) | Desde hourly-first | Consolidado | OPERATIVO |
| **Real operational** (servicios) | Desde day_v2/hour_v2 | Consolidado | OPERATIVO |
| Canonical monthly hist | v_trips_real_canon (trips_all) | Legacy (no proxy) | LEGACY |
| MV mensual/semanal legacy | trips_all | Legacy | LEGACY |
| LOB monthly/weekly | trips_all | Legacy | LEGACY |

---

## 5. Reglas de fallback

1. Si `comision_empresa_asociada` existe y es != 0 → usar como revenue real
2. Si no existe pero `precio_yango_pro` existe y > 0 → calcular proxy con config
3. Si ninguno disponible → `revenue_source = 'missing'`, revenue = NULL/0
4. NaN en `precio_yango_pro` o `comision_empresa_asociada` → convertido a NULL por guard (migración 122)
5. Proxy NUNCA sobreescribe el dato real; solo lo complementa donde falta

---

## 6. Alertas y hardening

### Sistema de alertas

| Alerta | Métrica | Umbral | Severidad |
|--------|---------|--------|-----------|
| NaN en fuente raw | precio_yango_pro = NaN | > 0 | blocked |
| Proxy excesivo | % proxy completados | ≥ 80% warn, ≥ 95% blocked | warning/blocked |
| Revenue missing | % missing | ≥ 5% warn, ≥ 20% blocked | warning/blocked |
| NaN en agregados | NaN en day_v2 | > 0 | blocked |
| Zero revenue ciudad | Revenue = 0 con actividad | > 0 | blocked |
| Drift entre cadenas | % diferencia HF vs BS | ≥ 15% warn, ≥ 40% blocked | warning/blocked |
| Datos desactualizados | Horas sin dato nuevo | ≥ 48h | blocked |

### Action Engine

14 acciones operativas definidas. Motor evalúa métricas WoW por ciudad + alertas de calidad y genera acciones priorizadas con owner sugerido.

### Endpoints de monitoreo

| Endpoint | Función |
|----------|---------|
| `GET /ops/revenue-quality/check` | Check completo + alertas |
| `GET /ops/revenue-quality/alerts` | Historial de alertas |
| `GET /ops/revenue-quality/by-city` | Breakdown por ciudad |
| `GET /ops/revenue-proxy/coverage` | Cobertura real vs proxy |
| `GET /ops/revenue-proxy/config` | Config de comisión |
| `GET /ops/action-engine/run` | Ejecutar engine |
| `GET /ops/action-engine/today` | Acciones del día |

---

## 7. Limitaciones conocidas

| # | Limitación | Impacto | Estado |
|---|-----------|---------|--------|
| 1 | `comision_empresa_asociada` rota en 2025 y marzo 2026+ | Revenue opera 100% proxy para esos periodos | DOCUMENTADO |
| 2 | 3 registros con NaN en precio_yango_pro (trips_2026) | Neutralizados por guard pero existen en raw | MITIGADO |
| 3 | Country normalization: HF usa 'co'/'pe', BS usa 'colombia'/'peru' | Drift esperado en comparaciones cross-chain | DOCUMENTADO |
| 4 | MV day_v2 muestra revenue=0 para marzo 2026 | Requiere investigación post-refresh | PENDIENTE |
| 5 | Cadenas legacy siguen dependiendo de trips_all | Migración pendiente (no bloquea operación) | PLANIFICADO |
| 6 | Business Slice facts no tienen columnas proxy repobladas | Requiere re-populate con refresh_business_slice_mvs | PENDIENTE |

---

## 8. Operación del sistema

### Universo

- **9 ciudades activas:** Cali (22.5M), Lima (18.5M), Barranquilla (9.3M), Medellín (6.7M), Trujillo (1.4M), Arequipa (0.7M), Bucaramanga (87K), Bogotá (68K), Cúcuta (15K)
- **59.2M viajes** en trips_2025 + trips_2026
- **12.9M completados** (21.7%), **46.3M cancelados** (78.3%)
- **100% mapeado territorialmente** (29 parks en dim.dim_park)

### Métricas validadas (últimos 7 días, fact_v2)

| Ciudad | Active drivers | Trips | Trips/driver |
|--------|---------------|-------|-------------|
| Lima | 3,259 | 90,329 | 27.72 |
| Cali | 2,013 | 69,914 | 34.73 |
| Barranquilla | 465 | 11,468 | 24.66 |
| Trujillo | 231 | 7,403 | 32.05 |
| Arequipa | 159 | 4,424 | 27.82 |
| Bogotá | 140 | 1,272 | 9.09 |
| Medellín | 51 | 560 | 10.98 |

### Métricas de cancelación (último mes cerrado, day_v2)

- Cancel rate general: 75-90% (alto, esperado por modelo de negocio ride-hailing)
- Bogotá: 37.58% (significativamente más bajo — posible diferencia operativa)

---

## 9. Qué falta (ingestión)

**El sistema está OPERATIVO pero NO resuelto en origen.**

Para salir de dependencia proxy:

1. **Reparar pipeline de ingestión** de `comision_empresa_asociada` en la fuente upstream
2. **Backfill 2025** si alguna vez estuvo disponible en otra fuente
3. **Backfill febrero 2026** (50% faltante) y marzo+ (100% faltante)
4. Una vez reparado, el proxy se reduce automáticamente (COALESCE prioriza real)

---

## 10. Migraciones del sistema

| # | Migración | Propósito |
|---|-----------|-----------|
| 118 | enriched_base_trips_2025_2026 | Business Slice a trips oficiales |
| 120 | revenue_proxy_config_and_layer | Config proxy + vistas audit |
| 121 | consolidate_hourly_first_revenue | Canon 120d sin trips_all + proxy en fact_v2 |
| 122 | revenue_hardening_nan_guard | NaN guard + tabla alertas |
| 123 | action_engine_catalog_and_output | Action Engine |

---

## 11. Veredicto

**GO CONDICIONADO**

El sistema es **operable y confiable dentro de sus limitaciones documentadas**:
- Revenue funciona via proxy calibrado con datos reales (mediana exacta 3.00%)
- Alertas detectan degradación automáticamente
- Action Engine traduce problemas en acciones
- Todo es trazable y auditable

**Condiciones para GO completo:**
1. Reparar ingestión de comision_empresa_asociada upstream
2. Resolver revenue=0 en MVs para ciudades activas
3. Repoblar Business Slice facts con proxy
4. Migrar cadenas legacy restantes
