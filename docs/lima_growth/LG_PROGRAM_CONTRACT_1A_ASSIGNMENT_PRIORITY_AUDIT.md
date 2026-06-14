# LG_PROGRAM_CONTRACT_1A_ASSIGNMENT_PRIORITY_AUDIT

**Phase:** LG-PROGRAM-CONTRACT-1A — Program Assignment Priority Audit  
**Motor:** Control Foundation  
**Generated:** 2026-06-13  
**Veredict:** `C — CONTRATO AMBIGUO. Two priority systems in conflict. Requires product decision.`

---

## PRE-CHECK

| Question | Answer |
|----------|--------|
| 1. Motor | Control Foundation |
| 2. Fase | LG-PROGRAM-CONTRACT-1A (audit only) |
| 3. Tablas | `program_eligibility_daily` (read), `driver_explorer_fact` (read) |
| 4. Writers | NONE modified |
| 5. Freshness | NONE affected |
| 6. Riesgos | **MEDIUM** — 9,125 drivers affected if bug confirmed |
| 7. Rollback | N/A — audit only |

---

## 1. PRIORITY CONTRACT DISCOVERY

### Definitive Evidence: `priority = 1` = MOST IMPORTANT

**Source:** `yego_lima_priority_registry.py:10`
```
El número menor = mayor prioridad (1 = primero en recibir capacidad).
```

### Program-Level Priority (capacity allocation)

| Program | Rank | Meaning |
|---------|------|---------|
| `PROGRAM_HIGH_VALUE_RECOVERY` | **1** | Highest priority — gets capacity first |
| `PROGRAM_CHURN_PREVENTION` | **2** | Second priority |
| `PROGRAM_14_90` | **3** | Third priority |
| `PROGRAM_ACTIVE_GROWTH` | **4** | Lowest priority |

### Intra-Program Priority (eligibility sub-priority)

| Program | Priority Range | Meaning |
|---------|---------------|---------|
| `PROGRAM_14_90` | **1-4** | EARLY_LIFE=1, REACTIVATED=2, ACTIVATED=3 |
| `PROGRAM_ACTIVE_GROWTH` | **10-50** | recoverable=10, NO_TRIPS=20, LOW=30, MEDIUM=40 |
| `PROGRAM_CHURN_PREVENTION` | **100-130** | CHURN_RISK=100, churn_risk_flag=110, declining=120 |

### The DISTINCT ON Clause

```sql
-- In build_driver_explorer_fact(), line 309
ORDER BY ds.driver_profile_id, pr.priority NULLS LAST
```

This picks the **lowest** `pr.priority` value per driver. Due to the intra-program ranges (14/90=1-4 < AG=10-50 < CHURN=100-130), the selection order is:

```
ASC winner: 14/90 → ACTIVE_GROWTH → CHURN_PREVENTION → NULL
```

---

## 2. THE CONTRADICTION

### Two priority systems, opposite results

| System | What It Controls | Priority Order | Lowest Priority Wins? |
|--------|-----------------|---------------|----------------------|
| **Program Registry** | Capacity allocation (who gets campaign slots first) | HVR > CHURN > 14/90 > AG | YES — HVR(1) gets capacity first |
| **Eligibility sub-priority** | DISTINCT ON selection (which program a driver gets in Explorer) | 14/90(1-4) > AG(10-50) > CHURN(100-130) | YES — 14/90(1) wins over CHURN(100) |

**Result:** A driver qualifying for both ACTIVE_GROWTH and CHURN_PREVENTION gets ACTIVE_GROWTH in the Explorer (because AG priority=10-50 < CHURN priority=100-130). But the capacity allocator would give CHURN_PREVENTION more capacity (because program rank 2 < 4).

**The same driver is in different programs depending on which system you ask.**

---

## 3. MULTI-PROGRAM DISTRIBUTION

