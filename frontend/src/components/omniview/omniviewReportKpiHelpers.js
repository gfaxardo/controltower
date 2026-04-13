/**
 * KPI ejecutivos para Reportes Omniview (totales matriz / períodos).
 */
import { MATRIX_KPIS, fmtValue, periodLabel } from './omniviewMatrixUtils.js'

/**
 * Último y penúltimo valor no nulo del KPI en la fila TOTAL (`matrix.totals`).
 */
export function getLastPrevForKpi (matrix, kpiKey) {
  if (!matrix?.allPeriods?.length || !matrix.totals) return null
  const periods = matrix.allPeriods
  let lastPk = null
  let lastVal = null
  for (let i = periods.length - 1; i >= 0; i--) {
    const pk = periods[i]
    const t = matrix.totals.get(pk)
    const v = t?.[kpiKey]
    if (v != null && v !== '' && !Number.isNaN(Number(v))) {
      lastPk = pk
      lastVal = Number(v)
      break
    }
  }
  if (lastPk == null) return null
  const lastIdx = periods.indexOf(lastPk)
  let prevPk = null
  let prevVal = null
  for (let i = lastIdx - 1; i >= 0; i--) {
    const pk = periods[i]
    const t = matrix.totals.get(pk)
    const v = t?.[kpiKey]
    if (v != null && v !== '' && !Number.isNaN(Number(v))) {
      prevPk = pk
      prevVal = Number(v)
      break
    }
  }
  return { lastPk, lastVal, prevPk, prevVal }
}

/**
 * Texto de variación vs período anterior en la serie (no baseline backend).
 */
export function formatDeltaVsPrevious (kpiKey, lastVal, prevVal) {
  if (prevVal == null || lastVal == null) return null
  const kpi = MATRIX_KPIS.find((k) => k.key === kpiKey)
  const diff = lastVal - prevVal
  if (kpi?.showAsPct) {
    const pp = diff * 100
    const sign = pp > 0 ? '+' : ''
    return `${sign}${pp.toFixed(1)} pp vs período anterior`
  }
  const pct = prevVal !== 0 ? (diff / Math.abs(prevVal)) * 100 : null
  const sign = diff > 0 ? '+' : diff < 0 ? '−' : ''
  const absStr = fmtValue(Math.abs(diff), kpiKey)
  if (pct != null && Number.isFinite(pct)) {
    const signPct = pct > 0 ? '+' : ''
    return `${sign}${absStr} (${signPct}${pct.toFixed(1)}%) vs período anterior`
  }
  return `${sign}${absStr} vs período anterior`
}

export function formatPeriodWindowLabel (allPeriods, grain) {
  if (!allPeriods?.length) return ''
  const a = periodLabel(allPeriods[0], grain)
  const b = periodLabel(allPeriods[allPeriods.length - 1], grain)
  return `${a} — ${b}`
}
