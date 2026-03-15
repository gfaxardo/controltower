# REAL — Semántica de periodos abiertos y cerrados

## Definiciones

| Periodo | Descripción | Cerrado/Abierto |
|---------|-------------|-----------------|
| Hoy | current_date | **Parcial** (el día sigue en curso) |
| Ayer | current_date - 1 | **Cerrado** |
| Semana actual | Lunes de la semana actual hasta hoy | **Parcial** |
| Última semana cerrada | Lunes a domingo de la semana pasada | **Cerrado** |
| Mes actual | Día 1 del mes hasta hoy | **Parcial** |
| Último mes cerrado | Mes completo anterior | **Cerrado** |

## Reglas para comparativos

- **WoW (week over week)**: comparar semana actual (parcial) con semana anterior (cerrada) es válido pero debe etiquetarse: "Esta semana (parcial) vs semana anterior (cerrada)".
- **MoM (month over month)**: igual: mes actual (parcial) vs mes anterior (cerrado); la UI debe dejar claro que uno es parcial.
- **No mezclar**: no mostrar un único número que sume "parcial + cerrado" sin indicarlo; no comparar dos periodos parciales de distinta longitud como si fueran equivalentes.

## En la UI

- Donde se muestre semana o mes, indicar con badge o texto: "Cerrado" / "Abierto (parcial)".
- Si una comparación no es válida (ej. mismo día de semana con pocos datos), no mostrar número engañoso; mostrar "—" o "Datos insuficientes".

## En backend

- **real_operational_comparatives_service**: "this_week" es lunes a hoy (parcial); "baseline" son semanas anteriores completas. Ya está diferenciado.
- **get_freshness_global_status**: PARTIAL_EXPECTED = periodo actual abierto, no se considera error.
