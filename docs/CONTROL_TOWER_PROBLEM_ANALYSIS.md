# CONTROL TOWER — ANÁLISIS DE PROBLEMAS

Documento de auditoría: problemas estructurales reales, priorizados, con recomendaciones concretas. No describe el sistema (ver CONTROL_TOWER_SYSTEM_MAP.md).

---

## FASE 1 — DETECCIÓN DE PROBLEMAS

### 1. DUPLICIDAD DE FUENTES DE VERDAD

#### Viajes (trips reales)

| Fuente | Grano | Incluye trips_2026 | Usado en |
|--------|-------|--------------------|----------|
| **ops.mv_real_trips_monthly** | month | **No** (solo trips_all) | Resumen, KPICards, /ops/real/monthly, /real/summary/monthly, core_service |
| **ops.mv_real_trips_by_lob_month/week** | month/week | Depende de v_real_trips_with_lob_v2 (canon completo) | Real LOB legacy (/ops/real-lob/monthly, weekly) |
| **ops.mv_real_lob_month_v2 / week_v2** | month/week | **Sí** (120d) | Real LOB v2, real_lob_service_v2 |
| **ops.mv_real_rollup_day** + **mv_real_drill_dim_agg** | day/period | **Sí** (120d) | Real Drill, Drill PRO |
| **ops.mv_real_lob_hour_v2, day_v2, week_v3, month_v3** | hour/day/week/month | **Sí** (120d) | Real Operativo |

**Problema:** La vista que alimenta el **Resumen ejecutivo** (KPICards, Plan vs Real) es **ops.mv_real_trips_monthly**, que en la migración 013 se construye únicamente desde **public.trips_all**. No incluye **trips_2026**. Por tanto, en 2026 el “Real” del Resumen está **incompleto o desfasado** respecto a Drill y Operativo.

- **Fuente correcta para “Real” único:** La cadena que une trips_all + trips_2026 con deduplicación (v_trips_real_canon o v_trips_real_canon_120d) y luego agrega. Hoy eso lo hace la cadena 120d (rollup_day, drill_dim_agg, lob_month_v2).
- **Qué deprecar:** No deprecar MVs sin migración. Sí **dejar de usar mv_real_trips_monthly como única fuente del Resumen**; unificar Resumen con una fuente que incluya 2026 (o documentar explícitamente “Real sin 2026” en UI).

#### Revenue

| Fuente | Definición | Usado en |
|--------|------------|----------|
| **mv_real_trips_monthly.revenue_real_yego** | SUM(comision_empresa_asociada) desde trips_all | Resumen, /ops/real/monthly |
| **mv_real_lob_*_v2** (cadena 120d) | Misma lógica desde canon 120d | Real LOB v2, Drill, Operativo |
| **real_rollup_day / drill** | Margen/revenue desde fact 120d | Real Drill |

**Problema:** La **definición** es la misma (comision_empresa_asociada), pero el **universo de viajes** no: Resumen excluye 2026, el resto puede incluirlo. Resultado: totales distintos por pantalla.

- **Fuente correcta:** Una sola definición de “revenue real” (ej. comision_empresa_asociada sobre v_trips_real_canon o 120d) y que Resumen y Drill lean del mismo universo (o se etiquete “Real histórico sin 2026” en Resumen).

#### Margin

- **Drill:** margin_total_raw, margin_total_pos, margin_unit_pos (desde rollup_day / real_drill_dim_fact).
- **Real LOB v2 / Operativo:** Pueden exponer margen desde la misma cadena 120d.
- **Problema:** No hay una única “margin real” en el Resumen; margen aparece sobre todo en Drill. Si alguien compara “revenue” del Resumen con “margen” del Drill, está mezclando conceptos. Falta claridad: revenue vs margen y en qué vista es canónico.

#### Drivers (conductores activos)

| Fuente | Definición | Usado en |
|--------|------------|----------|
| **mv_real_trips_monthly.active_drivers_real** | COUNT(DISTINCT conductor_id) por mes desde trips_all | Resumen, /ops/real/monthly |
| **Driver Lifecycle / Supply** | mv_driver_weekly_stats, mv_driver_monthly_stats (desde trips_unified) | Ciclo de vida, Supply |

**Problema:** “Activos” en Resumen = conductores con al menos un viaje en el mes (trips_all). “Activos” en Supply/Lifecycle = lógica semanal/mensual sobre **trips_unified** (trips_all + trips_2026) con work_mode (FT/PT). Son **dos definiciones distintas** y dos fuentes; los números no tienen por qué coincidir.

