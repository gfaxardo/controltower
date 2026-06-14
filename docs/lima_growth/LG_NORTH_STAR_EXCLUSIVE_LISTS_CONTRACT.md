# LG-NORTH-1A — Lima Growth North Star: Exclusive Dynamic Lists Contract

**Date:** 2026-06-13
**Status:** DEFINITIVE
**Purpose:** Define the final product of Lima Growth Machine and govern all future actions.

---

## 1. Executive Definition

**The final product of Lima Growth Machine is not the dashboard.**

The final product is a **daily refreshed system of mutually exclusive operational driver lists**, exportable to Control Loop, actionable by humans or mass channels, and measurable by daily/weekly impact.

- Dashboard = visibility, not the product.
- Program UI = visibility, not the product.
- Metrics = control, not the product.
- The product = operational assignment: who to work today, why, with what objective, and how impact is measured.

## 2. Core Principles

| # | Principle |
|---|-----------|
| 1 | Every driver must belong to **at most one** active operational list per day. |
| 2 | Eligibility may be multi-signal; final operational assignment must be **exclusive**. |
| 3 | Lists must be **refreshed daily** with recent operational behavior. |
| 4 | Every list must have: objective, entry criteria, exit criteria, priority order, owner/use case, export target, measurement target. |
| 5 | Lists must be **exportable** to Control Loop or equivalent CRM workflow. |
| 6 | Actions taken must be **tracked** by channel/person/outcome. |
| 7 | Impact must be **measured** daily and weekly per list. |

## 3. MVP Definition

The Minimum Viable Product for production cutover:

1. Daily exclusive list generation — one driver = one operational universe.
2. Every list has: objective, entry/exit criteria, priority, measurement target.
3. Export to Control Loop.
4. Action capture by channel/person.
5. Daily impact measurement.
6. Weekly impact aggregation.

## 4. Exclusive Operational Universes (Hierarchical)

### 4.1 New / Reactivated Activation — Day 0 to 14

| Dimension | Value |
|-----------|-------|
| Goal | Reach 50 trips within first 14 days |
| Entry | Newly activated or reactivated driver; operational age 0-14 days; below 50 trips in activation window |
| Exit | Reaches 50 trips OR age > 14 days |
| Treatment | Activation push, onboarding, first habit formation |
| Priority | Highest — early intervention critical |

### 4.2 Ramp-Up — Day 15 to 45

| Dimension | Value |
|-----------|-------|
| Goal | Reach or sustain 100 trips per week |
| Entry | Operational age 15-45 days; not meeting 100 trips/week; not inactive/recovery |
| Exit | Reaches 100 trips/week OR age > 45 days OR becomes inactive/recovery |
| Treatment | Productivity ramp-up |

### 4.3 Consolidation — Day 46 to 90

| Dimension | Value |
|-----------|-------|
| Goal | Reach or sustain 100 trips per week |
| Entry | Operational age 46-90 days; not meeting 100 trips/week; not inactive/recovery |
| Exit | Reaches 100 trips/week OR age > 90 days OR becomes inactive/recovery |
| Treatment | Habit consolidation, productivity stabilization |

### 4.4 Active Growth — 90+ Days (Active Drivers)

| Dimension | Value |
|-----------|-------|
| Goal | Move drivers at least one productivity band upward |
| Entry | Active driver; not in 0-14/15-45/46-90 windows; not recovery; not cemetery; below desired productivity band |
| Productivity Bands | 1-10, 11-20, 21-30, 31-40, 41-50, 51-75, 76-99, 100+ trips/week |
| Band Source | **Current weekly_trips** (not historical best_week_12w). `best_week_12w` reserved for value tier and recovery value classification. |
| Exit | Moves up target band OR reaches 100+ trips/week OR becomes recovery |
| Treatment | Targeted growth per band |

### 4.5 Recovery — Recently Inactive

