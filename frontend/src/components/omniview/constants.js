/** Años permitidos en Omniview Matrix / Reportes (UI fija). */
export const AVAILABLE_YEARS = [2025, 2026]

export const DEFAULT_OMNIVIEW_YEAR = 2026

/** Normaliza año persistido o por defecto a uno de AVAILABLE_YEARS. */
export function normalizeOmniviewYear (y) {
  const n = Number(y)
  if (AVAILABLE_YEARS.includes(n)) return n
  return DEFAULT_OMNIVIEW_YEAR
}