---

### 2. INCOHERENCIAS ENTRE VISTAS

- **Real Resumen ≠ Real Drill ≠ Real Operativo**
  - **Causa:** Resumen usa **mv_real_trips_monthly** (solo trips_all). Drill y Operativo usan cadena **120d** (trips_all + trips_2026, ventana 120d).
  - **Efecto:** Para un mismo mes, el usuario puede ver un “Real” en Resumen y otro en Drill/Operativo. Se pierde confianza en el dato.

- **Real LOB legacy ≠ Real LOB v2**
  - **Causa:** Legacy: mv_real_trips_by_lob_* (origen en vistas LOB sobre canon; puede ser canon completo o no según migraciones). v2: mv_real_lob_month_v2/week_v2 desde **120d**.
  - **Efecto:** Dos endpoints (/ops/real-lob/monthly vs /ops/real-lob/monthly-v2) y posiblemente dos totales para el mismo periodo. No está claro cuál es “el” Real por LOB.

- **Drill “legacy” (v_real_drill_country_month, etc.) vs Drill PRO (mv_real_drill_dim_agg)**
  - **Causa:** Las vistas v_real_drill_* se apoyan en **v_real_trips_base_drill** (trips_all en 050). Drill PRO usa **mv_real_drill_dim_agg** alimentado por la cadena 120d (real_drill_dim_fact).
  - **Efecto:** Dos fuentes de “drill”: una sin 2026 y otra con 120d. Si la UI mezcla ambas, los números no cuadran.

- **Cierre de periodo**
  - **Causa:** Drill expone estado (CERRADO/ABIERTO/FALTA_DATA/VACIO); Resumen no. El usuario no sabe si el “Real” del Resumen es definitivo o parcial.
  - **Efecto:** Decisiones sobre meses “cerrados” sin saber si realmente lo están en la fuente que ve.

---

### 3. SOBRECARGA COGNITIVA EN UI

- **Tabs que sobran o duplican:**
  - **“Drill y diario (avanzado)”** dentro de Real: ofrece drill por país/periodo/LOB/park y “diario”. El **mismo tipo de decisión** (qué pasó por LOB/parque/periodo) ya está en parte en Operativo (día/hora). Son dos formas de ver “dónde pasó” con fuentes distintas; el usuario no sabe cuál es la referencia.
  - **Plan y validación** con **7 sub-tabs** (Plan Válido, Expansión, Huecos, Fase 2B, Fase 2C, Universo & LOB, Real vs Proyección): demasiados puntos de entrada para “plan vs real” y validación. Varios podrían ser una sola vista con filtros o secciones.

- **Vistas que no aportan decisión clara:**
  - **Real LOB “legacy”** (/ops/real-lob/monthly y /weekly) si la fuente no está alineada con 2026 y con el resto del Real: aporta ruido (“otro número más”) en lugar de una única verdad.
  - **Real vs Proyección** en un sub-tab de Plan: es una decisión de desempeño/forecast; conceptualmente encaja mejor en “Performance” o en un bloque ejecutivo, no escondido en validación.

- **Duplicación de información:**
  - Resumen muestra Plan vs Real; Plan y validación también muestra Plan vs Real (MonthlySplitView, WeeklyPlanVsRealView, plan-vs-real/alerts). El mismo mensaje “¿vamos bien vs plan?” aparece en dos sitios con posibles diferencias de fuente/filtro.

---

### 4. CONCEPTOS CONFUSOS

- **Semanas**
  - **Problema:** En Driver Lifecycle y Supply, **week_start = lunes** (DATE_TRUNC('week', …)). En otras vistas (drill por semana) puede no estar documentado si es lunes o ISO. La UI no explicita “semana operativa (lun–dom)”.
  - **Consecuencia:** Comparar “esta semana” en una pantalla con “semana S6” en otra puede generar malentendidos.
  - **Simplificación:** Una sola definición oficial (“semana = lunes a domingo”, o ISO) y etiquetado/tooltip en todas las vistas: “Semana operativa (lun–dom)” o “ISO week”.

