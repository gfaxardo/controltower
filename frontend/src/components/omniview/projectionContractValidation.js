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
    const missingYtdSlice = list.filter(
      (r) => r == null || typeof r.ytd_slice !== 'object' || r.ytd_slice?.slice_key == null,
    )
    if (missingYtdSlice.length > 0) {
      issues.push({
        code: 'missing_ytd_slice',
        message: `${missingYtdSlice.length} de ${list.length} filas sin ytd_slice válido`,
        missingCount: missingYtdSlice.length,
        total: list.length,
      })
    }
    const badRowType = list.filter(
      (r) =>
        r &&
        r.row_type != null &&
        r.row_type !== 'lob' &&
        r.row_type !== 'subfleet',
    )
    if (badRowType.length > 0) {
      issues.push({
        code: 'invalid_row_type',
        message: `${badRowType.length} filas con row_type distinto de lob|subfleet`,
        missingCount: badRowType.length,
        total: list.length,
      })
    }
    if (
      meta &&
      meta.ytd_summary &&
      typeof meta.ytd_summary === 'object' &&
      !meta.ytd_summary.error
    ) {
      const auth = meta.authoritative_ytd
      if (
        !auth ||
        typeof auth !== 'object' ||
        typeof auth.total !== 'object' ||
        typeof auth.total.ytd_slice !== 'object'
      ) {
        issues.push({
          code: 'missing_authoritative_ytd',
          message: 'meta.authoritative_ytd ausente o total sin ytd_slice (FASE 3.8B)',
        })
      }
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
