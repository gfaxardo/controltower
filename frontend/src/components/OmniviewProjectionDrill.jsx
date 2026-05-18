import { useEffect, useMemo, useState } from 'react'
import { MATRIX_KPIS, periodHeaderPrimary } from './omniview/omniviewMatrixUtils.js'
import {
  PROJECTION_KPIS,
  fmtAttainment,
  fmtGap,
  projectionSignalColor,
  SIGNAL_DOT,
  describeCurveSource,
  getKpiContract,
  getKpiComparabilityBadge,
  getKpiComparabilityNote,
  getKpiDecisionStatus,
  getKpiDecisionNote,
  getKpiDecisionBadge,
  KPI_AGGREGATION_TYPE,
} from './omniview/projectionMatrixUtils.js'
import { computeRootCause, fmtImpact } from './omniview/rootCauseEngine.js'
import { buildDrillAlertPayload, buildActionHandoff } from './omniview/alertingEngine.js'
import { getControlLoopPlanVsReal } from '../services/api.js'

export default function OmniviewProjectionDrill ({ selection, grain, compact, onClose, projectionMeta, planVersion }) {
  const w = compact ? 'w-80' : 'w-[25rem]'

  if (!selection) return null

  return (
    <aside className={`${w} shrink-0 rounded-lg border border-gray-200 bg-white shadow-sm self-start sticky top-2 overflow-hidden`}>
      <DrillContent
        selection={selection}
        grain={grain}
        compact={compact}
        onClose={onClose}
        projectionMeta={projectionMeta}
        planVersion={planVersion}
      />
    </aside>
  )
}

