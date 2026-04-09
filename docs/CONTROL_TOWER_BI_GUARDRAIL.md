# Control Tower BI Guardrail

## Fuente oficial

Para runtime operativo de Control Tower, las fuentes oficiales son:

- `trips_2025`
- `trips_2026`
- `ops.*`
- dimensiones canónicas vigentes

`bi.real_monthly_agg` es legacy y no puede usarse como source of truth operativo.

## Política

- Se permiten referencias a `bi.*` solo si están justificadas en `backend/config/bi_guardrail_allowlist.json`.
- Casos típicos permitidos:
  - metadata activa de ingesta (`bi.ingestion_status`)
  - stubs legacy explícitos y documentados
  - scripts offline de exploración/diagnóstico fuera del runtime
- Cualquier referencia nueva a `bi.*` fuera de la allowlist debe fallar.

## Cómo validar

Comando directo:

```bash
python backend/scripts/check_bi_guardrail.py
```

Como test:

```bash
python -m pytest backend/tests/test_bi_guardrail.py -q
```

## Cómo aprobar una excepción legítima

1. justificar por qué no puede ir a `ops.*`
2. añadir la referencia exacta a `backend/config/bi_guardrail_allowlist.json`
3. documentar si es `metadata activa`, `legacy tolerada` o `script offline`
4. mantener el conteo exacto para que el guardrail detecte nuevos usos no previstos