| Dimension | Value |
|-----------|-------|
| Goal | Recover drivers who recently became inactive |
| Entry | Recently inactive/deactivated/churn-risk; not in active growth; not in new/ramp/consolidation |
| Sub-universes | High Value Recovery, Low Value Recovery |
| Exit | Reactivates OR ages into cemetery |
| Treatment | Reactivation, obstacle removal, personalized or mass recovery |

### 4.6 Cemetery — Long Churned / Archived

| Dimension | Value |
|-----------|-------|
| Goal | Separate long-churned drivers from active/recovery operations |
| Entry | Long inactive, archived, far beyond recovery window |
| Exit | Reactivates → enters New/Reactivated Activation |
| Treatment | Low-frequency campaigns, reactivation experiments, archive management |

## 5. Mutual Exclusivity Rule

The final operational assignment must be mutually exclusive per day:

- Priority order resolves collisions.
- A driver cannot appear in two active operational worklists on the same day.
- If a driver qualifies for multiple signals, final assignment must choose ONE universe.
- The highest-priority universe wins (activation > recovery > growth > consolidation > ramp-up).

## 6. Daily Refresh Rule

Lists must be refreshed every day with recent operational behavior:

- Current universe assignment
- Entry/exit status changes
- Productivity band updates
- Recovery/reactivation detection
- Export eligibility
- Measurement baseline recalculation

## 7. Control Loop Export Rule

Each list must export or synchronize to Control Loop. Minimum export contract:

| Field | Description |
|-------|-------------|
| `driver_profile_id` | Driver identifier |
| `assigned_universe` | Which universe they belong to |
| `program_code` | Operational program/list code |
| `objective` | What the action aims to achieve |
| `reason` | Why they are in this list |
| `priority` | Order within the worklist |
| `recommended_action` | Suggested action category |
| `target_metric` | What to measure |
| `baseline_metric` | Starting value for comparison |
| `generated_date` | When the list was generated |
| `owner/channel` | Who handles this (if pre-assigned) |

## 8. Action Measurement Rule

The system must measure actions taken on lists:

- Who contacted the driver
- Channel used
- Date/time of contact
- Outcome/disposition
- Next state after contact
- Trips before contact (baseline)
- Trips after contact (7d, 30d windows)
- Daily impact (completed_orders_day, supply_hours_day)
- Weekly impact (week-over-week change)

Not implementing in this phase. Declared as north star requirement.

## 9. What Is Accessory

The following are secondary to the north star:

- Dashboards without actionable lists underneath
- Charts not tied to worklists
- Health redesign not blocking list generation
- AI suggestions before deterministic lists exist
- New campaigns before exclusive list assignment
- Advanced explanations before list correctness
- Program Registry V3 full redesign before V1 cutover

## 10. Governance Rule — North Star Test

Every future Growth Machine task must answer:

| # | Question |
|---|----------|
| 1 | Does this improve exclusive dynamic operational lists? |
| 2 | Does this improve daily refresh correctness? |
| 3 | Does this improve Control Loop export? |
| 4 | Does this improve action tracking? |
| 5 | Does this improve daily/weekly impact measurement? |
| 6 | If NO to all, why is this being done now? |

**Rule:** If the answer is NO to all 5 questions → document/backlog, do NOT implement.

## 11. Immediate Cutover Implication

The immediate production cutover must prioritize **Exclusive Dynamic Lists V1** over further dashboard polish.

Next implementation phase: **LG-PROG-EXCL-1A — Exclusive Dynamic Lists Contract Freeze + Dry Run.**

## 12. Deferred Future Enhancements

Maintain deferred and blocked:

- Full Lifecycle State Machine
- Program Registry V3 (beyond V1 cutover scope)
- Advanced Top Performer Program
- AI Suggestions / AI Copilot
- Automated Campaigns
- Full Control Loop V2
- Commission Attribution
- Advanced Impact Modeling
- Diagnostic Engine 2A.3

## 13. Verdict

### **LG_NORTH_1A_CERTIFIED**

---

*The North Star is exclusive dynamic operational lists. The dashboard is navigation, not the destination.*