function DrillContent ({ selection, grain, compact, onClose, projectionMeta, planVersion }) {
  const [clData, setClData] = useState(null)
  const [clLoading, setClLoading] = useState(false)

  const { cityKey, lineKey, period, kpiKey, lineData, periodDeltas, raw } = selection
  const cityParts = cityKey.split('::')
  const cityName = cityParts[1] || cityParts[0]
  const countryName = cityParts[0]
  const sliceName = lineData?.business_slice_name || '—'

  const drillAlert = useMemo(
    () => buildDrillAlertPayload({
      cityKey,
      lineKey,
      city: cityName,
      country: countryName,
      slice: sliceName,
      period,
      grain,
      kpiKey,
      periodDeltas,
    }),
    [cityKey, lineKey, cityName, countryName, sliceName, period, grain, kpiKey, periodDeltas]
  )

  const selectedKpi = useMemo(
    () => MATRIX_KPIS.find(k => k.key === kpiKey) || MATRIX_KPIS[0],
    [kpiKey]
  )

  const delta = periodDeltas?.[kpiKey]

  useEffect(() => {
    if (!planVersion || !cityName || cityName === '—') return
    let cancelled = false
    setClLoading(true)
    getControlLoopPlanVsReal({
      plan_version: planVersion,
      city: cityName,
    })
      .then(res => {
        if (cancelled) return
        const rows = res?.data || []
        const filtered = rows.filter(r =>
          r.business_slice_name === sliceName ||
          r.linea_negocio_canonical === sliceName
        )
        setClData(filtered.length > 0 ? filtered : rows.slice(0, 10))
      })
      .catch(() => { if (!cancelled) setClData(null) })
      .finally(() => { if (!cancelled) setClLoading(false) })
    return () => { cancelled = true }
  }, [planVersion, cityName, sliceName])

  const fontSize = compact ? 'text-[10px]' : 'text-[11px]'
  const labelCls = `${fontSize} text-gray-400 font-medium`
  const valueCls = `${fontSize} text-gray-800 font-semibold`

  return (
    <>
      <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between bg-slate-50/60">
        <div className="min-w-0">
          <h3 className="text-xs font-bold text-gray-700 uppercase tracking-wide truncate">{cityName} · {sliceName}</h3>
          <p className="text-[10px] text-gray-400 mt-0.5">{countryName} · {period} · {selectedKpi.label}</p>
        </div>
        <button type="button" onClick={onClose} className="p-1 rounded hover:bg-gray-200 transition-colors flex-shrink-0" title="Cerrar">
          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="divide-y divide-gray-100 max-h-[calc(100vh-200px)] overflow-y-auto">
        {/* Evolution Chart — Real vs Proyección + tendencia */}
        <ProjectionEvolutionChart selection={selection} grain={grain} compact={compact} />

        {/* FASE_KPI_CONSISTENCY: Tipo de KPI y comparabilidad cross-grain */}
        <KpiContractSection kpiKey={kpiKey} kpiContract={projectionMeta?.kpi_contract} labelCls={labelCls} valueCls={valueCls} />

        {/* Gap summary */}
        {delta?.isProjection && (
          <div className="px-4 py-3">
            <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Resumen gap</h4>
            <GapSummaryGrid delta={delta} kpiKey={kpiKey} labelCls={labelCls} valueCls={valueCls} />
          </div>
        )}

        {/* Curve detail */}
        {delta?.isProjection && (
          <div className="px-4 py-3 bg-amber-50/30 border-b border-amber-100/80">
            <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Confianza de proyección</h4>
            <div className="flex flex-wrap items-center gap-2 mb-1">
              <span className={`inline-block px-1.5 py-px rounded text-[9px] font-bold border ${
                (delta.projection_confidence === 'high' || !delta.projection_confidence)
                  ? 'bg-emerald-100 text-emerald-900 border-emerald-200'
                  : delta.projection_confidence === 'medium'
                    ? 'bg-amber-100 text-amber-900 border-amber-200'
                    : 'bg-red-100 text-red-900 border-red-200'
              }`}>
                {!delta.projection_confidence || delta.projection_confidence === 'high'
                  ? 'Alta'
                  : delta.projection_confidence === 'medium'
                    ? 'Media'
                    : 'Baja'}
              </span>
              {delta.projection_anomaly && (
                <span className="text-[9px] font-semibold text-amber-800 border border-amber-300 rounded px-1">Anomalía vol.</span>
              )}
            </div>
            <p className="text-[9px] text-gray-600 leading-snug">
              Basado en nivel de fallback de trips y magnitud del ajuste de conservación en la celda.
            </p>
          </div>
        )}

        {delta?.isProjection && delta.curve_method && (
          <div className="px-4 py-3">
            <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Detalle curva</h4>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1">
              <span className={labelCls}>Método</span>
              <span className={valueCls}>{describeCurveSource(delta.curve_method)}</span>
              <span className={labelCls}>Confianza</span>
              <span className={valueCls}>
                <ConfidenceBadge confidence={delta.curve_confidence} />
              </span>
              {delta.fallback_level != null && (
                <>
                  <span className={labelCls}>Nivel fallback</span>
                  <span className={valueCls}>{delta.fallback_level}</span>
                </>
              )}
              {delta.expected_ratio != null && (
                <>
                  <span className={labelCls}>Ratio esperado</span>
                  <span className={valueCls}>{(delta.expected_ratio * 100).toFixed(1)}%</span>
                </>
              )}
              {delta.conservation_adjustment_applied && (
                <>
                  <span className={labelCls}>Ajuste conservación</span>
                  <span className={valueCls}>
                    {delta.conservation_adjustment_value != null ? `${delta.conservation_adjustment_value >= 0 ? '+' : ''}${delta.conservation_adjustment_value}` : 'sí'}
                    {' '}(últ. período)
                  </span>
                </>
              )}
            </div>
          </div>
        )}

        {/* Breakdown por KPI */}
        <div className="px-4 py-3">
          <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Breakdown por KPI</h4>
          <div className="space-y-2">
            {PROJECTION_KPIS.map(kpi => {
              const d = periodDeltas?.[kpi]
              const kpiMeta = MATRIX_KPIS.find(k => k.key === kpi)
              if (!d || !d.isProjection) return null
              const signal = d.signal || 'no_data'
              const dotClass = SIGNAL_DOT[signal] || SIGNAL_DOT.no_data
              const attColor = projectionSignalColor(signal)
              const isCurrent = kpi === kpiKey

              return (
                <div key={kpi} className={`rounded-md border px-3 py-2 ${isCurrent ? 'border-blue-200 bg-blue-50/40' : 'border-gray-100 bg-gray-50/30'}`}>
                  <div className="flex items-center justify-between mb-1">
                    <span className={`${fontSize} font-semibold text-gray-700`}>{kpiMeta?.label || kpi}</span>
                    <span className="inline-flex items-center gap-1">
                      <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotClass}`} />
                      <span className={`${fontSize} font-bold`} style={{ color: attColor }}>{fmtAttainment(d.attainment_pct)}</span>
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1">
                    <div>
                      <div className="text-[9px] text-gray-400">Real</div>
                      <div className={`${fontSize} font-medium text-gray-700`}>{_fmtCompact(d.value)}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-gray-400">Expected</div>
                      <div className={`${fontSize} font-medium text-gray-700`}>{_fmtCompact(d.projected_expected)}</div>
                    </div>
                    <div>
                      <div className="text-[9px] text-gray-400">Gap</div>
                      <div className={`${fontSize} font-medium text-gray-700`}>{fmtGap(d.gap_to_expected, kpi)}</div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Root Cause Analysis */}
        {delta?.isProjection && (
          <RootCauseSection
            kpiKey={kpiKey}
            periodDeltas={periodDeltas}
            compact={compact}
          />
        )}

        {/* Acción sugerida (FASE 3.3) */}
        {delta?.isProjection && drillAlert && (
          <ActionSection drillAlert={drillAlert} compact={compact} />
        )}

        {/* Control Loop history */}
        <div className="px-4 py-3">
          <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Historial Plan vs Real</h4>
          {clLoading && (
            <div className="flex items-center gap-2 py-2">
              <span className="inline-block w-3 h-3 border-2 border-gray-300 border-t-blue-500 rounded-full animate-spin" />
              <span className="text-[10px] text-gray-400">Cargando...</span>
            </div>
          )}
          {!clLoading && (!clData || clData.length === 0) && (
            <p className="text-[10px] text-gray-400 py-1">Sin datos históricos disponibles para esta combinación.</p>
          )}
          {!clLoading && clData && clData.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-100">
                    <th className="px-1 py-0.5 text-left text-[9px] font-medium text-gray-400 uppercase">Periodo</th>
                    <th className="px-1 py-0.5 text-left text-[9px] font-medium text-gray-400 uppercase">Tajada</th>
                    <th className="px-1 py-0.5 text-right text-[9px] font-medium text-gray-400 uppercase">Plan</th>
                    <th className="px-1 py-0.5 text-right text-[9px] font-medium text-gray-400 uppercase">Real</th>
                    <th className="px-1 py-0.5 text-right text-[9px] font-medium text-gray-400 uppercase">Gap%</th>
                  </tr>
                </thead>
                <tbody>
                  {clData.slice(0, 8).map((row, i) => {
                    const gapPct = row.gap_pct_trips ?? row.gap_pct_revenue
                    const gapColor = gapPct == null ? 'text-gray-400'
                      : Number(gapPct) <= 0 ? 'text-emerald-700'
                      : Number(gapPct) <= 10 ? 'text-amber-700'
                      : 'text-red-700'
                    return (
                      <tr key={i} className="border-b border-gray-50">
                        <td className="px-1 py-0.5 text-[10px] text-gray-600 whitespace-nowrap">{row.period || '—'}</td>
                        <td className="px-1 py-0.5 text-[10px] text-gray-600 truncate max-w-[80px]" title={row.business_slice_name}>{row.business_slice_name || row.linea_negocio_canonical || '—'}</td>
                        <td className="px-1 py-0.5 text-[10px] text-gray-700 text-right font-medium">{_fmtCompact(row.projected_trips ?? row.projected_revenue)}</td>
                        <td className="px-1 py-0.5 text-[10px] text-gray-700 text-right font-medium">{_fmtCompact(row.real_trips ?? row.real_revenue)}</td>
                        <td className={`px-1 py-0.5 text-[10px] text-right font-semibold ${gapColor}`}>
                          {gapPct != null ? `${Number(gapPct).toFixed(1)}%` : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  )
}

function GapSummaryGrid ({ delta, kpiKey, labelCls, valueCls }) {
  const signal = delta.signal || 'no_data'
  const dotClass = SIGNAL_DOT[signal] || SIGNAL_DOT.no_data
  const attColor = projectionSignalColor(signal)

  return (
    <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
      <span className={labelCls}>Real al corte</span>
      <span className={valueCls}>{_fmtCompact(delta.value)}</span>

      <span className={labelCls}>Expected al corte</span>
      <span className={valueCls}>{_fmtCompact(delta.projected_expected)}</span>

      <span className={labelCls}>Plan total periodo</span>
      <span className={valueCls}>{_fmtCompact(delta.projected_total)}</span>

      <span className={labelCls}>Cumplimiento</span>
      <span className={valueCls}>
        <span className="inline-flex items-center gap-1">
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${dotClass}`} />
          <span style={{ color: attColor }}>{fmtAttainment(delta.attainment_pct)}</span>
        </span>
      </span>

      <span className={labelCls}>Gap vs expected</span>
      <span className={valueCls}>{fmtGap(delta.gap_to_expected, kpiKey)}</span>

      {delta.gap_to_full != null && (
        <>
          <span className={labelCls}>Gap vs plan total</span>
          <span className={valueCls}>{fmtGap(delta.gap_to_full, kpiKey)}</span>
        </>
      )}

      {delta.completion_pct != null && (
        <>
          <span className={labelCls}>Completitud vs plan</span>
          <span className={valueCls}>{delta.completion_pct.toFixed(1)}%</span>
        </>
      )}
    </div>
  )
}

function ConfidenceBadge ({ confidence }) {
  if (!confidence) return <span className="text-gray-400">—</span>
  const cls = confidence === 'high' ? 'bg-emerald-100 text-emerald-800 border-emerald-200'
    : confidence === 'medium' ? 'bg-amber-100 text-amber-800 border-amber-200'
    : 'bg-red-100 text-red-800 border-red-200'
  const label = confidence === 'high' ? 'Alta'
    : confidence === 'medium' ? 'Media'
    : confidence === 'fallback' ? 'Fallback'
    : 'Baja'
  return (
    <span className={`inline-block px-1.5 py-px rounded text-[9px] font-semibold border ${cls}`}>{label}</span>
  )
}

// ─── Root Cause Analysis Section ─────────────────────────────────────────────

const DRIVER_BADGE_CLS = {
  positive: 'bg-emerald-100 text-emerald-800 border-emerald-200',
  negative: 'bg-red-100 text-red-800 border-red-200',
  neutral:  'bg-gray-100 text-gray-700 border-gray-200',
}

const META_LABELS = {
  ticket_actual:    'Ticket real',
  ticket_expected:  'Ticket esperado',
  tpd_actual:       'Trips/driver real',
  tpd_expected:     'Trips/driver esperado',
  drivers_actual:   'Drivers reales',
  drivers_expected: 'Drivers esperados',
  trips_actual:     'Trips reales',
  trips_expected:   'Trips esperados',
}

const TEAM_LABELS = {
  supply: 'Supply',
  ops: 'Operaciones',
  pricing: 'Pricing',
  marketing: 'Marketing',
  loyalty: 'Loyalty',
  closer: 'Closer',
}

const SEVERITY_BADGE = {
  CRITICAL: 'bg-red-100 text-red-900 border-red-300',
  HIGH: 'bg-orange-100 text-orange-900 border-orange-300',
  MEDIUM: 'bg-amber-100 text-amber-900 border-amber-300',
  LOW: 'bg-slate-100 text-slate-700 border-slate-200',
  WATCH: 'bg-emerald-100 text-emerald-900 border-emerald-200',
}

const URGENCY_LABELS = {
  immediate: 'Inmediata',
  same_day: 'Mismo día',
  this_week: 'Esta semana',
}

function ActionSection ({ drillAlert, compact }) {
  const [showDebug, setShowDebug] = useState(false)
  const fontSize = compact ? 'text-[10px]' : 'text-[11px]'
  const handoff = useMemo(() => buildActionHandoff(drillAlert), [drillAlert])
  const sev = drillAlert.severity || 'LOW'
  const badgeCls = SEVERITY_BADGE[sev] || SEVERITY_BADGE.LOW
  const team = TEAM_LABELS[drillAlert.target_team] || drillAlert.target_team

  return (
    <div className="px-4 py-3 border-t border-gray-100">
      <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Acción sugerida</h4>

      <div className="flex flex-wrap items-center gap-2 mb-2">
        <span className={`inline-block px-1.5 py-px rounded text-[9px] font-bold border ${badgeCls}`}>
          {drillAlert.priority_band} · {sev}
        </span>
        <span className={`${fontSize} text-gray-500`}>
          Score {drillAlert.priority_score != null ? drillAlert.priority_score.toFixed(1) : '—'}
        </span>
      </div>

      <div className="space-y-1.5 mb-2">
        <div>
          <span className="text-[9px] text-gray-400">Equipo sugerido</span>
          <div className={`${fontSize} font-semibold text-gray-800`}>{team}</div>
        </div>
        <div>
          <span className="text-[9px] text-gray-400">Urgencia</span>
          <div className={`${fontSize} font-semibold text-gray-800`}>
            {URGENCY_LABELS[drillAlert.urgency] || drillAlert.urgency}
          </div>
        </div>
        <div>
          <span className="text-[9px] text-gray-400">Razón</span>
          <div className={`${fontSize} text-gray-700 leading-snug`}>{drillAlert.action_rationale}</div>
        </div>
        <div className="rounded-md bg-violet-50 border border-violet-100 px-2 py-1.5">
          <div className={`${fontSize} text-violet-900 font-medium`}>{drillAlert.suggested_action_text}</div>
        </div>
        {Array.isArray(drillAlert.trust_notes) && drillAlert.trust_notes.length > 0 && (
          <div className="rounded-md bg-slate-50 border border-slate-200 px-2 py-1.5 space-y-0.5">
            {drillAlert.trust_notes.map((tn, i) => (
              <div key={i} className={`${fontSize} text-slate-700`}>{tn}</div>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        onClick={() => setShowDebug(s => !s)}
        className="text-[9px] text-gray-400 hover:text-gray-600 underline mb-1"
      >
        {showDebug ? 'Ocultar' : 'Ver'} desglose del score (auditoría)
      </button>
      {showDebug && drillAlert.score_breakdown && (
        <div className={`rounded border border-gray-100 bg-gray-50 px-2 py-1.5 ${fontSize} text-gray-600 font-mono space-y-0.5`}>
          <div>gap_component: {drillAlert.score_breakdown.gap_component}</div>
          <div>signal_component: {drillAlert.score_breakdown.signal_component}</div>
          <div>kpi_weight: {drillAlert.score_breakdown.kpi_weight}</div>
          <div>grain_factor: {drillAlert.score_breakdown.grain_factor}</div>
          <div>confidence_mult: {drillAlert.score_breakdown.confidence_multiplier}</div>
          <div>curve: {drillAlert.score_breakdown.curve_confidence}</div>
          <div>main_driver: {drillAlert.score_breakdown.main_driver_key ?? '—'}</div>
          <div className="text-gray-500 whitespace-pre-wrap pt-1">{drillAlert.impact_basis}</div>
          {handoff && (
            <div className="pt-1 border-t border-gray-200 mt-1 text-[9px] text-gray-500">
              Handoff v{handoff.handoff_version} · {handoff.generated_at}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function RootCauseSection ({ kpiKey, periodDeltas, compact }) {
  const result = useMemo(
    () => computeRootCause(kpiKey, periodDeltas),
    [kpiKey, periodDeltas]
  )

  const fontSize = compact ? 'text-[10px]' : 'text-[11px]'

  if (!result.is_complete) {
    return (
      <div className="px-4 py-3">
        <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Root Cause Analysis</h4>
        <p className={`${fontSize} text-gray-400 italic`}>
          {result.reason || 'Datos insuficientes para descomponer el gap.'}
        </p>
      </div>
    )
  }

  const { gap_total, factors, main_driver, recommendation, meta } = result
  const maxAbs = Math.max(...factors.map(f => Math.abs(f.impact)), 1)
  const mainBadgeCls = DRIVER_BADGE_CLS[main_driver?.direction] || DRIVER_BADGE_CLS.neutral

  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">Root Cause Analysis</h4>
        <span className={`${fontSize} font-semibold`} style={{ color: gap_total >= 0 ? '#059669' : '#dc2626' }}>
          {fmtImpact(gap_total, kpiKey)}
        </span>
      </div>

      {/* Badge driver principal */}
      {main_driver && (
        <div className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md border text-[10px] font-semibold mb-3 ${mainBadgeCls}`}>
          <svg className="w-3 h-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          Principal causa: {main_driver.label} ({main_driver.pct}%)
        </div>
      )}

      {/* Barras horizontales por factor */}
      <div className="space-y-2 mb-3">
        {factors.map(factor => {
          const barWidth = Math.round((Math.abs(factor.impact) / maxAbs) * 100)
          const isMain = factor.key === main_driver?.key
          const barCls = factor.direction === 'positive' ? 'bg-emerald-500' : factor.direction === 'negative' ? 'bg-red-400' : 'bg-gray-300'
          const impactColor = factor.direction === 'positive' ? '#059669' : factor.direction === 'negative' ? '#dc2626' : '#6b7280'

          return (
            <div key={factor.key}>
              <div className="flex items-center justify-between mb-0.5">
                <span className={`${fontSize} text-gray-600 ${isMain ? 'font-semibold' : 'font-normal'}`}>
                  {factor.label}
                </span>
                <span className={`${fontSize} font-semibold tabular-nums`} style={{ color: impactColor }}>
                  {fmtImpact(factor.impact, kpiKey)}
                  <span className="text-gray-400 font-normal ml-1">({factor.pct}%)</span>
                </span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-1.5">
                <div
                  className={`${barCls} h-1.5 rounded-full transition-all`}
                  style={{ width: `${barWidth}%` }}
                />
              </div>
            </div>
          )
        })}
      </div>

      {/* Métricas derivadas relevantes */}
      {meta && Object.keys(meta).some(k => meta[k] != null) && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 mb-3 pt-2 border-t border-gray-100">
          {Object.entries(meta).map(([k, v]) => {
            if (v == null || !META_LABELS[k]) return null
            return (
              <div key={k} className="flex flex-col">
                <span className="text-[9px] text-gray-400">{META_LABELS[k]}</span>
                <span className={`${fontSize} font-medium text-gray-700`}>{_fmtCompact(v)}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Recomendación */}
      {recommendation && (
        <div className="rounded-md bg-blue-50 border border-blue-100 px-3 py-2">
          <div className="flex items-start gap-1.5">
            <svg className="w-3 h-3 text-blue-400 flex-shrink-0 mt-px" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            <span className={`${fontSize} text-blue-700 leading-snug`}>{recommendation}</span>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Evolution Chart (Real vs Proyección + tendencia) ──────────────────

function ProjectionEvolutionChart ({ selection, grain, compact }) {
  const { lineData, kpiKey: initialKpi } = selection
  const [chartKpi, setChartKpi] = useState(initialKpi)

  const series = useMemo(() => {
    if (!lineData?.periods) return { points: [], projPoints: [], labels: [], trend: [], min: 0, max: 100 }
    const entries = [...lineData.periods.entries()].sort((a, b) => String(a[0]).localeCompare(String(b[0])))
    const isProjectable = PROJECTION_KPIS.includes(chartKpi)
    const points = []
    const projPoints = []
    const labels = []

    for (const [pk, cell] of entries) {
      const realVal = isProjectable
        ? (cell.projection?.[chartKpi]?.actual ?? cell.metrics?.[chartKpi])
        : cell.metrics?.[chartKpi]
      if (realVal == null && !isProjectable) continue
      const projVal = isProjectable
        ? (cell.projection?.[chartKpi]?.projected_expected ?? cell.projection?.[chartKpi]?.projected_total)
        : null
      points.push({ period: pk, value: Number(realVal) })
      if (projVal != null) projPoints.push({ period: pk, value: Number(projVal) })
      const d = new Date(pk + 'T00:00:00')
      labels.push(grain === 'daily'
        ? `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`
        : grain === 'weekly'
          ? periodHeaderPrimary(pk, grain)
          : periodHeaderPrimary(pk, grain))
    }

    if (points.length < 2) return { points, projPoints, labels, trend: [], min: 0, max: 100 }
    const values = points.map(p => p.value)
    const allValues = [...values, ...projPoints.map(p => p.value)]
    const trend = computeMovingAverage(values, Math.min(3, values.length))
    const min = Math.min(...allValues, ...trend.filter(v => v != null))
    const max = Math.max(...allValues, ...trend.filter(v => v != null))
    const pad = Math.max((max - min) * 0.1, 1)
    return {
      points, projPoints, labels, trend,
      min: Math.max(0, Math.floor(min - pad)),
      max: Math.ceil(max + pad),
      isProjectable,
    }
  }, [lineData, chartKpi, grain])

  const { points, projPoints, labels, trend, min, max, isProjectable } = series
  if (points.length < 2) {
    return (
      <div className="px-4 py-3">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-[9px] text-gray-400 uppercase tracking-wider">Evolución</span>
          <select value={chartKpi} onChange={e => setChartKpi(e.target.value)}
            className="text-[9px] py-px px-1 rounded border border-gray-200 bg-white text-gray-600">
            {MATRIX_KPIS.map(k => <option key={k.key} value={k.key}>{k.label}</option>)}
          </select>
        </div>
        <p className="text-[9px] text-gray-400 py-1">Datos insuficientes para mostrar evolución.</p>
      </div>
    )
  }

  const w = 260, h = 90, padX = 32, padY = 10, padB = 14
  const plotW = w - padX - 6, plotH = h - padY - padB
  const range = max - min || 1
  const toX = (i) => padX + (points.length === 1 ? plotW / 2 : (i / (points.length - 1)) * plotW)
  const toY = (v) => padY + plotH - ((v - min) / range) * plotH

  const realLine = points.map((p, i) => `${toX(i)},${toY(p.value)}`).join(' ')
  const trendLine = trend.map((v, i) => v != null ? `${toX(i)},${toY(v)}` : null).filter(Boolean).join(' ')
  const projLine = isProjectable && projPoints.length >= 2
    ? projPoints.map((p, i) => {
        const idx = points.findIndex(rp => rp.period === p.period)
        return idx >= 0 ? `${toX(idx)},${toY(p.value)}` : null
      }).filter(Boolean).join(' ')
    : null

  const yTicks = []
  for (let t = 0; t <= 3; t++) {
    const val = min + (range * t / 3)
    yTicks.push({ y: toY(val), label: val >= 1000 ? `${(val/1000).toFixed(0)}K` : val.toFixed(0) })
  }

  return (
    <div className="px-3 py-2.5">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[9px] text-gray-400 uppercase tracking-wider shrink-0">Evolución</span>
        <select value={chartKpi} onChange={e => setChartKpi(e.target.value)}
          className="text-[9px] py-px px-1.5 rounded border border-gray-200 bg-white text-gray-600 outline-none">
          {MATRIX_KPIS.map(k => <option key={k.key} value={k.key}>{k.label}</option>)}
        </select>
      </div>
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ maxWidth: w }}>
        {yTicks.map((t, i) => (
          <g key={`g-${i}`}>
            <line x1={padX} y1={t.y} x2={w - 4} y2={t.y} stroke="#e5e7eb" strokeWidth={0.5} />
            <text x={padX - 3} y={t.y + 3} textAnchor="end" className="fill-gray-400" style={{ fontSize: '6px' }}>{t.label}</text>
          </g>
        ))}
        {labels.filter((_, i) => i % Math.max(1, Math.floor(labels.length / 5)) === 0 || i === labels.length - 1).map((l, i) => {
          const realIdx = labels.indexOf(l)
          if (realIdx < 0) return null
          return <text key={`xl-${i}`} x={toX(realIdx)} y={h - 3} textAnchor="middle" className="fill-gray-400" style={{ fontSize: '6px' }}>{l}</text>
        })}
        {trendLine && (
          <polyline points={trendLine} fill="none" stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="4,2" />
        )}
        {projLine && (
          <polyline points={projLine} fill="none" stroke="#8b5cf6" strokeWidth={1.5} strokeDasharray="3,1" />
        )}
        <polyline points={realLine} fill="none" stroke="#3b82f6" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle key={`d-${i}`} cx={toX(i)} cy={toY(p.value)} r={2.2} fill="#3b82f6" stroke="white" strokeWidth={1} />
        ))}
        {projPoints.filter(p => points.some(rp => rp.period === p.period)).map((p, i) => {
          const idx = points.findIndex(rp => rp.period === p.period)
          return <circle key={`pd-${i}`} cx={toX(idx)} cy={toY(p.value)} r={2.2} fill="#8b5cf6" stroke="white" strokeWidth={1} />
        })}
        {/* Legend */}
        <line x1={w - 85} y1={6} x2={w - 73} y2={6} stroke="#3b82f6" strokeWidth={2} />
        <text x={w - 71} y={8} className="fill-gray-600" style={{ fontSize: '6px' }}>Real</text>
        {projLine && (
          <>
            <line x1={w - 52} y1={6} x2={w - 40} y2={6} stroke="#8b5cf6" strokeWidth={1.5} strokeDasharray="3,1" />
            <text x={w - 38} y={8} className="fill-gray-600" style={{ fontSize: '6px' }}>Proy</text>
          </>
        )}
        {trendLine && (
          <>
            <line x1={projLine ? w - 24 : w - 36} y1={6} x2={projLine ? w - 12 : w - 24} y2={6} stroke="#f59e0b" strokeWidth={1.5} strokeDasharray="3,2" />
            <text x={projLine ? w - 10 : w - 22} y={8} className="fill-gray-600" style={{ fontSize: '6px' }}>Tend.</text>
          </>
        )}
      </svg>
    </div>
  )
}

function computeMovingAverage (values, windowSize) {
  const result = []
  for (let i = 0; i < values.length; i++) {
    const start = Math.max(0, i - Math.floor(windowSize / 2))
    const end = Math.min(values.length, i + Math.floor(windowSize / 2) + 1)
    const slice = values.slice(start, end)
    result.push(slice.reduce((a, b) => a + b, 0) / slice.length)
  }
  return result
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function _fmtCompact (v) {
  if (v == null) return '—'
  const n = Number(v)
  if (Math.abs(n) >= 1000000) return `${(n / 1000000).toFixed(2)}M`
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}K`
  return n.toFixed(n % 1 === 0 ? 0 : 2)
}

/**
 * FASE_KPI_CONSISTENCY — Sección "Tipo de KPI" en el drill.
 *
 * Muestra de forma explícita la naturaleza del KPI (aditivo, distinct, ratio,
 * derivado), su comparabilidad cross-grain y la nota recomendada por el
 * contrato. Esto evita que el usuario interprete sumas inválidas (ej. sumar
 * `active_drivers` semanales) o promedios de promedios (ej. `avg_ticket`).
 */
function KpiContractSection ({ kpiKey, kpiContract, labelCls, valueCls }) {
  if (!kpiKey) return null
  const contract = getKpiContract(kpiKey, kpiContract)
  if (!contract) return null
  const badge = getKpiComparabilityBadge(kpiKey, kpiContract)
  const note = getKpiComparabilityNote(kpiKey, kpiContract)
  // FASE_VALIDATION_FIX: decision readiness
  const decisionBadge = getKpiDecisionBadge(kpiKey, kpiContract)
  const decisionNote = getKpiDecisionNote(kpiKey, kpiContract)

  const toneCls = (tone) => {
    switch (tone) {
      case 'emerald': return 'bg-emerald-100 text-emerald-800 border-emerald-200'
      case 'sky':     return 'bg-sky-100 text-sky-800 border-sky-200'
      case 'amber':   return 'bg-amber-100 text-amber-800 border-amber-200'
      case 'red':     return 'bg-red-100 text-red-800 border-red-200'
      default:        return 'bg-slate-100 text-slate-700 border-slate-200'
    }
  }

  const ruleLabel = (() => {
    switch (contract.comparison_rule) {
      case 'exact_sum': return 'SUM(días del mes) = mensual'
      case 'same_formula_different_scope': return 'Misma fórmula, distinto scope'
      case 'not_directly_comparable': return 'No comparable por suma'
      default: return contract.comparison_rule || '—'
    }
  })()

  return (
    <div className="px-4 py-3 bg-slate-50/40">
      <h4 className="text-[10px] font-bold text-gray-500 uppercase tracking-wider mb-2">Tipo de KPI</h4>
      <div className="flex flex-wrap items-center gap-1.5 mb-2">
        {badge && (
          <span className={`inline-block px-1.5 py-px rounded text-[9px] font-bold border ${toneCls(badge.tone)}`}>
            {badge.label}
          </span>
        )}
        {decisionBadge && (
          <span
            className={`inline-block px-1.5 py-px rounded text-[9px] font-bold border ${toneCls(decisionBadge.tone)}`}
            title={decisionNote || undefined}
          >
            {decisionBadge.label}
          </span>
        )}
        <span className="text-[9px] text-slate-500">
          {contract.comparable_across_grains ? 'Comparable por scope' : 'No comparable por suma entre granos'}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        <span className={labelCls}>Regla</span>
        <span className={valueCls}>{ruleLabel}</span>
        {contract.allowed_for_drift_alerts === false && (
          <>
            <span className={labelCls}>Alertas aditivas</span>
            <span className="text-[10px] text-amber-700 font-semibold">No aplica — leer por scope</span>
          </>
        )}
      </div>
      {note && (
        <p className="mt-2 text-[10px] leading-snug text-slate-600">{note}</p>
      )}
      {decisionNote && (
        <p className="mt-1 text-[10px] leading-snug text-slate-500 italic border-l-2 border-slate-300 pl-1.5">
          {decisionNote}
        </p>
      )}
    </div>
  )
}
