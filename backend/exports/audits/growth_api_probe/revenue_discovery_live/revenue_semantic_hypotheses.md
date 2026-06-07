# Yango Revenue Field — Semantic Hypotheses

**Generated:** 2026-06-05T00:18:46.312114-05:00

---

## Overview

This document captures hypotheses about what each revenue-relevant field semantically represents.
Each hypothesis is classified by confidence level and includes reasoning.

---

## UNKNOWN

Unclassified — needs more investigation.

### `transactions[category_name=Card payment].amount`
- **Source endpoint:** POST /v2/parks/transactions/list
- **Confidence:** MEDIUM
- **Grain:** transaction
- **Value range:** 30.60 -&gt; 30.60

### `transactions[category_name=Cash].amount`
- **Source endpoint:** POST /v2/parks/transactions/list
- **Confidence:** MEDIUM
- **Grain:** transaction
- **Value range:** 7.50 -&gt; 23.90

### `transactions[category_name=Partner fee for trip].amount`
- **Source endpoint:** POST /v2/parks/transactions/list
- **Confidence:** MEDIUM
- **Grain:** transaction
- **Value range:** -0.92 -&gt; -0.23

### `transactions[category_name=Promo code discount compensation].amount`
- **Source endpoint:** POST /v2/parks/transactions/list
- **Confidence:** MEDIUM
- **Grain:** transaction
- **Value range:** 0.20 -&gt; 0.20

### `transactions[category_name=Service fee for My Destinations and My Neighborhood modes].amount`
- **Source endpoint:** POST /v2/parks/transactions/list
- **Confidence:** MEDIUM
- **Grain:** transaction
- **Value range:** -0.98 -&gt; -0.36

### `transactions[category_name=Service fee for trip].amount`
- **Source endpoint:** POST /v2/parks/transactions/list
- **Confidence:** MEDIUM
- **Grain:** transaction
- **Value range:** -3.11 -&gt; -0.57

### `transactions[category_name=Service fee, VAT].amount`
- **Source endpoint:** POST /v2/parks/transactions/list
- **Confidence:** MEDIUM
- **Grain:** transaction
- **Value range:** -0.56 -&gt; -0.10

---

## Key Discovery: Transaction Categories

Transaction categories with `group_id` reveal revenue semantics directly:

| Category | group_id | Semantic |
|---|---|---|
| `platform_card` | (category group) | **GMV_CANDIDATE** |
| `platform_corporate` | (category group) | **GMV_CANDIDATE** |
| `partner_rides` | (category group) | **REVENUE_YEGO_CANDIDATE** |
| `platform_fees` | (category group) | **COMMISSION_CANDIDATE** |
| `partner_fees` | (category group) | **FEE_CANDIDATE** |
| `platform_bonus` | (category group) | **BONUS_OR_ADJUSTMENT** |
| `platform_tip` | (category group) | **BONUS_OR_ADJUSTMENT** |
| `cash_collected` | (category group) | **GMV_CANDIDATE** |
| `platform_promotion` | (category group) | **BONUS_OR_ADJUSTMENT** |
| `partner_other` | (category group) | **REVENUE_YEGO_CANDIDATE** |
| `platform_other` | (category group) | **COMMISSION_CANDIDATE** |

---

## Key Discovery: Order `price` Field

Per official API docs (https://fleet.yango.com/docs/api/en/):
- `price` in orders is a **STRING** type (fixed-point like `"12345.1434"`), NOT an object.
- It does NOT have a `.final_cost` sub-property.
- Any code treating it as `order["price"]["final_cost"]` is INCORRECT per docs.
