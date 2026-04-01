/**
 * Overrides de sesión / localStorage para calibración ligera del Insight Engine.
 * No toca backend. Solo claves soportadas; el resto se ignora.
 */
import { INSIGHT_CONFIG } from './insightConfig.js'

export const INSIGHT_USER_STORAGE_KEY = 'yego_omniview_insight_config'

const STORAGE_VERSION = 1

function clamp (n, lo, hi) {
  if (typeof n !== 'number' || Number.isNaN(n)) return lo
  return Math.min(hi, Math.max(lo, n))
}

/** Lee patch guardado (o null). */
export function loadInsightUserPatch () {
  try {
    const raw = localStorage.getItem(INSIGHT_USER_STORAGE_KEY)
    if (!raw) return null
    const o = JSON.parse(raw)
    if (o?.v !== STORAGE_VERSION || typeof o !== 'object') return null
    return sanitizePatch(o.patch || {})
  } catch {
    return null
  }
}

function sanitizePatch (p) {
  if (!p || typeof p !== 'object') return {}
  const out = {}
  if (p.sensitivityMultiplier != null) {
    out.sensitivityMultiplier = clamp(Number(p.sensitivityMultiplier), 0.5, 2)
  }
  if (p.panelTopN != null) {
    const n = Number(p.panelTopN)
    if ([5, 10, 20].includes(n)) out.panelTopN = n
  }
  if (p.impactWeights && typeof p.impactWeights === 'object') {
    const w = {}
    for (const k of Object.keys(INSIGHT_CONFIG.impactWeights)) {
      const x = Number(p.impactWeights[k])
      if (!Number.isNaN(x) && x >= 0 && x <= 1) w[k] = x
    }
    if (Object.keys(w).length) out.impactWeights = w
  }
  return out
}

/** Guarda patch (merge con existente saneado). */
export function saveInsightUserPatch (partial) {
  const prev = loadInsightUserPatch() ?? {}
  const next = sanitizePatch({ ...prev, ...partial })
  try {
    localStorage.setItem(INSIGHT_USER_STORAGE_KEY, JSON.stringify({ v: STORAGE_VERSION, patch: next }))
  } catch {
    /* ignore quota */
  }
  return next
}

export function clearInsightUserPatch () {
  try {
    localStorage.removeItem(INSIGHT_USER_STORAGE_KEY)
  } catch { /* ignore */ }
}

/**
 * Fusiona INSIGHT_CONFIG con patch de usuario (pesos, sensibilidad).
 * No muta el objeto base.
 */
export function mergeInsightRuntimeConfig (base = INSIGHT_CONFIG, userPatch = null) {
  const patch = userPatch && typeof userPatch === 'object' ? sanitizePatch(userPatch) : {}
  const impactWeights = { ...base.impactWeights, ...patch.impactWeights }
  return {
    ...base,
    impactWeights,
    userSensitivityMultiplier: patch.sensitivityMultiplier ?? 1,
    panelTopN: patch.panelTopN ?? base.panelDefaults?.topN ?? 10,
  }
}
