# YEGO Operational Flow — Historical Enrichment Discovery

**Fecha:** Mayo 2026
**Fase:** Control Foundation / Data Source Governance
**Estado:** Discovery — NO implementado en produccion

---

## 1. Problema de Vintage Limitation

El indicador `yego_operational_supply_30d` usa `public.module_ct_fleet_summary_daily` como fuente
principal para detectar nuevos conductores (primer dia con supply_hours > 0).

**Limitacion:** fleet_summary solo tiene datos desde **2026-02-15**.
Cualquier conductor que haya operado en YEGO antes de esa fecha, pero que NO tuvo
supply_hours entre Feb 15 y Marzo 31, aparece como "nuevo" en Abril 2026.
Esto es un **falso nuevo**.

---

## 2. Impacto Medido — Abril 2026 Lima

| Metrica | Fleet-only | Trips-enriched | Delta |
|---------|:---:|:---:|:---:|
| Nuevos YEGO | 2,747 | 1,089 | -1,658 (-60%) |
| Reactivados | 214 | 1,871 | +1,657 |
| Flujo total | 2,961 | 2,960 | ~igual |
| Vintage risk | 60% | 0% | - |

- **548 drivers (20%)** tenian viajes completados ANTES de Feb 15 2026 (antes del inicio de fleet_summary)
- **1,658 drivers** fueron reclasificados de "nuevo" a "reactivado" o "existente con historia"
- El flujo total (N+R) se mantiene estable (~2,960), pero la composicion cambia radicalmente

---

## 3. Por que trips_2025/trips_2026 pueden enriquecer

| Evidencia | Valor |
|-----------|-------|
| fleet_summary drivers en trips_2026 | 89.2% |
| Driver ID compatible entre fuentes | SI |
| trips_2025 cobertura historica | 2025 completo |
| trips_2026 cobertura | 2026 en curso |
| Parque principal Yego Lima | 6,558 drivers abril |

El 89.2% de los conductores de fleet_summary tambien aparecen en trips_2026.
Los driver_id son compatibles (mismo formato UUID). Esto permite usar trips
como fuente auxiliar de presencia historica.

---

## 4. Por que trips NO debe reemplazar fleet_summary

| Razon | Detalle |
|-------|---------|
| trips es mas amplio | 27,167 drivers vs 12,589 fleet_summary |
| trips no tiene supply_hours | La senal de actividad principal es SH, no viajes |
| trips incluye otros parques | Hay 1,042 drivers en trips Lima que NO estan en fleet_summary |
| trips no es fuente primaria de operaciones | fleet_summary es la fuente disenada para tracking operativo |

trips debe usarse SOLO como evidencia auxiliar de presencia historica previa,
no como fuente principal de actividad actual.

---

## 5. Ventanas de Reactivacion Probadas

| Ventana | Nuevos (enr.) | Reactivados (enr.) | Flujo total | Nota |
|---------|:---:|:---:|:---:|---|
| 30d | 1,089 | 1,871 | 2,960 | Mejor sensibilidad |
| 60d | 1,089 | 1,574 | 2,663 | Reactivados mas restrictivos |
| 90d | 1,089 | 1,404 | 2,493 | Ventana mas conservadora |

Recomendacion: **30 dias** para monitoreo interno (mayor sensibilidad).
60 dias si se quiere ser mas conservador con la definicion de reactivado.

---

## 6. Riesgos del Enriquecimiento

| Riesgo | Mitigacion |
|--------|-----------|
| Contaminacion de universo (drivers no-YEGO en trips) | Filtrar trips por parques Lima Yego (dim_park.city='lima') |
| Driver ID mismatch en algunos casos | Aceptar solo drivers que aparecen en AMBAS fuentes |
| Trips como fuente de actividad actual | Usar trips SOLO para presencia historica, no para actividad del mes |
| Performance de queries | Promover a materialized view si se usa frecuentemente |

---

## 7. Conclusion

**SI** — trips_2025 y trips_2026 PUEDEN usarse como enriquecimiento historico
para YEGO Operational Flow. El 20% de los "nuevos" detectados por fleet_summary
en Abril 2026 son falsos nuevos. El enriquecimiento reduce la inflacion de nuevos
en 60% sin alterar el flujo total significativamente.

---

## 8. Propuesta de Fase Futura

1. Crear `ops.mv_yego_driver_historical_presence` con first_seen_date por driver
   combinando fleet_summary (primario) + trips (auxiliar)
2. Modificar `yego_operational_supply_30d` para usar historical presence en vez de
   fleet_summary-only para deteccion de nuevos
3. Promover operational flow a serving fact (MV) para reducir runtime
4. NO activar scoring oficial Yango basado en este indicador

**Estado:** PENDIENTE de decision de implementacion.

---

**Documento generado por:** YEGO Control Tower / Data Source Governance
**Version:** 1.0 / Mayo 2026
