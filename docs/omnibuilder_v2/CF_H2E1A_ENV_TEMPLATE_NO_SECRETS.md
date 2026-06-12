# CF-H2E.1A — ENV VAR TEMPLATE (NO SECRETS)

> **Fase:** CF-H2E.1A — Multipark Credential Activation
> **Motor:** Control Foundation
> **Fecha:** 2026-06-12
> **Status:** TEMPLATE — NO SECRETS

---

## SECURITY RULE

Este archivo NUNCA contiene secrets reales. Los valores son placeholders vacíos.
Los secrets deben configurarse directamente como variables de entorno en el servidor o en `.env` local (nunca commitear).

---

## NAMING CANÓNICO

```
YANGO_<PARK_SLUG>_CLIENT_ID
YANGO_<PARK_SLUG>_API_KEY
```

---

## PILOT PARKS (5) — ENV VAR LIST

### Lima (TIER_1 — Production Baseline)

```env
# ── Yango Lima ──
YANGO_LIMA_CLIENT_ID=
YANGO_LIMA_API_KEY=
```

- **Park:** Yego Lima
- **park_id:** 08e20910d81d42658d4334d3f6d10ac0
- **City:** Lima, Peru
- **Status:** ACTIVE (44K orders ingested)

---

### Trujillo (TIER_2 — Major Operations)

```env
# ── Yango Trujillo ──
YANGO_TRUJILLO_CLIENT_ID=
YANGO_TRUJILLO_API_KEY=
```

- **Park:** Yego Trujillo
- **park_id:** 851e30755bba4d298e2e837f571b4ab8
- **City:** Trujillo, Peru
- **Status:** PENDING activation

---

### Arequipa (TIER_2 — Major Operations)

```env
# ── Yango Arequipa ──
YANGO_AREQUIPA_CLIENT_ID=
YANGO_AREQUIPA_API_KEY=
```

- **Park:** Yego Arequipa
- **park_id:** 56e4607dfc354e0a9cde4f0aa7973003
- **City:** Arequipa, Peru
- **Status:** PENDING activation

---

### Pro (TIER_2 — Major Operations)

```env
# ── Yango Pro ──
YANGO_PRO_CLIENT_ID=
YANGO_PRO_API_KEY=
```

- **Park:** Yego Pro
- **park_id:** 64085dd85e124e2c808806f70d527ea8
- **City:** Lima, Peru (premium fleet)
- **Status:** PENDING activation

---

### TukTuk (TIER_3 — Niche)

```env
# ── Yango TukTuk ──
YANGO_TUKTUK_CLIENT_ID=
YANGO_TUKTUK_API_KEY=
```

- **Park:** Yego TukTuk
- **park_id:** e3e07c00ed914f82a59c03283a178d6e
- **City:** Lima, Peru (mototaxi fleet)
- **Status:** PENDING activation

---

## EXCLUDED

### Mi Auto (TIER_3 — BLOCKED)

```env
# ── Yango Mi Auto ──
YANGO_MI_AUTO_CLIENT_ID=
YANGO_MI_AUTO_API_KEY=
```

- **Park:** Yego Mi Auto
- **park_id:** fafd623109d740f8a1f15af7c3dd86c6
- **Status:** BLOCKED — not in dim_park, metadata incomplete
- **Action:** DO NOT ACTIVATE until dim_park entry and metadata resolved

---

## LEGACY ENV VARS (Lima fallback)

These are the original Lima-only env vars. The scheduler falls back to these for Lima if `YANGO_LIMA_*` are not set:

```env
YANGO_CLIENT_ID=
YANGO_API_KEY=
YANGO_LIMA_PARK_ID=
```

---

## HOW TO ACTIVATE

1. Copy the env var pairs for the parks you want to activate.
2. Fill in the actual `CLIENT_ID` and `API_KEY` values from the Excel maestro.
3. Set them as environment variables or add to `.env` (NEVER commit `.env`).
4. Run `cf_h2e1_multipark_scheduler.py --once` to verify ingestion.

---

## VERIFICATION

```bash
# Test credential resolution
python -c "import os; print('LIMA CLIENT_ID set:', bool(os.environ.get('YANGO_LIMA_CLIENT_ID')))"

# Run scheduler dry-run for all parks
python -m scripts.cf_h2e1_multipark_scheduler --dry-run --parks all
```
