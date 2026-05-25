# CONTROL TOWER USAGE METRICS — ARCHITECTURE PLAN

**Date**: 2025-05-25
**Purpose**: Define what to measure, not how to build the analytics system

---

## 1. PRINCIPLES

- Logging at service level, not analytics SDK
- No PII (no driver IDs in logs, only counts)
- No heavy instrumentation — leverage existing request logging
- Metrics stored in existing PostgreSQL (no new infra)
- This is an architecture PLAN — implementation deferred to when needed

---

## 2. METRICS TO TRACK

### System Health
| Metric | What | How |
|---|---|---|
| `omniview_matrix_load_time_ms` | Time for /ops/business-slice/omniview to respond | Already logged in main.py middleware |
| `omniview_projection_load_time_ms` | Time for /ops/business-slice/omniview-projection | Already logged |
| `behavioral_mvp_load_time_ms` | Time for /ops/diagnostics/behavioral/mvp | Already logged |
| `error_rate_5xx` | 500 errors per endpoint | Already logged |

### Feature Usage
| Metric | What | How |
|---|---|---|
| `view_mode_toggles` | Switches between Evolución and Vs Proyección | Frontend event → POST /ops/telemetry/event |
| `grain_changes` | Switches between monthly/weekly/daily | Same |
| `weekday_focus_applied` | VIE/LUN/etc. filter applied | Same |
| `weekday_focus_reset` | Filter reset to "todos" | Same |
| `drill_opened` | Cell click → drill panel | Same |
| `drill_momentum_tab` | Switched to Momentum tab in drill | Same |
| `drill_plan_vs_real_tab` | Switched to Plan vs Real tab in drill | Same |
| `fullscreen_activated` | Fullscreen matrix or drill | Same |
| `export_downloaded` | CSV export clicked | Same |
| `behavioral_panel_opened` | Behavioral MVP panel accessed | Same |

### Operational Value
| Metric | What | How |
|---|---|---|
| `priority_strip_items_read` | Which items operator hovered/clicked in strip | Frontend event |
| `cells_clicked_per_session` | How many drill interactions | Frontend event |
| `session_duration` | Time spent on Omniview Matrix page | Frontend event (visibility change) |
| `return_rate` | How often same user returns to Omniview | Session tracking |

---

## 3. TELEMETRY ENDPOINT (planned, not built)

```
POST /ops/telemetry/event
{
  "event": "weekday_focus_applied",
  "value": "VIE",
  "page": "/operacion/omniview-matrix",
  "timestamp": "2025-05-25T15:00:00Z"
}
```

Lightweight, fire-and-forget. No session tracking required for MVP metrics.

---

## 4. WHAT NOT TO TRACK

- Individual driver views (PII risk)
- Operator identity (privacy)
- Exact cell coordinates clicked (noise)
- Scroll position (noise)
- Mouse movement (privacy + noise)
- Session replay (privacy + complexity)

---

## 5. IMPLEMENTATION PHASES

| Phase | What | When |
|---|---|---|
| **Phase 1** | Use existing request logging (main.py middleware) — already live | Now |
| **Phase 2** | Add frontend event logging for feature usage | After operational validation shows features are useful |
| **Phase 3** | Build telemetry dashboard | When enough data exists to analyze |
| **Phase 4** | Session-based UX analytics | Only if adoption metrics show need for optimization |

---

## 6. CURRENT BASELINE (from existing logging)

| Metric | Source | Available? |
|---|---|---|
| API response times per endpoint | `main.py:44` middleware | ✅ |
| Request counts per endpoint | Middleware | ✅ |
| Error rates | Middleware | ✅ |
| Feature usage (toggles, clicks, drill) | Not logged | ❌ Phase 2 |
| Session duration | Not logged | ❌ Phase 2 |
