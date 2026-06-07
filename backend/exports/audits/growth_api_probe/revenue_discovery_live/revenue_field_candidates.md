# Yango Revenue Field Candidates — Analysis

**Generated:** 2026-06-05T00:18:46.312055-05:00
**Park ID (masked):** 08e20910***
**Date Range:** 2026-06-01 -&gt; 2026-06-03
**Dry Run:** False

---

## Field Candidates

### 1. `transactions[category_name=Card payment].amount`  —  **UNKNOWN**
- **Endpoint:** POST /v2/parks/transactions/list
- **Data type:** string (fixed-point)
- **Grain:** transaction
- **Confidence:** MEDIUM
- **Currency distribution:** {'PEN': 50}
- **Range:** 30.60 -&gt; 30.60 (avg: 30.60)
- **Can be negative:** False
- **Coverage:** 2.0% of records
- **Has event_at:** 1 transactions
- **Has order_id:** 1 transactions

### 2. `transactions[category_name=Cash].amount`  —  **UNKNOWN**
- **Endpoint:** POST /v2/parks/transactions/list
- **Data type:** string (fixed-point)
- **Grain:** transaction
- **Confidence:** MEDIUM
- **Currency distribution:** {'PEN': 50}
- **Range:** 7.50 -&gt; 23.90 (avg: 11.37)
- **Can be negative:** False
- **Coverage:** 22.0% of records
- **Has event_at:** 11 transactions
- **Has order_id:** 11 transactions

### 3. `transactions[category_name=Partner fee for trip].amount`  —  **UNKNOWN**
- **Endpoint:** POST /v2/parks/transactions/list
- **Data type:** string (fixed-point)
- **Grain:** transaction
- **Confidence:** MEDIUM
- **Currency distribution:** {'PEN': 50}
- **Range:** -0.92 -&gt; -0.23 (avg: -0.39)
- **Can be negative:** True
- **Coverage:** 22.0% of records
- **Has event_at:** 11 transactions
- **Has order_id:** 11 transactions

### 4. `transactions[category_name=Promo code discount compensation].amount`  —  **UNKNOWN**
- **Endpoint:** POST /v2/parks/transactions/list
- **Data type:** string (fixed-point)
- **Grain:** transaction
- **Confidence:** MEDIUM
- **Currency distribution:** {'PEN': 50}
- **Range:** 0.20 -&gt; 0.20 (avg: 0.20)
- **Can be negative:** False
- **Coverage:** 2.0% of records
- **Has event_at:** 1 transactions
- **Has order_id:** 1 transactions

### 5. `transactions[category_name=Service fee for My Destinations and My Neighborhood modes].amount`  —  **UNKNOWN**
- **Endpoint:** POST /v2/parks/transactions/list
- **Data type:** string (fixed-point)
- **Grain:** transaction
- **Confidence:** MEDIUM
- **Currency distribution:** {'PEN': 50}
- **Range:** -0.98 -&gt; -0.36 (avg: -0.57)
- **Can be negative:** True
- **Coverage:** 6.0% of records
- **Has event_at:** 3 transactions
- **Has order_id:** 3 transactions

### 6. `transactions[category_name=Service fee for trip].amount`  —  **UNKNOWN**
- **Endpoint:** POST /v2/parks/transactions/list
- **Data type:** string (fixed-point)
- **Grain:** transaction
- **Confidence:** MEDIUM
- **Currency distribution:** {'PEN': 50}
- **Range:** -3.11 -&gt; -0.57 (avg: -1.28)
- **Can be negative:** True
- **Coverage:** 24.0% of records
- **Has event_at:** 12 transactions
- **Has order_id:** 12 transactions

### 7. `transactions[category_name=Service fee, VAT].amount`  —  **UNKNOWN**
- **Endpoint:** POST /v2/parks/transactions/list
- **Data type:** string (fixed-point)
- **Grain:** transaction
- **Confidence:** MEDIUM
- **Currency distribution:** {'PEN': 50}
- **Range:** -0.56 -&gt; -0.10 (avg: -0.23)
- **Can be negative:** True
- **Coverage:** 22.0% of records
- **Has event_at:** 11 transactions
- **Has order_id:** 11 transactions