- **Churned**
  - **Problema:** supply_definitions: “Conductores activos la semana N-1 que no registraron viajes esta semana N”. En driver_lifecycle_build: churn_flow_week = activos en W que no aparecen en W+1. Es la misma idea pero “churn” se usa también en Fleet Leakage (progressive_leakage, lost_driver). No hay una sola etiqueta “churn” con definición visible en todas las pantallas.
  - **Consecuencia:** “Churned” en Supply vs “lost_driver” en Leakage vs “churn_flow” en Lifecycle suenan parecido pero no son idénticos; el usuario asume que es lo mismo.
  - **Simplificación:** Glosario único (ej. “Churn = sin viajes en la semana de referencia tras haber estado activo la semana anterior”) y reutilizarlo en Supply, Lifecycle y Leakage con tooltip.

- **Reactivated**
  - **Problema:** Definición: “vuelven a registrar viajes tras al menos una semana inactiva”. En SQL: prev_week_trips = 0 y trips_completed_week > 0. En “migration” se habla de “revival”. “Reactivated” y “revival” se solapan y no están unificados en copy de UI.
  - **Simplificación:** Una sola palabra (p. ej. “Reactivated”) y una definición corta en tooltip; “revival” solo como variante en contexto de migración si se mantiene.

- **Supply**
  - **Problema:** “Supply” es a la vez: (1) número de conductores activos (active_supply), (2) viajes de esos activos (week_supply), (3) módulo con overview/composición/migración/alertas. No está claro si “Supply” es un KPI (“el supply subió”) o la pestaña.
  - **Simplificación:** En UI, distinguir: “Supply (conductores activos)” para el KPI y “Supply” como nombre del módulo; en tooltips aclarar “conductores con al menos un viaje en la semana”.

---

### 5. FEATURES DESINTEGRADAS

