# AUDITORIA FASE 1F-1 — PAYMENT DETAILS SOURCE

Fecha: 2026-05-20 08:15

## Columnas

- `id` (integer)
- `driver_id` (character varying)
- `park_id` (character varying)
- `bank_name` (character varying)
- `account_number` (character varying)
- `account_type` (character varying)
- `recipient_name` (character varying)
- `document_type` (character varying)
- `document_number` (character varying)
- `created_at` (timestamp without time zone)
- `updated_at` (timestamp without time zone)

## Estadisticas

- Total rows: 0
- Distinct driver_id: 0
- Distinct account_number: 0
- Null/empty account_number: 0
- Null/empty bank_name: 0
- Null/empty driver_id: 0

## Clusters bancarios

- Cuentas compartidas por 2+ drivers: 0
- Cuentas compartidas por 3+ drivers: 0
- Cuentas compartidas por 5+ drivers: 0
- Total drivers en clusters: 0

## Top 10 clusters (masked)

| Bank | Masked Account | Drivers |
|---|---|---|

## Capacidades

- Columnas minimas (driver_id, bank_name, account_number): SI
- Bank source listo para wiring: SI

## Decision

**NO-GO** — columnas minimas=OK, clusters_2=0