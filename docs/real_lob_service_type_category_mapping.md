# Categorías de service_type – Mapping final

## GRUPO A — Aceptados como servicio legítimo (directos)

| Raw upstream | Normalizado | Trips |
|---|---|---|
| economico | economico | 16.5M |
| moto | moto | 3.3M |
| confort | confort | 1.2M |
| standard | standard | 766k |
| minivan | minivan | 114k |
| start | start | 91k |
| cargo | cargo | 85k |
| premier | premier | 14k |
| express | express | 13k |
| xl | xl | — |

## GRUPO B — Aceptados, normalizados a canónica

| Raw upstream | Normalizado | Regla |
|---|---|---|
| Económico | economico | unaccent + lower |
| mensajería | mensajeria | unaccent |
| confort+ | confort_plus | + → _plus |
| tuk-tuk / Tuk-Tuk / tuk tuk | tuk_tuk | guiones/espacios → _ |
| Exprés | expres | unaccent |
| Envíos | envios | unaccent |
| Taxi Moto | taxi_moto | espacio → _, lower |
| Confort | confort | lower |
| Standard | standard | lower |
| Premier | premier | lower |

## GRUPO C — Aceptados como servicio desconocido pero legítimo

Cualquier valor que tras normalización cumpla `^[a-z0-9_]+$` y ≤30 chars sin coma y ≤3 palabras queda con su nombre normalizado (ej. nuevos tipos del upstream).

## GRUPO D — Rechazados → UNCLASSIFIED

| Raw | Razón |
|---|---|
| focos led para auto, moto | coma |
| -), calle enrique palacios, 1072, ... | coma + basura textual |
| servicio especial para reparto urbano | >3 palabras |
| promoción taxi ejecutivo | >3 palabras |
| (vacío/NULL) | vacío |

## Mapping LOB (canon.map_real_tipo_servicio_to_lob_group)

| tipo_servicio_norm | lob_group |
|---|---|
| economico, confort, confort_plus, standard, start, minivan, premier, xl, economy | auto taxi |
| moto, taxi_moto | taxi moto |
| tuk_tuk | tuk tuk |
| cargo, express, expres, envios, mensajeria | delivery |

Tipos no mapeados → UNCLASSIFIED en LOB (1.27%).
