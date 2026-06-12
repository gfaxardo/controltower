# OV2-MVP.4A — OPERATOR TRAINING GUIDE

> **Fase:** OV2-MVP.4A — Deprecation Preparation
> **Sub-document:** Operator Training Guide
> **Fecha:** 2026-06-12

---

## 1. ¿QUÉ ES OMNIVIEW V2?

Omniview V2 es la nueva version de la matriz operacional. Muestra los mismos datos que V1 (trips, revenue, drivers, etc.) pero con:

- **Mejor arquitectura** — mas rapida, mas ligera
- **Source badges** — sabes de donde vienen los datos (CT o Yango)
- **Signal colors** — colores que te dicen si algo va bien o mal
- **Fullscreen** — aprovecha toda la pantalla
- **Park filter** — filtra por parque directamente

---

## 2. DIFERENCIAS CON V1

| V1 | V2 |
|----|----|
| Omniview Matrix | Omniview V2 MVP |
| Evolution / Projection modes | Real Matrix + Plan vs Real |
| Filtro: Year + Month | Filtro: Date from/to (mas flexible) |
| KPI: 7 metricas | KPI: 6 metricas (commission muestra N/A temporalmente) |
| Status bar fija | Status bar colapsable |
| No source info | Badge CT/YANGO en cada celda |
| Sin fullscreen | Boton [F] Fullscreen |
| Sin park filter | Dropdown de parque |
| Inspector con Evolution/Momentum | Inspector con Value, Source, Trust, Drill |

---

## 3. BUSINESS SLICE

V2 muestra cada business slice como una fila en la matriz:

- **Auto Regular** — autos normales
- **PRO** — flota premium
- **Tuk Tuk** — mototaxis
- **Delivery** — entregas
- **Carga** — carga
- **YMA** — YMA

Filtra por slice con el dropdown "All Slices".

---

## 4. EXECUTION CONTEXT

Cuando seleccionas "Plan vs Real (Monthly)", V2 muestra:

| Columna | Significado |
|---------|-------------|
| **Real** | Lo que realmente paso |
| **Plan** | Lo que estaba planeado |
| **Gap** | Plan - Real |
| **Attainment %** | Real / Plan × 100 |

Si no hay plan: muestra "Plan no disponible" pero **no oculta Real**.

---

## 5. SOURCE BADGES

| Badge | Significado |
|-------|-------------|
| **CT** (verde) | Datos de Control Tower (fuente oficial) |
| **YAN** (violeta) | Datos de Yango API (shadow, no oficial) |
| **FB** (ambar) | Fallback — CT no disponible, usando alternativa |

---

## 6. TRUST SIGNALS

| Color/Senal | Significado |
|-------------|-------------|
| Borde verde | Delta positivo — el valor subio |
| Borde rojo | Delta negativo — el valor bajo |
| Borde gris | Sin cambio |
| Celda ambar | Warning — datos no canonicos |
| Celda gris | Bloqueado — sin datos |
| ▲ | Subio |
| ▼ | Bajo |
| → | Igual |
| N/A | No disponible |

---

## 7. FILTERS

V2 tiene 6 filtros (vs 4 en V1):

1. **Source** — CT Trips o Yango API
2. **Grain** — Day / Week / Month
3. **Date From/To** — rango de fechas
4. **Country** — Peru / Colombia
5. **City** — Lima, Trujillo, Arequipa, etc.
6. **Park** — Lima, Trujillo, Arequipa, Pro, TukTuk
7. **Business Slice** — Auto Regular, Delivery, PRO, etc.

---

## 8. FULLSCREEN

- Click **[F] Fullscreen** en la barra superior
- La matriz ocupa toda la pantalla
- Los filtros y status bar se mantienen
- Presiona **Esc** para salir

---

## 9. STATUS BAR

Click en **> Status** para expandir:

- Fecha operativa
- Freshness (FRESH/STALE/CRITICAL)
- Coverage %
- Source (CANONICAL/SHADOW)
- Fallback status

---

## 10. FAQ

**¿Donde estan los reportes ECharts?**
Los graficos de barra/linea no estan en V2 todavia. Usa la matriz + filtros como alternativa. Los reportes graficos volveran en una version futura.

**¿Por que Commission muestra N/A?**
El pipeline de datos de commission no esta generando valores todavia. V2 muestra N/A para no mostrar un 0% falso. Se esta trabajando en la solucion.

**¿Puedo volver a V1?**
Si. V1 sigue disponible en "Omniview Matrix" en la barra lateral. V2 es la herramienta recomendada pero V1 es el respaldo.

**¿V2 reemplaza a V1?**
Eventualmente si. Durante el trial, V2 es la herramienta principal. V1 queda como respaldo por ahora.

**¿Los datos son los mismos?**
Si. V2 usa los mismos serving facts que V1. Las metricas deben coincidir. Si ves diferencias, reportalo como friccion.
