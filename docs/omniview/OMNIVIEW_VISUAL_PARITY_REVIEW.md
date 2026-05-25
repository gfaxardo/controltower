# OMNIVIEW VISUAL PARITY REVIEW vs YANGO LOYALTY

**Date**: 2026-05-25
**Method**: Code-level structural comparison

---

## 1. WHICH TRANSMITS MORE AUTHORITY?

**Loyalty** — stronger entry experience:
- Bold title "Yango Loyalty Tracker" (16px, weight: 700)
- Hero stats with gradient background and large numbers
- Category cards (ORO/PLATA/BRONCE) with colored borders and backgrounds

**Omniview** — weaker entry:
- No view title (matrix IS the view)
- Command header is a 22px meta bar (11px font)
- No hero section

**Gap**: Loyalty has a clear "command identity" established in the first 100px. Omniview's first pixel is a thin meta bar.

---

## 2. WHICH FEELS CLEARER?

**Loyalty** — 3 clear zones: header → executive summary → city ranking
**Omniview** — 3 zones: command header → filter controls → matrix

Both have 3 zones. But:
- Loyalty's zones have clear visual weight differences (header bold, executive summary prominent, ranking collapsible)
- Omniview's zones compete visually (command header card = filter controls card = same border-radius/background/shadow)

**Gap**: Omniview filter controls have the same visual weight as the command header. Hierarchy is flat.

---

## 3. WHICH FEELS MORE FOCUSED?

**Loyalty** — Tabbed: Resumen / Detalle KPI / Configurar Metas. Focus is explicit.
**Omniview** — Evolution vs Projection toggle (implicit), KPI focus mode (implicit). Grain toggle (implicit). Multiple "focus modes" competing.

**Gap**: Omniview has 3-4 implicit focus modes (grain, KPI, view mode, compact) but none feels dominant.

---

## 4. WHICH HAS BETTER HIERARCHY?

**Loyalty** — Clear: Title > Executive Summary > KPIs > City Detail
**Omniview** — Flat: Meta bar = Filter card = Matrix table (similar visual weight)

**Gap**: Omniview lacks vertical visual hierarchy between command header and filter controls.

---

## 5. DOES OMNIVIEW STILL FEEL LIKE RAW MATRIX?

**Partially yes** — the matrix IS the dominant element. The command header helps but it's too thin to overcome matrix dominance. The filter card competes for attention.

---

## 6. DOES COMMAND HEADER HELP OR HURT?

**Helps** — adds context that didn't exist before.
**But insufficient** — 22px height with 11px font doesn't feel like a "command center" header. It feels like a status notification bar.

---

## 7. LOYALTY PATTERNS STILL MISSING IN OMNIVIEW

| Pattern | Present in Loyalty | Present in Omniview |
|---------|-------------------|-------------------|
| Bold view title | YES | NO |
| Period + progress in subtitle | YES (subtitle) | Yes (meta bar, but very thin) |
| Executive summary with narrative | YES | Partial (MatrixExecutiveBanner, conditional) |
| Hero stats with gradient | YES | NO (matrix IS the stats) |
| Category/concept pillars | YES (ORO/PLATA/BRONCE) | NO |
| Visual identity colors | YES (amber/silver/bronze) | NO (matrix uses semantic colors per cell) |

---

## 8. WHAT'S EXCESSIVE IN OMNIVIEW?

- Filter controls card has same visual weight as command header → **redundant framing**
- Too many toggle options visible simultaneously (grain + country + city + KPI + sort + plan version) → **cognitive load**
- MatrixExecutiveBanner content length can dominate (playbook text, impact %, confidence score) → **information density spike**

---

## 9. WHAT GENERATES NOISE?

- Filter controls in a full card (border + bg + rounded) competing with command header
- Controls section with 8+ dropdowns/toggles in 2 rows
- MatrixExecutiveBanner multiline expansion when warnings exist

---

## 10. WHAT DIFFICULTIES FOCUS?

- No dominant visual anchor in the command header
- Mode/period info is same font weight as health dots
- Multiple implicit focus modes without clear hierarchy

---

## 11. WHAT TRANSMITS "CONTROL"?

- Health dots (green/amber/red) — effective visual shorthand
- Attention counts (blocked/critical chips) — tells you what needs you
- Matrix cells with signal colors (green/warning/danger) — data-level control visibility

---

## 12. WHAT TRANSMITS "GENERIC DASHBOARD"?

- Filter controls card (generic card-with-fields pattern)
- Meta bar at 22px (looks like a browser status bar, not a command header)
- Border-radius on both command header and filter card (uniform look)

---

## TUNING RECOMMENDATIONS

### High impact, low risk
1. **Bump command header visual weight**: mode/period to 12px semibold (from 11px). Increase meta-bar min-height to 26px (from 22px).
2. **Reduce filter controls visual weight**: use ct-toolbar styling (no full card chrome) instead of card.

### Medium impact, safe
3. **Add view context text**: "Omniview Matrix" label in command header (even subtle — it signals "this is the command center").
4. **Stronger visual separation**: add a subtle shadow or border treatment to differentiate command header from filter bar.

### Structural (future phase)
5. Executive summary strip (not now — requires new data)
6. Category-style pillars for Omniview (not applicable — matrix is the display)
