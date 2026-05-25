# OMNIVIEW AUTHORITY VISUAL AUDIT

**Date**: 2026-05-25

---

## BAND STACKING (top to bottom)

| # | Band | Height | Action |
|---|------|--------|--------|
| 1 | OmniviewCommandHeader card (rounded-lg border bg-ct-card shadow-sm) | ~2px border | PRESERVE + strengthen |
| 2 | Inside: command strip (bg-ct-surface border-b) | 26px | MERGE — remove inner bg, make strip transparent |
| 3 | Inside: MatrixExecutiveBanner children area (border-t bg-ct-surface/50 py-1.5) | 0-40px | REDUCE — py-1, integrate into same visual unit |
| 4 | Filter toolbar (ct-toolbar-compact rounded-lg border bg-ct-surface) | ~32px | MERGE into header card — single control surface |
| 5 | Matrix table | rest | PRESERVE |

## ISSUES FOUND

| Issue | Severity | Fix |
|-------|----------|-----|
| Two cards above matrix (header + filters) | HIGH | Merge into one |
| Command strip has its own bg + border, making it feel nested | MEDIUM | Remove inner bg/border from strip |
| Children area (banner) is visually separate from header | MEDIUM | Reduce padding, lighter separator |
| Filter toolbar is a full card competing with command header | HIGH | Move inside command header card |
| Gap between cards (space-y-2) adds dead air | LOW | Reduce to space-y-1.5 or eliminate |

## CLASSIFICATION

| Element | Action |
|---------|--------|
| Command header outer card | PRESERVE + strengthen (add left accent?) |
| Command strip inner bg/border | REMOVE (redundant nesting) |
| ExecutiveBanner children area | REDUCE (py-1, lighter separator) |
| Filter toolbar card | MERGE into command header |
| Matrix table | DO NOT TOUCH |
| Health dots | ELEVATE — they're good, keep visible |
| Attention counts | PRESERVE |
| Mode selector | ELEVATE — make more prominent |
