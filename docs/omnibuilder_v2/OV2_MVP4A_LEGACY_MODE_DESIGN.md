# OV2-MVP.4A — LEGACY MODE DESIGN

> **Fase:** OV2-MVP.4A — Deprecation Preparation
> **Sub-document:** Legacy Mode Design
> **Fecha:** 2026-06-12

---

## 1. CONCEPT

`V1_LEGACY_MODE` is a feature flag that puts Omniview V1 into a read-only legacy state. V1 remains accessible but is clearly marked as deprecated. This is the intermediate state between "V2 active" and "V1 removed."

---

## 2. FLAG DESIGN

### Backend Flag

```python
# settings.py
V1_LEGACY_MODE: bool = Field(default=False)
```

### Frontend Flag

```javascript
// .env
VITE_V1_LEGACY_MODE=false
```

### Activation

```bash
# Server: set env var
export V1_LEGACY_MODE=true

# Frontend: build-time flag
VITE_V1_LEGACY_MODE=true npm run build
```

---

## 3. WHAT HAPPENS IN LEGACY MODE

### V1 Behavior

| Aspect | Normal | Legacy Mode |
|--------|--------|-------------|
| Route accessible | Yes | **Yes** (no redirect) |
| Data served | Production | Production (same endpoints) |
| Banner | None | **"V1 LEGACY — This view will be deprecated. Use Omniview V2."** |
| New features | Allowed | **Frozen** |
| Bug fixes | Allowed | P0 only |
| Performance optimizations | Allowed | **Frozen** |
| Default route | Yes | **No** — V2 becomes default |

### V2 Behavior

| Aspect | Normal | Legacy Mode |
|--------|--------|-------------|
| Route accessible | Dev only | **Production** |
| productionReady | false | **true** |
| Default route | No | **Yes** |

---

## 4. TRANSITION STATES

```
┌─────────────┐    trial pass    ┌─────────────┐    30d stable    ┌──────────────┐
│  CURRENT     │ ───────────────→ │  LEGACY      │ ──────────────→ │  REMOVED      │
│  V1: default │                  │  V1: legacy  │                  │  V2: only     │
│  V2: shadow  │                  │  V2: default │                  │  V1: gone     │
└─────────────┘                  └─────────────┘                  └──────────────┘
```

---

## 5. IMPLEMENTATION (pseudo-code)

### Backend (router)

```python
@router.get("/ops/business-slice/monthly")
def get_monthly(..., response: Response):
    from app.settings import settings
    if settings.V1_LEGACY_MODE:
        response.headers["X-V1-Legacy"] = "true"
    # ... normal response
```

### Frontend (App.jsx)

```jsx
const V1_LEGACY_MODE = import.meta.env.VITE_V1_LEGACY_MODE === 'true';

// Legacy banner above V1 views
{V1_LEGACY_MODE && (
  <div className="v1-legacy-banner">
    V1 LEGACY — This view will be deprecated. Use Omniview V2.
  </div>
)}

// V2 becomes default route
{defaultTab === 'Operacion' && V1_LEGACY_MODE && (
  <Navigate to="/operacion/omniview-v2-shadow" />
)}
```

### Navigation Registry

```javascript
// When V1_LEGACY_MODE:
// - V1 entries get visibility: KEEP_VISIBLE (still accessible, but marked)
// - V2 entry gets productionReady: true
// - V2 gets defaultRoute: true
```

---

## 6. ROLLBACK FROM LEGACY MODE

```
Set V1_LEGACY_MODE=false
→ V1 returns to default
→ V2 returns to shadow
→ Zero code changes needed
```

**Rollback time: < 60 seconds** (env var change + restart or rebuild)

---

## 7. SAFETY RULES

| Rule | Enforcement |
|------|-------------|
| Legacy mode never removes data | Flag-based, no code deletion |
| V1 endpoints never go down | Same serving chain |
| Rollback is instant | Single env var toggle |
| No redirects forced on users | V1 routes still work, just marked |
| Training required before activation | Operations team must know legacy mode exists |