| Metric | Value |
|--------|-------|
| Total rows in eligibility | 28,128 |
| Distinct drivers | 18,040 |
| Drivers with 1 program | 8,915 (49.4%) |
| Drivers with 2 programs | **8,162 (45.2%)** |
| Drivers with 3 programs | 963 (5.3%) |
| Avg programs per driver | 1.56 |

**Nearly half of all drivers (45.2%) qualify for 2+ programs.** This is not an edge case — it's the norm.

---

## 4. ASC vs DESC SIMULATION

### Full Simulation (all 9,125 multi-program drivers)

| Metric | ASC (current) | DESC (would be) |
|--------|--------------|-----------------|
| CHURN_PREVENTION | 0 | **7,457** (+7,457) |
| ACTIVE_GROWTH | 6,476 | **1,668** (-4,808) |
| 14_90 | 2,649 | 0 (-2,649) |
| **Would change** | — | **9,125 (100%)** |

### Top Transitions

| Transition | Drivers | % of Multi |
|-----------|---------|-----------|
| ACTIVE_GROWTH → CHURN_PREVENTION | **6,476** | 71.0% |
| PROGRAM_14_90 → ACTIVE_GROWTH | 1,668 | 18.3% |
| PROGRAM_14_90 → CHURN_PREVENTION | 981 | 10.7% |

---

## 5. CONCRETE EXAMPLES

### Case 1: Driver in ACTIVE_GROWTH who should be in CHURN_PREVENTION

| Attribute | Value |
|-----------|-------|
| Driver | `ff3ba172fc1042b0b9a1` |
| Eligible for | ACTIVE_GROWTH (priority=30), CHURN_PREVENTION (priority=100) |
| Current (ASC) | **ACTIVE_GROWTH** (priority 30 < 100) |
| Would be (DESC) | **CHURN_PREVENTION** |
| trips_7d | 1 |
| churn_risk_flag | **TRUE** |
| declining_flag | FALSE |

**This driver has churn_risk_flag=TRUE but is in ACTIVE_GROWTH.** They do 1 trip/week. The churn risk is real. They should be in CHURN_PREVENTION.

### Case 2: Driver in 14_90 who should be in CHURN_PREVENTION

| Attribute | Value |
|-----------|-------|
| Driver | `0ac93ee12d76431886b6` |
| Eligible for | 14_90 (priority=4), ACTIVE_GROWTH (priority=20), **CHURN_PREVENTION (priority=110)** |
| Current (ASC) | **14_90** (priority 4 < 110) |
| Would be (DESC) | **CHURN_PREVENTION** |
| trips_7d | 12 |
| churn_risk_flag | **TRUE** |

**This new driver (14_90) already shows churn_risk_flag=TRUE.** They should be in CHURN_PREVENTION to prevent early churn.

### Case 3: Driver in 14_90 who should be in ACTIVE_GROWTH

| Attribute | Value |
|-----------|-------|
| Driver | `41de440994ba40fca08c` |
| Eligible for | 14_90 (priority=4), ACTIVE_GROWTH (priority=30) |
| Current (ASC) | **14_90** |
| Would be (DESC) | **ACTIVE_GROWTH** |
| trips_7d | 3 |

**This new driver has low activity but no risk flags.** ACTIVE_GROWTH (below target) might be more appropriate than 14_90 (new driver).

---

## 6. UI VALIDATION TARGETS

| # | Driver ID | Current Program | Should Be | trips_7d | churn_risk | How to Find |
|---|-----------|----------------|-----------|---------|-----------|-------------|
| 1 | `ff3ba172fc10` | ACTIVE_GROWTH | CHURN_PREVENTION | 1 | TRUE | Search by ID, check program column |
| 2 | `0ac93ee12d76` | 14_90 | CHURN_PREVENTION | 12 | TRUE | Search by ID, check RNA band |
| 3 | `c22dedd72f6a` | ACTIVE_GROWTH | CHURN_PREVENTION | 3 | FALSE* | declining=TRUE, should be in CHURN |
| 4 | `469863118748` | ACTIVE_GROWTH | CHURN_PREVENTION | 1 | TRUE | Very low activity + risk flag |
| 5 | `41de440994ba` | 14_90 | ACTIVE_GROWTH | 3 | FALSE | New driver, low activity, no risk |

