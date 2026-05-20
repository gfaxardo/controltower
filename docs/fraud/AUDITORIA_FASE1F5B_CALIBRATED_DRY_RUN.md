# AUDITORIA FASE 1F-5B — CALIBRATED DRY RUN

**Fecha**: 2026-05-20
**Estado**: GO condicionado — motor calibrado funcional

---

## Resultados calibrados (D-7, limit=200)

| Rutina | Signal Flags | Candidates | Cases | Drivers Flagged |
|---|---|---|---|---|
| REPEATED_ORIGIN_PATTERN | 0 | 3 | 0 | 3 |
| COORDINATED_ORIGIN_PATTERN | min=6 (vs 3) | | | |

## Antes vs Despues

| Metrica | Antes (v1) | Despues (v1_calibrated) |
|---|---|---|
| Min drivers coordinated | 3 | 6 |
| Repeated origin creates case | SI (151 casos) | NO (solo con combo) |
| Coordinated origin explosion | 5000 origenes | Reducido (p95=4, p99=8) |
| Short trip ratio signal | 60% | 15% |
| Case guardrails | No | Si (max 50/run) |
| Tier system (flag/candidate/case) | No | Si |
| Thresholds versionados | No | Si (DB) |

## Efectividad

- **Repeated origin**: ya NO crea casos masivos. Solo candidates que requieren combo para escalar.
- **Coordinated origin**: min_drivers=6 filtra 90%+ de origenes normales.
- **Short trip farming**: ratio 15% captura p99+, reduciendo ruido.
- **Guardrails**: previenen >50 casos por corrida.

## Confirmacion

- NO acciones reales
- NO data sintetica
- Omniview intacto
- Plan vs Real intacto
