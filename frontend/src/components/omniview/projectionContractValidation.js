/**
 * Validación de contrato Omniview (proyección): YTD en meta y PoP en filas.
 * Refuerzo anti-regresión silenciosa; no altera datos, solo reporta.
 */

/**
 * @param {Record<string, unknown>|null|undefined} meta
 * @param {unknown[]} rows
 * @returns {{ ok: boolean, issues: Array<{ code: string, message: string, missingCount?: number, total?: number }> }}
 */
export function validateProjectionOmniviewContract (meta, rows) {
  const issues = []
  if (meta == null) {
    issues.push({ code: 'missing_meta', message: 'meta ausente en la respuesta' })
  } else if (meta.ytd_summary === undefined || meta.ytd_summary === null) {
    issues.push({ code: 'missing_ytd_summary', message: 'meta.ytd_summary ausente' })
  } else if (typeof meta.ytd_summary === 'object' && meta.ytd_summary.error) {
    issues.push({ code: 'ytd_summary_error', message: String(meta.ytd_summary.error) })
  }
  const list = Array.isArray(rows) ? rows : []
  if (list.length > 0) {
    const missingPop = list.filter((r) => r == null || typeof r.period_over_period !== 'object')
    if (missingPop.length > 0) {
      issues.push({
        code: 'missing_period_over_period',
        message: `${missingPop.length} de ${list.length} filas sin period_over_period`,
        missingCount: missingPop.length,
        total: list.length,
      })
    }
  }
  return { ok: issues.length === 0, issues }
}

/**
 * @param {Record<string, unknown>|null|undefined} meta
 * @param {unknown[]} rows
 */
export function logProjectionYtdPopDebug (meta, rows) {
  console.log('[projection debug] ytd_summary:', meta?.ytd_summary ?? null)
  const list = Array.isArray(rows) ? rows : []
  const sample = list.slice(0, 8).map((r, i) => ({
    i,
    line: r?.business_slice_name ?? r?.city ?? i,
    period_over_period: r?.period_over_period ?? null,
  }))
  console.log('[projection debug] period_over_period (muestra hasta 8 filas):', sample)
  const missing = list.filter((r) => r == null || typeof r.period_over_period !== 'object').length
  console.log('[projection debug] period_over_period resumen:', { total: list.length, missing })
}