---

## 7. ROOT CAUSE

The `priority` column in `program_eligibility_daily` was designed for **intra-program ranking** (who's most urgent within a program). The ranges (14/90=1-4, AG=10-50, CHURN=100-130) ensure drivers sort correctly WITHIN their single program.

The DISTINCT ON in `build_driver_explorer_fact()` uses this column for **cross-program selection** (which program wins when a driver qualifies for multiple). This is an OFF-LABEL USE of the priority column. The ranges produce the wrong cross-program ordering.

### The Correct Cross-Program Order (per Program Registry)

```
HVR (rank 1) → CHURN_PREVENTION (rank 2) → 14_90 (rank 3) → ACTIVE_GROWTH (rank 4)
```

### The Current Cross-Program Order (from DISTINCT ON)

```
14_90 (sub 1-4) → ACTIVE_GROWTH (sub 10-50) → CHURN_PREVENTION (sub 100-130)
```

**These are opposites.** CHURN_PREVENTION should be the highest-priority program after HVR. Instead it's the lowest.

---

## 8. FIX OPTIONS (for LG-PROGRAM-CONTRACT-1B)

### Option A: Fix DISTINCT ON to use program-level rank

```sql
ORDER BY ds.driver_profile_id,
    CASE pr.program_code
        WHEN 'PROGRAM_HIGH_VALUE_RECOVERY' THEN 1
        WHEN 'PROGRAM_CHURN_PREVENTION' THEN 2
        WHEN 'PROGRAM_14_90' THEN 3
        WHEN 'PROGRAM_ACTIVE_GROWTH' THEN 4
        ELSE 999
    END
```

**Impact:** 9,125 drivers change program. CHURN_PREVENTION goes from 317 to ~7,500. ACTIVE_GROWTH drops from 15,054 to ~9,000.

### Option B: Re-range intra-program priorities

Set 14/90=100-104, AG=200-250, CHURN=300-330. Then ASC still gives 14/90 → AG → CHURN. Current behavior preserved. But this is a semantic hack.

### Option C: Add a separate `program_rank` column

New column in eligibility for cross-program selection. Intra-program `priority` stays as-is for sorting within program.

### Option D: Product decision — what should win?

If the product intent is "new drivers first, then active, then churn" → current behavior is correct. If intent is "highest value/risk first" → need Option A.

---

## VEREDICT

### C — CONTRATO AMBIGUO

**Evidencia:**

1. **Two priority systems exist and they produce opposite results.**
2. The program registry says CHURN_PREVENTION > ACTIVE_GROWTH (rank 2 vs 4).
3. The DISTINCT ON produces ACTIVE_GROWTH > CHURN_PREVENTION (sub-priority 10-50 vs 100-130).
4. **9,125 drivers (100% of multi-program drivers) would change program if the registry order were used.**
5. **6,476 drivers in ACTIVE_GROWTH qualify for CHURN_PREVENTION but don't get it.**
6. The `priority` column was designed for intra-program ranking, not cross-program selection. The DISTINCT ON uses it off-label.

**This is NOT a simple bug (B). The intra-program priority ranges (1-4, 10-50, 100-130) were DELIBERATELY spaced to make 14/90 win over AG over CHURN in ASC order. This was a design choice. But it contradicts the program-level registry.**

### Backlog

| Ticket | Description | Phase |
|--------|-------------|-------|
| **LG-PROGRAM-CONTRACT-1B** | Resolve priority contract ambiguity. Options: A (fix DISTINCT ON to program rank), C (add program_rank column), D (product decision). Requires product owner decision on which program should win for multi-eligible drivers. | Next |
