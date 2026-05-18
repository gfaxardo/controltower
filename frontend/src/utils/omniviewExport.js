/**
 * omniviewExport.js — Control Foundation: Omniview Matrix Export
 *
 * Exporta la matriz de Omniview (Evolución y Vs Proyección) con metadata,
 * data quality, YTD, filtros y resumen de oportunidades.
 *
 * Motor: Control Foundation (ACTIVE)
 * NO usa backend. NO recalcula KPIs. NO incluye Decision/Action Engine.
 * Solo exporta datos ya cargados en la UI.
 */

import { MATRIX_KPIS, periodLabel as periodLabelFn, fmtValue, fmtDelta, signalColorForKpi, signalArrow, computeDeltas } from '../components/omniview/omniviewMatrixUtils.js'
import {
  PROJECTION_KPIS,
  fmtAttainment,
  fmtGap,
  fmtGapPct,
  projectionSignalColor,
  projectionPeriodLabel,
} from '../components/omniview/projectionMatrixUtils.js'

// ─── Helpers ─────────────────────────────────────────────────────────────────

function csvEscape (v) {
  let s = String(v === null || v === undefined ? '' : v)
  // Protección contra formula injection en Excel/Sheets
  // = y + son triggers universales de fórmula. - solo si va seguido de no-dígito.
  if (/^[=+@\t\r]/.test(s) || /^-(?![\d.])/.test(s)) {
    s = "'" + s
  }
  if (s.includes(',') || s.includes('"') || s.includes('\n') || s.includes('\r')) {
    return '"' + s.replace(/"/g, '""') + '"'
  }
  return s
}

function csvRow (cells) {
  return cells.map(csvEscape).join(',')
}

function csvSection (title, columns, rows) {
  const lines = []
  lines.push('')
  lines.push('--- ' + title + ' ---')
  lines.push(csvRow(columns))
  for (const row of rows) {
    lines.push(csvRow(row))
  }
  return lines.join('\n')
}

function ts () {
  const d = new Date()
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function filename (state) {
  const mode = state.viewMode === 'proyeccion' ? 'projection' : 'evolution'
  const grain = state.grain || 'monthly'
  const country = (state.country || 'all').toLowerCase().replace(/[^a-z0-9]/g, '')
  const city = (state.city || 'all').toLowerCase().replace(/[^a-z0-9]/g, '')
  const ver = (state.planVersion || 'noversion').toLowerCase().replace(/[^a-z0-9_-]/g, '').slice(0, 30)
  const d = new Date()
  const dateStr = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}_${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}`
  return `yego_omniview_${mode}_${grain}_${country}_${city}_${ver}_${dateStr}.csv`
}

// ─── Section builders ────────────────────────────────────────────────────────

function buildMetadataSection (state) {
  const cols = ['key', 'value']
  const rows = [
    ['export_generated_at', ts()],
    ['export_mode', state.viewMode === 'proyeccion' ? 'proyeccion' : 'evolucion'],
    ['grain', state.grain || 'monthly'],
    ['country', state.country || '(todos)'],
    ['city', state.city || '(todas)'],
    ['business_slice', state.businessSlice || '(todas)'],
    ['fleet', state.fleet || '(todas)'],
    ['year', state.year ?? ''],
    ['month', state.month || ''],
    ['selected_plan_version_key', state.planVersion || ''],
    ['show_subfleets', state.showSubfleets ? 'si' : 'no'],
    ['sort_key', state.sortKey || 'alpha'],
    ['focused_kpi', state.focusedKpi || 'trips_completed'],
    ['density', state.compact ? 'compacto' : 'comodo'],
    ['frontend_route', '/operacion/omniview-matrix'],
    ['data_last_available_at', state.maxDataDate || state.freshnessInfo?.derived_max_date || state.sliceMaxTripDate || ''],
    ['note', 'Export generado desde datos actualmente cargados en UI'],
  ]
  return csvSection('METADATA', cols, rows)
}

/** Metadata de la versión seleccionada (desde el registry de versiones). */
function buildVersionMetadataSection (state) {
  const { planVersion, planVersions } = state
  const cols = ['field', 'value']
  const rows = []
  const v = Array.isArray(planVersions)
    ? planVersions.find(p => p.key === planVersion || p.plan_version_key === planVersion)
    : null
  rows.push(['selected_plan_version_key', planVersion || ''])
  rows.push(['display_name', v?.display_name || v?.label || planVersion || ''])
  rows.push(['description', v?.description || ''])
  rows.push(['source_filename', v?.source_filename || ''])
  rows.push(['uploaded_by', v?.uploaded_by || ''])
  rows.push(['uploaded_at', v?.uploaded_at || ''])
  rows.push(['status', v?.status || 'active'])
  rows.push(['row_count', v?.row_count != null ? String(v.row_count) : ''])
  rows.push(['valid_rows', v?.valid_rows != null ? String(v.valid_rows) : ''])
  rows.push(['invalid_rows', v?.invalid_rows != null ? String(v.invalid_rows) : ''])
  rows.push(['min_period', v?.min_period || ''])
  rows.push(['max_period', v?.max_period || ''])
  return csvSection('VERSION_METADATA', cols, rows)
}

function buildDataQualitySection (state) {
  const cols = ['indicator', 'value', 'status', 'detail']
  const rows = []

  const df = state.matrixMeta?.data_freshness
  if (df) {
    rows.push(['data_freshness_status', df.status || '', df.max_data_date || '', `lag: ${df.lag_days ?? '—'} dias`])
  }
  if (state.freshnessInfo) {
    rows.push(['freshness_group', state.freshnessInfo.derived_max_date || '', state.freshnessInfo.status || '', state.freshnessInfo.message || ''])
  }
  if (state.coverageSummary) {
    rows.push(['coverage_pct', String(state.coverageSummary.coverage_pct ?? ''), state.coverageSummary.coverage_pct >= 95 ? 'ok' : 'warning', `mapped ${state.coverageSummary.mapped_trips ?? ''} / total ${state.coverageSummary.total_trips ?? ''}`])
  }
  if (state.matrixTrust) {
    const mt = state.matrixTrust
    rows.push(['trust_status', mt.trust_status || '', mt.trust_status || '', mt.message || ''])
    if (mt.operational_decision) {
      rows.push(['decision_mode', mt.operational_decision.decision_mode || '', mt.operational_decision.decision_mode || '', ''])
      if (mt.operational_decision.confidence) {
        rows.push(['confidence_score', String(mt.operational_decision.confidence.score ?? ''), '', `coverage:${mt.operational_decision.confidence.coverage} freshness:${mt.operational_decision.confidence.freshness} consistency:${mt.operational_decision.confidence.consistency}`])
      }
    }
  }
  if (state.projectionMeta?.integrity_status) {
    const int = state.projectionMeta.integrity_status
    rows.push(['integrity_status', int.status || '', int.status || '', (int.issues || []).join('; ')])
  }

  const projMeta = state.projectionMeta
  if (projMeta?.plan_without_real?.count > 0) {
    rows.push(['plan_without_real_count', String(projMeta.plan_without_real.count), 'warning', 'Filas de plan sin real asociado'])
  }

  return csvSection('DATA_QUALITY', cols, rows)
}

function buildFiltersSection (state) {
  const cols = ['filter', 'value']
  const rows = [
    ['view_mode', state.viewMode || 'evolucion'],
    ['grain', state.grain || 'monthly'],
    ['country', state.country || '(todos)'],
    ['city', state.city || '(todas)'],
    ['business_slice', state.businessSlice || '(todas)'],
    ['fleet', state.fleet || '(todas)'],
    ['year', state.year ?? ''],
    ['month', state.month || ''],
    ['selected_plan_version_key', state.planVersion || ''],
    ['show_subfleets', state.showSubfleets ? 'si' : 'no'],
    ['sort_key', state.sortKey || 'alpha'],
    ['focused_kpi', state.focusedKpi || 'trips_completed'],
    ['density', state.compact ? 'compacto' : 'comodo'],
    ['iso_week_scope', state.grain === 'weekly' ? 'ISO weeks (pueden cruzar meses)' : 'n/a'],
  ]
  return csvSection('FILTERS', cols, rows)
}

function buildEvolutionMatrixSection (state) {
  const { matrix, grain } = state
  if (!matrix || !matrix.allPeriods?.length) return ''
  const { cities, allPeriods } = matrix

  const cols = ['country', 'city', 'business_slice', 'fleet', 'is_subfleet', 'period_key', 'period_label', 'kpi', 'value', 'delta_pct', 'delta_abs', 'signal', 'previous_value', 'comparison_mode']
  const rows = []

  for (const [, cityData] of cities.entries()) {
    for (const [, lineData] of cityData.lines.entries()) {
      const deltasMap = computeDeltas(lineData.periods, allPeriods, state.periodStates)
      for (const pk of allPeriods) {
        const periodEntry = lineData.periods.get(pk)
        const deltas = deltasMap.get(pk)
        if (!periodEntry) continue
        for (const kpi of MATRIX_KPIS) {
          const val = periodEntry.metrics[kpi.key]
          const d = deltas?.[kpi.key]
          rows.push([
            cityData.country,
            cityData.city,
            lineData.business_slice_name,
            lineData.fleet_display_name,
            lineData.is_subfleet ? 'si' : 'no',
            pk,
            periodLabelFn(pk, grain, matrix.periodDayLabels),
            kpi.label,
            val != null ? String(val) : '',
            d?.delta_pct != null ? String(d.delta_pct) : '',
            d?.delta_abs != null ? String(d.delta_abs) : '',
            d?.signal || '',
            d?.previous != null ? String(d.previous) : '',
            d?.comparison_mode || '',
          ])
        }
      }
    }
  }

  return csvSection('EVOLUTION_MATRIX', cols, rows)
}

function buildProjectionMatrixSection (state) {
  const { projMatrix, grain } = state
  if (!projMatrix || !projMatrix.allPeriods?.length) return ''
  const { cities, allPeriods } = projMatrix

  const cols = ['country', 'city', 'business_slice', 'is_subfleet', 'period_key', 'period_label', 'kpi', 'real_value', 'projected_expected', 'projected_total', 'gap_abs', 'gap_pct', 'attainment_pct', 'signal', 'confidence', 'curve_method', 'fallback_level']
  const rows = []

  for (const [, cityData] of cities.entries()) {
    for (const [, lineData] of cityData.lines.entries()) {
      for (const pk of allPeriods) {
        const periodEntry = lineData.periods.get(pk)
        if (!periodEntry) continue
        for (const kpiKey of PROJECTION_KPIS) {
          const proj = periodEntry.projection?.[kpiKey]
          if (!proj) continue
          const kpi = MATRIX_KPIS.find(k => k.key === kpiKey)
          rows.push([
            cityData.country,
            cityData.city,
            lineData.business_slice_name,
            lineData.is_subfleet ? 'si' : 'no',
            pk,
            projectionPeriodLabel(pk, grain),
            kpi?.label || kpiKey,
            proj.actual != null ? String(proj.actual) : '',
            proj.projected_expected != null ? String(proj.projected_expected) : '',
            proj.projected_total != null ? String(proj.projected_total) : '',
            proj.gap_to_expected != null ? String(proj.gap_to_expected) : '',
            proj.gap_pct != null ? String(proj.gap_pct) : '',
            proj.attainment_pct != null ? String(proj.attainment_pct) : '',
            proj.signal || '',
            proj.curve_confidence || periodEntry.projection_confidence || '',
            proj.curve_method || '',
            proj.fallback_level != null ? String(proj.fallback_level) : '',
          ])
        }
      }
    }
  }

  return csvSection('PROJECTION_VS_REAL_LONG', cols, rows)
}

function buildYtdSummarySection (state) {
  const ytd = state.projectionMeta?.ytd_summary
  if (!ytd || ytd.error) return ''

  const cols = ['slice', 'kpi', 'ytd_real', 'ytd_plan', 'ytd_gap_abs', 'ytd_gap_pct', 'ytd_fulfillment_pct', 'signal', 'notes']
  const rows = []

  const slices = ytd.slices || ytd.by_slice
  const totalYtd = ytd.total || ytd.overall

  const pushSlice = (label, sliceData) => {
    if (!sliceData) return
    for (const kpi of PROJECTION_KPIS) {
      const pre = kpi + '_'
      const real = sliceData[pre + 'real'] ?? sliceData[kpi] ?? sliceData[pre + 'actual']
      const plan = sliceData[pre + 'plan'] ?? sliceData[pre + 'projected']
      const gap = sliceData[pre + 'gap'] ?? sliceData[pre + 'gap_abs']
      const gapPct = sliceData[pre + 'gap_pct']
      const fullPct = sliceData[pre + 'fulfillment_pct'] ?? sliceData[pre + 'attainment_pct']
      const sig = sliceData[pre + 'signal']
      const kpiLabel = (MATRIX_KPIS.find(k => k.key === kpi) || {}).label || kpi
      rows.push([
        label,
        kpiLabel,
        real != null ? String(real) : '',
        plan != null ? String(plan) : '',
        gap != null ? String(gap) : '',
        gapPct != null ? String(gapPct) : '',
        fullPct != null ? String(fullPct) : '',
        sig || '',
        sliceData.notes || sliceData.status || '',
      ])
    }
  }

  if (totalYtd) pushSlice('YTD_TOTAL', totalYtd)

  if (Array.isArray(slices)) {
    for (const s of slices) {
      const label = s.slice || s.business_slice_name || s.label || '—'
      pushSlice(label, s)
    }
  } else if (slices && typeof slices === 'object') {
    for (const [key, s] of Object.entries(slices)) {
      pushSlice(key, s)
    }
  }

  return csvSection('YTD_SUMMARY', cols, rows)
}

function buildOpportunitiesSection (state) {
  const meta = state.projectionMeta
  if (!meta) return ''
  const ops = Array.isArray(meta.operational_suggestions) ? meta.operational_suggestions : []
  const ctx = Array.isArray(meta.contextual_suggestions) ? meta.contextual_suggestions : []
  const all = [
    ...ops.map(s => ({ ...s, _type: 'operacional' })),
    ...ctx.map(s => ({ ...s, _type: 'contextual' })),
  ]
  if (!all.length) return ''

  const cols = ['type', 'headline', 'city', 'business_slice', 'priority_band', 'confidence', 'expected_impact_pct', 'owner_suggested', 'channel', 'rationale']
  const rows = []

  for (const s of all) {
    const headline = s.recommended_action_name || s.opportunity?.headline || ''
    rows.push([
      s._type,
      headline,
      s.city || s.country || '',
      s.business_slice_name || s.lob || '',
      s.priority_band || s.severity || '',
      s.confidence || s.opportunity?.confidence || '',
      s.expected_impact != null ? String(s.expected_impact) : '',
      s.owner_suggested || s.target_team || '',
      s.channel_suggested || '',
      s.why || s.rationale || s.opportunity?.explanation || '',
    ])
  }

  return csvSection('OPPORTUNITIES_COMPACT', cols, rows)
}

// ─── Main export function ────────────────────────────────────────────────────

/**
 * @param {object} state — all relevant component state at export time
 * @returns {string} CSV content
 */
export function buildOmniviewExportPayload (state) {
  const sections = [
    buildMetadataSection(state),
    buildVersionMetadataSection(state),
    buildDataQualitySection(state),
    buildFiltersSection(state),
  ]

  if (state.viewMode === 'proyeccion') {
    sections.push(buildProjectionMatrixSection(state))
    sections.push(buildYtdSummarySection(state))
  } else {
    sections.push(buildEvolutionMatrixSection(state))
  }

  sections.push(buildOpportunitiesSection(state))

  return '\uFEFF' + sections.filter(Boolean).join('\n') + '\n'
}

/**
 * Triggers browser download of CSV.
 */
export function downloadOmniviewExport (content, filenameStr) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filenameStr
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * Convenience: builds payload and triggers download.
 * @param {object} state
 */
export function exportOmniviewFull (state) {
  const content = buildOmniviewExportPayload(state)
  downloadOmniviewExport(content, filename(state))
}