- **Behavioral Alerts**
  - **Dónde están hoy:** Sub-tab “Alertas de conducta” dentro de “Conductores en riesgo”. Endpoints /ops/behavior-alerts/* y /controltower/behavior-alerts/* (alias).
  - **Dónde deberían estar:** Son señales de **riesgo de desempeño** (caída de viajes, spike, sudden stop). Deberían estar integradas en un flujo “Riesgo” o “Conductores en riesgo” unificado, y/o un resumen en Resumen/Performance (“X conductores con alerta esta semana”).
  - **Por qué no ayudan a decidir hoy:** El usuario tiene que ir a un tab específico y no ve el impacto en KPIs globales (p. ej. “estas alertas explican Y% de la caída de viajes”). Sin enlace claro a “qué hacer” (Action Engine) o a “fuga” (Leakage), las alertas quedan aisladas.

- **Fleet Leakage**
  - **Dónde están hoy:** Sub-tab “Fuga de flota” en Conductores en riesgo. Fuente: v_fleet_leakage_snapshot (mv_driver_segments_weekly, v_driver_last_trip, etc.).
  - **Dónde deberían estar:** Es **riesgo de pérdida de flota** (watchlist, progressive_leakage, lost_driver). Debería estar en el mismo bloque que Behavioral Alerts y Action Engine, con un resumen tipo “N conductores en riesgo de fuga” visible desde Performance o un único “Riesgo”.
  - **Por qué no ayudan a decidir hoy:** Se ven como lista/tab separada; no hay un KPI de “fuga” en el Resumen ni relación explícita con “churned” de Supply o con alertas de conducta.

- **Segmentación (activos vs solo cancelan)**
  - **Dónde están hoy:** En **mv_real_drill_dim_agg** / real_drill_dim_fact (columnas de segmentación driver). Batch en ejecución; no tocar lógica.
  - **Dónde deberían estar:** En **todas** las vistas donde se muestre Real por LOB/park/periodo: poder filtrar o al menos ver “viajes de conductores activos” vs “solo cancelan”. Hoy la segmentación está solo en Drill PRO; Resumen y Real LOB no la exponen.
  - **Por qué no ayudan a decidir hoy:** La decisión “estamos perdiendo viajes por cancelaciones vs por menos conductores activos” no se puede tomar desde una sola vista; el usuario no ve la segmentación donde más importa (Resumen / Overview).

---

### 6. PROBLEMAS DE ARQUITECTURA

- **Cadenas paralelas de REAL**
  - **Cadena A:** trips_all → mv_real_trips_monthly (sin trips_2026). Usada por Resumen, real_repo, plan_real_split_service.
  - **Cadena B:** v_trips_real_canon_120d → v_real_trip_fact_v2 → mv_real_lob_* (hour/day/week/month v2/v3), mv_real_rollup_day, real_drill_dim_fact → Drill PRO, Real Operativo, Real LOB v2.
  - **Problema:** Dos “Reales” en producción. Mantenimiento doble (definiciones, refrescos, bugs). Riesgo de que correcciones se hagan solo en una cadena.
  - **Recomendación:** Una sola cadena canónica (la que incluya trips_all + trips_2026 y ventana clara). La otra debe alimentar solo legacy o eliminarse cuando el consumo esté migrado.

- **Dependencias innecesarias**
  - **schema_verify / inspect_real_columns** referencian **bi.real_monthly_agg** y **bi.real_daily_enriched** (orders_completed). El SYSTEM_MAP y los servicios de Real usan **ops.***. Si bi.* sigue en uso solo para verificación, es una dependencia oculta y confusa; si no se usa, sobra.
  - **Vistas drill “legacy”** (v_real_drill_country_month, etc.) basadas en v_real_trips_base_drill (trips_all): si la UI principal es Drill PRO (mv_real_drill_dim_agg), mantener dos conjuntos de vistas drill aumenta complejidad sin beneficio claro.

- **Vistas demasiado pesadas**
  - **real_lob_drill_pro_service** documenta que consultas sobre vistas que escanean **v_trips_real_canon** (58M filas, DISTINCT ON) generan GB de temp. El drill debería apoyarse solo en MVs/materializaciones (mv_real_drill_dim_agg, mv_real_rollup_day), no en vistas que recalculan desde viajes.
  - **Refresco de MVs:** Si mv_real_rollup_day y mv_real_drill_dim_agg dependen de cadenas pesadas, los timeouts y ventanas de “en proceso” deben ser explícitos en UI (FASE 5).

---

## FASE 2 — PRIORIZACIÓN

### P0 — Críticos (rompen confianza o consistencia)

| ID | Problema |
|----|----------|
| P0-1 | **Resumen usa mv_real_trips_monthly (solo trips_all).** En 2026, el “Real” del Resumen no incluye trips_2026; Drill y Operativo sí. Los ejecutivos ven un Real distinto al del resto del sistema. |
| P0-2 | **Dos cadenas REAL sin una fuente de verdad única.** Cualquier comparación entre Resumen, Real LOB, Drill y Operativo puede dar números distintos para el mismo periodo. |
| P0-3 | **Falta de indicación de “Real sin 2026” vs “Real con 2026” en UI.** El usuario no sabe qué está viendo; decisiones basadas en dato incompleto. |

### P1 — Importantes (dificultan uso y decisiones)

| ID | Problema |
|----|----------|
| P1-1 | **Real LOB legacy vs v2:** dos fuentes de “Real por LOB”; no está claro cuál es la de referencia. |
| P1-2 | **Drill legacy (v_real_drill_*) vs Drill PRO (mv_real_drill_dim_agg):** dos fuentes de drill; posible mezcla en UI. |
| P1-3 | **Definiciones distintas de “conductores activos”** entre Resumen (mv_real_trips_monthly) y Supply/Lifecycle (trips_unified + weekly/monthly stats). |
| P1-4 | **Alertas, Leakage y Segmentación** en tabs/sub-tabs aislados; no integrados en un flujo “Riesgo” ni en Resumen/Performance. |
| P1-5 | **Estados de data (poblado / en proceso / faltante)** no diferenciados en UI; con batch de segmentación en curso, el usuario no sabe si un número es definitivo. |
| P1-6 | **Revenue vs margen** no unificados: margen canónico solo en Drill; Resumen solo revenue. Riesgo de mezclar conceptos. |

### P2 — Mejoras (UX, claridad)

| ID | Problema |
|----|----------|
| P2-1 | **Demasiados sub-tabs** en Plan y validación (7) y en Conductores en riesgo (4) sin un hilo único. |
| P2-2 | **Conceptos “semana”, “churned”, “reactivated”, “supply”** sin definición única y visible (tooltips/glosario). |
| P2-3 | **“Drill y diario (avanzado)”** vs Operativo: dos formas de ver “dónde pasó” con fuentes distintas; etiquetado confuso. |
| P2-4 | **Real vs Proyección** escondido en Plan y validación; encaja mejor en Performance/Resumen. |
| P2-5 | **Duplicación Resumen vs Plan y validación** para “Plan vs Real”; mismo mensaje en dos sitios. |
| P2-6 | **Dependencia bi.real_* en schema_verify** si no se usa en flujos principales; código muerto o confuso. |

---

## FASE 3 — RECOMENDACIONES CONCRETAS

### P0-1: Resumen sin trips_2026

| Qué hacer | Alimentar el Resumen (KPICards, /ops/real/monthly) desde una fuente que incluya trips_2026, o exponer una sola “ventana” (ej. “Últimos 12 meses” desde la cadena 120d) y usarla solo para Resumen. |
| Qué NO hacer | No cambiar RAW ni el batch de segmentación. No crear una MV nueva sin justificar (se puede reutilizar la cadena 120d o una agregación existente tipo mv_real_lob_month_v3 si el grano encaja). |
| Impacto esperado | Resumen y Drill/Operativo coherentes; misma definición de “Real” en toda la torre. |
| Riesgo | Cambiar la fuente del Resumen puede cambiar los números actuales (subirán si se incorpora 2026). Debe comunicarse y, si hace falta, mantener temporalmente “Real histórico (sin 2026)” como opción. |

### P0-2: Dos cadenas REAL

| Qué hacer | Declarar **una** cadena como canónica (recomendado: la que usa v_trips_real_canon_120d → rollup/day → drill_dim_agg y MVs v2/v3). Migrar Resumen y cualquier consumo de mv_real_trips_monthly a esa cadena. Documentar que mv_real_trips_monthly es legacy y solo para compatibilidad hasta migración. |
| Qué NO hacer | No eliminar MVs de golpe; no tocar el batch de segmentación. No añadir una tercera cadena. |
| Impacto esperado | Una sola fuente de verdad para Real; menos duplicidad de lógica y refrescos. |
| Riesgo | Migración de endpoints y UI; pruebas de regresión en Plan vs Real y en reportes que dependan del “Real” actual. |

### P0-3: Indicación de ventana/universo en UI

| Qué hacer | En Resumen y en cualquier vista que muestre “Real”, mostrar una etiqueta o tooltip: “Real: viajes completados (trips_all + trips_2026)” o “Real: últimos 120 días” según la fuente. Si temporalmente Resumen sigue con trips_all, poner “Real (histórico, sin 2026)”. |
| Qué NO hacer | No cambiar cálculos en esta fase; solo presentación y textos. |
| Impacto esperado | El usuario sabe qué está viendo; se evitan decisiones sobre dato incompleto sin aviso. |
| Riesgo | Bajo. |

---

### P1-1: Real LOB legacy vs v2

| Qué hacer | Decidir cuál es la fuente oficial para “Real por LOB” (recomendado: v2, 120d). En UI, dejar una sola entrada “Real por LOB” que use esa fuente; la otra dejar como “legacy” o retirarla cuando no haya consumidores. |
| Qué NO hacer | No borrar endpoints sin comprobar quién los usa (frontend, reportes, integraciones). |
| Impacto esperado | Un solo número “Real por LOB” por periodo; menos confusión. |
| Riesgo | Si algo externo usa legacy, hay que migrarlo o mantener el endpoint con aviso de deprecación. |

### P1-2: Drill legacy vs Drill PRO

| Qué hacer | Que la UI de “Drill” use **solo** Drill PRO (mv_real_drill_dim_agg, real_drill_dim_fact). Si real_drill_service (v_real_drill_country_month, etc.) sigue en uso, redirigir a la misma fuente o deprecar esas vistas cuando nada las use. |
| Qué NO hacer | No eliminar vistas drill sin comprobar llamadas desde frontend (real_drill_service vs real_lob_drill_pro_service). |
| Impacto esperado | Un solo drill “Real”; coherencia con Operativo y LOB v2. |
| Riesgo | Revisar qué componentes llaman a /ops/real-drill/* vs /ops/real-lob/drill. |

### P1-3: Definición de “conductores activos”

| Qué hacer | Documentar en un único sitio: “Activos (Resumen)” = COUNT(DISTINCT conductor_id) en viajes completados en el mes (fuente X); “Activos (Supply)” = conductores con al menos un viaje en la semana (trips_unified). Añadir en UI tooltips: “Activos (mes)” vs “Activos (semana)” según la vista. |
| Qué NO hacer | No unificar las dos métricas en una sola sin acuerdo de negocio (pueden ser deliberadamente distintas). |
| Impacto esperado | Claridad; el usuario no espera que el “Real” del Resumen coincida con el “Supply” semanal. |
| Riesgo | Bajo. |

### P1-4: Alertas, Leakage, Segmentación desintegradas

| Qué hacer | (1) Un solo bloque “Riesgo” o “Conductores en riesgo” con resumen arriba: “X alertas, Y en riesgo de fuga, Z con segmentación en proceso”. (2) En Resumen o Performance, un KPI o enlace: “N conductores con alerta / en riesgo”. (3) Cuando el batch de segmentación esté estable, exponer segmentación (activo/solo cancelan) en Resumen/Drill como filtro o columna, no solo en Drill PRO. |
| Qué NO hacer | No tocar la lógica de alertas, leakage ni el batch de segmentación; solo organización de UI y enlaces. |
| Impacto esperado | Decisiones de riesgo en un solo flujo; segmentación visible donde se toman decisiones. |
| Riesgo | Cambios de navegación y componentes; asegurar que los endpoints actuales sigan respondiendo. |

### P1-5: Estados de data en UI

| Qué hacer | Usar v_real_data_coverage y estado (CERRADO/ABIERTO/FALTA_DATA/VACIO) y/o flags de “poblado” en MVs. En UI: valor normal si dato poblado; “En proceso” o gris si el batch aún no ha escrito; “Faltante” o warning si se esperaba dato y no hay. |
| Qué NO hacer | No cambiar la lógica de cobertura ni el batch; solo presentación. |
| Impacto esperado | El usuario sabe si un número es definitivo o temporal. |
| Riesgo | Bajo, siempre que la API ya exponga estado o last_refresh; si no, puede hacer falta un endpoint ligero de estado. |

### P1-6: Revenue vs margen

| Qué hacer | En documentación y tooltips: “Revenue real = comision_empresa_asociada (YEGO)”. “Margen” definirlo una vez (ej. mismo que revenue o revenue menos costes) y usarlo solo en vistas donde aplique (Drill). En Resumen no mostrar “margen” si la fuente no lo tiene sin aclarar. |
| Qué NO hacer | No mezclar revenue y margen en la misma tarjeta sin etiquetar. |
| Impacto esperado | Menos mezcla de conceptos al comparar pantallas. |
| Riesgo | Bajo. |

---

### P2 (resumen)

| Problema | Qué hacer | Qué NO hacer |
|----------|-----------|--------------|
| P2-1 Sub-tabs | Reducir o agrupar: p. ej. “Plan vs Real” (una vista con filtros), “Validación y acciones” (2B/2C), “Universo y proyección”. | No eliminar funcionalidad; reorganizar. |
| P2-2 Conceptos | Glosario único (semanas, churn, reactivated, supply) y tooltips en todas las métricas afectadas. | No cambiar definiciones en BD. |
| P2-3 Drill vs Operativo | Una sola entrada “Real” con sub-vistas “Vista día/hora” (Operativo) y “Drill por LOB/parque” (Drill PRO), con la misma fuente. Etiquetar “avanzado” solo si hace falta. | No duplicar datos. |
| P2-4 Real vs Proyección | Mover a Resumen o a un bloque “Performance” visible; no esconder en Plan y validación. | No cambiar datos. |
| P2-5 Duplicación Resumen / Plan | Dejar un solo “Plan vs Real” principal (Resumen); en Plan y validación, enfocarse en alertas, acciones, huecos, accountability. | No quitar KPIs; evitar dos “resúmenes” idénticos. |
| P2-6 bi.real_* | Si no hay consumo de bi.real_monthly_agg / real_daily_enriched, quitar de schema_verify o marcar como legacy. Si se usan, documentar en SYSTEM_MAP. | No borrar tablas bi sin confirmar. |

---

## Resumen ejecutivo

- **P0:** El Resumen ejecutivo usa una fuente de Real que **no incluye trips_2026** y convive con otra cadena (120d) que sí lo hace. Eso **rompe la confianza** en el dato y genera **inconsistencias** entre pantallas. Es crítico unificar fuente o etiquetar claramente el universo.
- **P1:** Varias fuentes duplicadas (Real LOB legacy/v2, Drill legacy/PRO), definiciones distintas de “activos” y features de riesgo (alerts, leakage, segmentación) **desconectadas** de la toma de decisiones. Mejorar con una sola fuente canónica, documentación clara y reorganización de UI.
- **P2:** Sobrecarga de tabs, conceptos sin definir en UI y duplicación de “Plan vs Real” son **mejoras de claridad** sin tocar datos.

**Regla:** No suavizar. Los problemas P0 deben resolverse antes de considerar el sistema “de confianza” para decisiones ejecutivas. Este análisis sirve como base para el rediseño conceptual (4 bloques: PERFORMANCE, DRIVERS, RISK, OPERACIÓN) y para implementar solo cambios de presentación y organización sin romper datos ni el batch en curso.
