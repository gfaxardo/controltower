import { useEffect, useMemo, useState } from 'react'
import { MATRIX_KPIS, fmtValue, fmtRaw, fmtDelta, signalColorForKpi, signalArrow, periodLabel, periodStateLabel, PERIOD_STATES, describeComparison } from './omniview/omniviewMatrixUtils.js'
import { resolveTrustIssueForSelection } from './omniview/trustInspectorDiagnostics.js'
import { logMatrixIssueAction } from '../services/api.js'

export default function BusinessSliceOmniviewInspector ({
  selection,
  grain,
  compact,
  onClose,
  insightForSelection,
  insightTransparency,
  periodStates,
  coverageSummary,
  matrixTrust,
  matrixMeta = null,
  onTrustStateRefresh,
}) {
  const w = compact ? 'w-80' : 'w-[25rem]'
  const trustIssue = useMemo(
    () => resolveTrustIssueForSelection(matrixTrust, selection, grain),
    [matrixTrust, selection, grain]
  )
  const sectionIds = useMemo(() => {
    const base = String(selection?.id || 'inspector').replace(/[^a-zA-Z0-9_-]/g, '-')
    return {
      period: `${base}-period`,
      diagnosis: `${base}-diagnosis`,
      evidence: `${base}-evidence`,
      raw: `${base}-raw`,
      unmapped: `${base}-unmapped`,
      history: `${base}-history`,
    }
  }, [selection?.id])
  const [copiedQuery, setCopiedQuery] = useState(null)
  const [actionBusy, setActionBusy] = useState(null)

  useEffect(() => {
    setCopiedQuery(null)
  }, [selection?.id])

  if (!selection) {
    return (
      <aside className={`${w} shrink-0 rounded-lg border border-gray-200 bg-white shadow-sm self-start sticky top-2`}>
        <div className="px-4 py-3 border-b border-gray-100">
          <h3 className="text-xs font-bold text-gray-600 uppercase tracking-wide">Inspector</h3>
        </div>
        <div className="p-4">
          <p className="text-[11px] text-gray-400 leading-relaxed">
            Click en una celda de la Matrix para abrir un diagnóstico operativo o el detalle normal de la selección.
          </p>
          <div className="mt-4 flex items-center justify-center">
            <div className="w-12 h-12 rounded-full bg-gray-50 flex items-center justify-center">
              <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" />
              </svg>
            </div>
          </div>
        </div>
      </aside>
    )
  }

  const { lineData, periodDeltas, period, raw, kpiKey: selectedKpiKey } = selection
  const label = (grain === 'daily' && raw?.day_label) ? String(raw.day_label) : periodLabel(period, grain)
  const selectedKpi = MATRIX_KPIS.find((kpi) => kpi.key === selectedKpiKey) || MATRIX_KPIS[0]
  const ins = insightForSelection
  const pState = periodStates?.get(period)
  const periodEngineRec = useMemo(
    () => (matrixMeta?.period_states || []).find((r) => r.period_key === period) || null,
    [matrixMeta, period]
  )
  const hasPartialDelta = Object.values(periodDeltas || {}).some((d) => d?.isPartialComparison)
  const comparisonDelta = periodDeltas?.[selectedKpiKey] || Object.values(periodDeltas || {}).find(Boolean)
  const comparisonDesc = describeComparison(comparisonDelta, grain)
  const hasEquivalentComparison = !!comparisonDelta?.is_equivalent_comparison

  const handleCopyQuery = async (label, sql) => {
    try {
      if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(sql)
        setCopiedQuery(label)
      }
    } catch {}
  }

  const scrollToSection = (sectionKey) => {
    const el = typeof document !== 'undefined' ? document.getElementById(sectionIds[sectionKey]) : null
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const handleActionLog = async (actionStatus) => {
    if (!trustIssue?.actionPayload) return
    try {
      setActionBusy(actionStatus)
      await logMatrixIssueAction({
        issue: trustIssue.actionPayload,
        action_status: actionStatus,
      })
      await onTrustStateRefresh?.()
    } catch {
      // noop: mantener inspector usable aunque falle el tracking
    } finally {
      setActionBusy(null)
    }
  }

  const modeBadgeCls = trustIssue?.decisionMode === 'BLOCKED'
    ? 'bg-rose-700 text-white'
    : trustIssue?.decisionMode === 'CAUTION'
      ? 'bg-amber-700 text-white'
      : 'bg-emerald-700 text-white'

  return (
    <aside className={`${w} shrink-0 rounded-lg border ${trustIssue ? 'border-slate-300' : ins ? 'border-red-200' : 'border-blue-200'} bg-white shadow-md self-start sticky top-2 overflow-hidden`}>
      <div className="bg-slate-900 text-white px-3 py-2 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">Inspector</span>
            {trustIssue && (
              <span className={`px-1.5 py-px rounded text-[9px] font-bold uppercase tracking-wide ${modeBadgeCls}`}>
                {trustIssue.decisionMode}
              </span>
            )}
          </div>
          <div className="text-[12px] font-bold truncate mt-0.5">{raw?.city || 'Global'} · {lineData.business_slice_name}</div>
          <div className="text-[10px] text-slate-400 truncate">
            {label} · {selectedKpi.label}
            {lineData.fleet_display_name !== '—' && ` · ${lineData.fleet_display_name}`}
            {lineData.is_subfleet && ` · Sub: ${lineData.subfleet_name}`}
          </div>
        </div>
        <button type="button" onClick={onClose} className="text-slate-400 hover:text-white text-sm leading-none shrink-0" title="Cerrar">×</button>
      </div>

      <div className="px-3 py-2 bg-slate-50 border-b border-slate-200 space-y-2">
        <div id={sectionIds.period} className="flex flex-wrap items-center gap-1.5">
          <MiniPill label="Ciudad" value={raw?.city || 'Global'} />
          <MiniPill label="Línea" value={lineData.business_slice_name} />
          <MiniPill label="Periodo" value={label} />
          <MiniPill label="Métrica" value={selectedKpi.label} />
          {pState && pState !== PERIOD_STATES.CLOSED && (
            <MiniPill label="Estado" value={periodStateLabel(pState)} />
          )}
        </div>

        {periodEngineRec && (
          <div className="rounded border border-slate-200 bg-white px-2 py-1.5 text-[9px] text-slate-700 leading-snug">
            <span className="font-semibold text-slate-600">Estado de período · </span>
            {periodStateLabel(periodEngineRec.period_status) || periodEngineRec.period_status}
            {periodEngineRec.expected_through_date && (
              <> · esperado ≤ {periodEngineRec.expected_through_date}</>
            )}
            {periodEngineRec.actual_max_date && (
              <> · max en período (day_fact) {periodEngineRec.actual_max_date_in_period || periodEngineRec.actual_max_date}</>
            )}
            {periodEngineRec.expected_end_of_period && (
              <> · fin esperado {periodEngineRec.expected_end_of_period}</>
            )}
            {periodEngineRec.is_comparable === false && (
              <span className="text-amber-700 font-medium"> · comparabilidad limitada</span>
            )}
            {periodEngineRec.completeness_ratio != null && (
              <> · completitud ~{(Number(periodEngineRec.completeness_ratio) * 100).toFixed(0)}%</>
            )}
          </div>
        )}

        {pState === PERIOD_STATES.STALE && (
          <div className="text-[9px] text-amber-900 bg-amber-50 rounded px-2 py-0.5 border border-amber-200">
            Data desactualizada: los deltas no son definitivos (la carga no cubre el fin esperado del período).
          </div>
        )}

        {matrixTrust?.executive?.playbook && (
          <div className="rounded border border-emerald-200 bg-emerald-50/80 px-2 py-1.5 text-[9px] text-emerald-950 leading-snug">
            <span className="font-semibold text-emerald-900">Playbook · </span>
            {matrixTrust.executive.playbook.recommended_action || matrixTrust.executive.playbook.operational_meaning}
            {matrixTrust.executive.playbook.suggested_process && (
              <div className="text-emerald-800/90 mt-0.5">{matrixTrust.executive.playbook.suggested_process}</div>
            )}
            {matrixTrust.executive.playbook.query_template && (
              <button
                type="button"
                className="mt-1 text-[9px] text-emerald-950 underline"
                onClick={() => handleCopyQuery('playbook', matrixTrust.executive.playbook.query_template)}
              >
                {copiedQuery === 'playbook' ? 'Copiado' : 'Copiar plantilla SQL'}
              </button>
            )}
          </div>
        )}

        {trustIssue ? (
          <div className="rounded-md border border-slate-200 bg-white px-2.5 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Estado y confianza</span>
              <span className={`px-1.5 py-px rounded text-[9px] font-bold uppercase ${trustIssue.severity === 'blocked' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'}`}>
                {trustIssue.code}
              </span>
              <span className="text-[11px] font-semibold text-slate-800">Conf. {trustIssue.confidence?.score ?? '—'}</span>
            </div>
            <div className="mt-1.5 grid grid-cols-3 gap-1.5 text-[10px]">
              <ScoreCell label="Coverage" value={trustIssue.confidence?.coverage} />
              <ScoreCell label="Freshness" value={trustIssue.confidence?.freshness} />
              <ScoreCell label="Consistency" value={trustIssue.confidence?.consistency} />
            </div>
          </div>
        ) : (
          <>
            {hasEquivalentComparison && comparisonDesc && (
              <div className="text-[9px] text-blue-700 bg-blue-50 rounded px-2 py-0.5 border border-blue-100">
                {comparisonDesc}
              </div>
            )}
            {!hasEquivalentComparison && hasPartialDelta && (
              <div className="text-[9px] text-blue-600 bg-blue-50 rounded px-2 py-0.5 border border-blue-100">
                Comparativo parcial vs cerrado — deltas orientativos
              </div>
            )}
          </>
        )}

        {trustIssue && (
          <div className="flex flex-wrap gap-1">
            <NavBtn onClick={() => scrollToSection('diagnosis')}>Diagnóstico</NavBtn>
            <NavBtn onClick={() => scrollToSection('evidence')}>Evidencia</NavBtn>
            <NavBtn onClick={() => scrollToSection('raw')}>Raw</NavBtn>
            {coverageSummary && <NavBtn onClick={() => scrollToSection('unmapped')}>Unmapped</NavBtn>}
            {!!matrixTrust?.trust_history_recent?.length && <NavBtn onClick={() => scrollToSection('history')}>Trust history</NavBtn>}
          </div>
        )}
      </div>

      {trustIssue ? (
        <div className="p-3 space-y-2.5 max-h-[68vh] overflow-y-auto bg-white">
          <SectionCard id={sectionIds.diagnosis} title="Diagnóstico principal" accent={trustIssue.severity}>
            <div className="space-y-2">
              {(trustIssue.earlyWarnings || []).length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {trustIssue.earlyWarnings.map((warn) => (
                    <span key={warn.type} className="px-1.5 py-px rounded border border-amber-200 bg-amber-50 text-[9px] font-medium text-amber-800">
                      Early warning: {warn.message}
                    </span>
                  ))}
                </div>
              )}
              <div>
                <h4 className="text-[12px] font-semibold text-slate-900">{trustIssue.title}</h4>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-600">{trustIssue.summary}</p>
              </div>
              {trustIssue.hardCapReason && (
                <div className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-[10px] text-amber-900">
                  El score quedó penalizado por este hallazgo: {trustIssue.hardCapReason}
                </div>
              )}
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Causas probables</p>
                <ul className="mt-1 space-y-1 text-[11px] text-slate-600">
                  {trustIssue.causes.map((cause) => <li key={cause}>• {cause}</li>)}
                </ul>
              </div>
            </div>
          </SectionCard>

          <SectionCard id={sectionIds.evidence} title="Evidencia" accent="neutral">
            <div className="grid grid-cols-2 gap-1.5">
              {trustIssue.evidence.map((item) => (
                <div key={`${item.label}-${item.value}`} className="rounded border border-slate-200 bg-slate-50 px-2 py-1.5">
                  <div className="text-[9px] uppercase tracking-wide text-slate-400">{item.label}</div>
                  <div className="text-[11px] font-semibold text-slate-800 break-all">{item.value}</div>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Acción sugerida" accent={trustIssue.severity}>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">Prioridad</span>
                <span className={`px-1.5 py-px rounded text-[9px] font-bold ${trustIssue.priority === 'Alta' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'}`}>
                  {trustIssue.priority}
                </span>
              </div>
              <p className="text-[11px] text-slate-800 font-medium">{trustIssue.action.primary}</p>
              <p className="text-[10px] text-slate-500 leading-relaxed">{trustIssue.action.process}</p>
              <div className="flex flex-wrap gap-1 pt-1">
                <button
                  type="button"
                  onClick={() => handleActionLog('executed')}
                  disabled={actionBusy != null}
                  className="px-2 py-0.5 rounded border border-slate-200 bg-white text-[10px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
                >
                  {actionBusy === 'executed' ? 'Registrando…' : 'Registrar acción ejecutada'}
                </button>
                <button
                  type="button"
                  onClick={() => handleActionLog('resolved')}
                  disabled={actionBusy != null}
                  className="px-2 py-0.5 rounded border border-emerald-200 bg-emerald-50 text-[10px] font-medium text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
                >
                  {actionBusy === 'resolved' ? 'Registrando…' : 'Marcar como resuelto'}
                </button>
              </div>
            </div>
          </SectionCard>

          {trustIssue.issueHistory && (
            <SectionCard title="Issue history" accent="neutral">
              <div className="grid grid-cols-3 gap-1.5">
                <MiniStat label="Primera aparición" value={String(trustIssue.issueHistory.first_seen || 'actual').slice(0, 10)} />
                <MiniStat label="Ocurrencias" value={String(trustIssue.issueHistory.occurrences || 1)} />
                <MiniStat label="Tendencia" value={String(trustIssue.issueHistory.trend || 'new')} />
              </div>
              {!!trustIssue.issueHistory.timeline?.length && (
                <div className="mt-2 space-y-1">
                  {trustIssue.issueHistory.timeline.slice(-4).map((row) => (
                    <div key={`${row.evaluated_at}-${row.period_key}`} className="rounded border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] text-slate-600">
                      {String(row.evaluated_at || '').slice(0, 10)} · {row.decision_mode} · conf {row.confidence_score}
                    </div>
                  ))}
                </div>
              )}
            </SectionCard>
          )}

          {trustIssue.issueCluster && (
            <SectionCard title="Issue clustering" accent="neutral">
              <div className="space-y-1">
                <p className="text-[11px] font-medium text-slate-800">{trustIssue.issueCluster.cluster_label}</p>
                <p className="text-[10px] text-slate-500 leading-relaxed">{trustIssue.issueCluster.cluster_description}</p>
                <div className="grid grid-cols-3 gap-1.5">
                  <MiniStat label="Issues" value={String(trustIssue.issueCluster.issue_count || 0)} />
                  <MiniStat label="Impacto comb." value={`${Number(trustIssue.issueCluster.combined_impact_pct || 0).toFixed(1)}%`} />
                  <MiniStat label="Peor estado" value={String(trustIssue.issueCluster.worst_status || 'warning')} />
                </div>
              </div>
            </SectionCard>
          )}

          <SectionCard title="Query sugerida" accent="neutral">
            <div className="space-y-2">
              {trustIssue.queries.map((q) => (
                <div key={q.label} className="rounded border border-slate-200 bg-slate-50">
                  <div className="flex items-center justify-between px-2 py-1 border-b border-slate-200">
                    <span className="text-[10px] font-semibold text-slate-700">{q.label}</span>
                    <button
                      type="button"
                      onClick={() => handleCopyQuery(q.label, q.sql)}
                      className="text-[10px] text-slate-500 hover:text-slate-800"
                    >
                      {copiedQuery === q.label ? 'Copiada' : 'Copiar SQL'}
                    </button>
                  </div>
                  <pre className="p-2 text-[10px] leading-relaxed text-slate-700 whitespace-pre-wrap overflow-x-auto">{q.sql}</pre>
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard id={sectionIds.raw} title="Raw" accent="neutral">
            <RawSnapshot raw={raw} selectedKpiKey={selectedKpiKey} />
          </SectionCard>

          {coverageSummary && (
            <SectionCard id={sectionIds.unmapped} title="Unmapped / cobertura" accent="neutral">
              <div className="grid grid-cols-2 gap-1.5">
                <MiniStat label="Cobertura" value={`${coverageSummary.coverage_pct}%`} />
                <MiniStat label="No mapeados" value={coverageSummary.unmapped_trips?.toLocaleString?.() || String(coverageSummary.unmapped_trips ?? '—')} />
                <MiniStat label="Viajes total" value={coverageSummary.total_trips?.toLocaleString?.() || String(coverageSummary.total_trips ?? '—')} />
                <MiniStat label="Mapped" value={coverageSummary.mapped_trips?.toLocaleString?.() || String(coverageSummary.mapped_trips ?? '—')} />
              </div>
            </SectionCard>
          )}

          {!!matrixTrust?.trust_history_recent?.length && (
            <SectionCard id={sectionIds.history} title="Trust history" accent="neutral">
              <div className="space-y-1">
                {matrixTrust.trust_history_recent.slice(0, 6).map((row) => (
                  <div key={`${row.id}-${row.evaluated_at}`} className="rounded border border-slate-200 px-2 py-1.5 bg-slate-50">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-semibold text-slate-800">{row.period_key}</span>
                      <span className="text-[10px] text-slate-500">{row.decision_mode} · {row.confidence_score}</span>
                    </div>
                    <div className="mt-0.5 text-[9px] text-slate-500">
                      Cob. {Number(row.coverage_score ?? 0).toFixed(0)} · Fresc. {Number(row.freshness_score ?? 0).toFixed(0)} · Consist. {Number(row.consistency_score ?? 0).toFixed(0)}
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          {!!trustIssue.actionHistory?.length && (
            <SectionCard title="Action tracking" accent="neutral">
              <div className="space-y-1">
                {trustIssue.actionHistory.slice(0, 5).map((row) => (
                  <div key={`${row.id}-${row.executed_at}`} className="rounded border border-slate-200 px-2 py-1.5 bg-slate-50">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] font-semibold text-slate-800">{row.action_status}</span>
                      <span className="text-[9px] text-slate-500">{String(row.executed_at || '').slice(0, 16).replace('T', ' ')}</span>
                    </div>
                    {row.notes && <div className="mt-0.5 text-[9px] text-slate-500">{row.notes}</div>}
                  </div>
                ))}
              </div>
            </SectionCard>
          )}
        </div>
      ) : (
        <>
          {ins && <InsightBanner insight={ins} transparency={insightTransparency} />}

          <SparklineBar lineData={lineData} kpiKey={selectedKpiKey} />

          <div className={`${compact ? 'p-2 space-y-1' : 'p-3 space-y-1.5'} max-h-[50vh] overflow-y-auto`}>
            {MATRIX_KPIS.map((kpi) => {
              const d = periodDeltas?.[kpi.key]
              const currentVal = d?.value
              const color = d ? signalColorForKpi(d.signal, kpi.key) : '#9ca3af'
              const arrow = d ? signalArrow(d.signal) : '—'
              const deltaText = d ? fmtDelta(d) : null
              const isHighlighted = selectedKpiKey === kpi.key
              const padCard = compact ? 'px-2 py-1.5' : 'px-2.5 py-2'

              return (
                <div key={kpi.key} className={`rounded-md border ${padCard} transition-colors ${
                  isHighlighted ? 'border-blue-300 bg-blue-50/60 shadow-sm' : 'border-gray-100 bg-gray-50/20 hover:bg-gray-50/50'
                }`}>
                  <div className="flex items-center justify-between mb-0.5">
                    <span className={`text-[9px] font-semibold uppercase tracking-wide ${isHighlighted ? 'text-blue-600' : 'text-gray-500'}`}>{kpi.label}</span>
                    {deltaText && <span className="text-[10px] font-bold" style={{ color }}>{arrow} {deltaText}</span>}
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className={`${compact ? 'text-base' : 'text-lg'} font-bold text-gray-900 leading-tight`}>{fmtValue(currentVal, kpi.key)}</span>
                    {d?.previous != null && (
                      <span className="text-[9px] text-gray-400">
                        {d.is_equivalent_comparison ? 'base eq:' : 'ant:'} {fmtRaw(d.previous)}
                      </span>
                    )}
                  </div>
                  {(d?.delta_abs_pp != null || d?.delta_pct != null) && (
                    <div className="mt-0.5 flex gap-3 text-[9px] text-gray-400">
                      {d?.delta_abs_pp != null && <span>Δ pp: {d.delta_abs_pp.toFixed(2)}</span>}
                      {d?.delta_pct != null && <span>Δ: {(d.delta_pct * 100).toFixed(1)}%</span>}
                    </div>
                  )}
                </div>
              )
            })}
          </div>

          <div className="px-3 py-2 bg-gray-50 border-t border-gray-200 space-y-0.5">
            <p className="text-[9px] font-bold text-gray-400 uppercase tracking-wide">Trazabilidad</p>
            <MetaRow label="Fuente" value="real_business_slice_month_fact" />
            {raw?.country && <MetaRow label="País" value={raw.country} />}
            {raw?.city && <MetaRow label="Ciudad" value={raw.city} />}
            {raw?.is_subfleet != null && <MetaRow label="Subflota" value={raw.is_subfleet ? 'Sí' : 'No'} />}
            <MetaRow label="Grano" value={grain} />
            {pState && <MetaRow label="Estado periodo" value={periodStateLabel(pState)} />}
            {comparisonDelta?.comparison_mode && <MetaRow label="Modo comparativo" value={comparisonDelta.comparison_mode} />}
            {comparisonDelta?.current_cutoff_date && <MetaRow label="Corte actual" value={comparisonDelta.current_cutoff_date} />}
            {comparisonDelta?.previous_equivalent_cutoff_date && <MetaRow label="Corte equivalente" value={comparisonDelta.previous_equivalent_cutoff_date} />}
            {coverageSummary && coverageSummary.total_trips > 0 && (
              <>
                <MetaRow label="Cobertura" value={`${coverageSummary.coverage_pct}%`} />
                <MetaRow label="No mapeados" value={coverageSummary.unmapped_trips.toLocaleString()} />
              </>
            )}
          </div>
        </>
      )}
    </aside>
  )
}

// ─── Insight banner in inspector ────────────────────────────────────────────
function InsightBanner ({ insight, transparency }) {
  const isCritical = insight.severity === 'critical'
  const bg = isCritical ? 'bg-red-50' : 'bg-amber-50'
  const border = isCritical ? 'border-red-200' : 'border-amber-200'
  const badgeBg = isCritical ? 'bg-red-600' : 'bg-amber-500'
  const textColor = isCritical ? 'text-red-800' : 'text-amber-800'

  const fmtPct = (v) => v != null ? `${(v * 100).toFixed(1)}%` : null
  const fmtDelta = (s) => {
    if (s.metric === 'cancel_rate_pct' && s.delta_abs_pp != null) return `${(s.delta_abs_pp / 100).toFixed(1)} pp`
    return fmtPct(s.delta_pct) || '—'
  }

  return (
    <div className={`${bg} border-b ${border} px-3 py-2 space-y-1`}>
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className={`${badgeBg} text-white px-1.5 py-px rounded text-[8px] font-bold uppercase`}>
          {insight.severity}
        </span>
        {insight.preliminary && (
          <span className="bg-blue-100 text-blue-700 px-1 py-px rounded text-[7px] font-bold uppercase">
            Preliminar
          </span>
        )}
        <span className={`text-[10px] font-bold ${textColor}`}>Insight detectado</span>
        {insight.groupedCount > 1 && (
          <span className="text-[8px] text-gray-500 bg-white/70 px-1 rounded border border-gray-200">
            {insight.groupedCount} señales agrupadas
          </span>
        )}
      </div>

      <div className={`text-[11px] font-semibold ${textColor} leading-tight`}>
        {insight.metricLabel}: {fmtPct(insight.delta_pct) || (insight.delta_abs_pp != null ? `${(insight.delta_abs_pp / 100).toFixed(1)} pp` : '—')}
      </div>

      {(insight.secondarySignals || []).length > 0 && (
        <ul className="text-[9px] text-gray-600 space-y-0.5 pl-2 list-disc">
          {(insight.secondarySignals || []).map((s) => (
            <li key={s.metric}>
              <span className="font-medium">{s.metricLabel}</span> ({s.severity}): {fmtDelta(s)}
            </li>
          ))}
        </ul>
      )}

      <div className="text-[10px] text-gray-600 leading-tight">
        <span className="font-medium">Causa (heurística):</span> {insight.explanation.cause}
      </div>

      <div className="text-[10px] text-gray-600 leading-tight">
        <span className="font-medium">Acción sugerida:</span> {insight.action.action}
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[9px] text-gray-400 mt-0.5">
        {insight.explanation.drivers_delta_pct != null && (
          <span>Conductores: {fmtPct(insight.explanation.drivers_delta_pct)}</span>
        )}
        {insight.explanation.trips_delta_pct != null && (
          <span>Viajes: {fmtPct(insight.explanation.trips_delta_pct)}</span>
        )}
        {insight.explanation.ticket_delta_pct != null && (
          <span>Ticket: {fmtPct(insight.explanation.ticket_delta_pct)}</span>
        )}
      </div>

      {transparency?.disclaimer && (
        <p className="text-[8px] text-gray-400 leading-snug border-t border-gray-200/60 pt-1 mt-1 italic">
          {transparency.disclaimer}
        </p>
      )}
    </div>
  )
}

function SparklineBar ({ lineData, kpiKey }) {
  const values = useMemo(() => {
    if (!lineData?.periods) return []
    const vals = []
    for (const pk of [...lineData.periods.keys()].sort()) {
      const v = lineData.periods.get(pk)?.metrics?.[kpiKey]
      vals.push(v != null ? Number(v) : null)
    }
    return vals
  }, [lineData, kpiKey])

  const valid = values.filter((v) => v != null)
  if (valid.length < 2) return null
  const max = Math.max(...valid), min = Math.min(...valid), range = max - min || 1
  const w = 200, h = 28, padY = 3
  const points = values.map((v, i) => {
    if (v == null) return null
    const x = values.length === 1 ? w / 2 : (i / (values.length - 1)) * w
    const y = padY + (h - 2 * padY) - ((v - min) / range) * (h - 2 * padY)
    return [x, y]
  }).filter(Boolean)
  const polyline = points.map((p) => p.join(',')).join(' ')
  const last = points[points.length - 1]

  return (
    <div className="px-3 py-1.5 border-b border-gray-100 flex items-center gap-2">
      <span className="text-[9px] text-gray-400 uppercase tracking-wider shrink-0">Tendencia</span>
      <svg width={w} height={h} className="flex-1" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <polyline points={polyline} fill="none" stroke="#3b82f6" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
        {last && <circle cx={last[0]} cy={last[1]} r={2.5} fill="#3b82f6" />}
      </svg>
    </div>
  )
}

function SectionCard ({ id, title, accent = 'neutral', children }) {
  const cls = accent === 'blocked'
    ? 'border-rose-200 bg-rose-50/40'
    : accent === 'warning'
      ? 'border-amber-200 bg-amber-50/40'
      : 'border-slate-200 bg-white'
  return (
    <section id={id} className={`rounded-lg border ${cls} px-3 py-2`}>
      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500 mb-1.5">{title}</div>
      {children}
    </section>
  )
}

function MiniPill ({ label, value }) {
  return (
    <span className="inline-flex items-center gap-1 rounded border border-slate-200 bg-white px-1.5 py-0.5">
      <span className="text-[9px] uppercase tracking-wide text-slate-400">{label}</span>
      <span className="text-[10px] font-medium text-slate-700">{value}</span>
    </span>
  )
}

function ScoreCell ({ label, value }) {
  return (
    <div className="rounded border border-slate-200 bg-slate-50 px-2 py-1">
      <div className="text-[9px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-[11px] font-semibold text-slate-800">{value != null ? Number(value).toFixed(0) : '—'}</div>
    </div>
  )
}

function MiniStat ({ label, value }) {
  return (
    <div className="rounded border border-slate-200 bg-slate-50 px-2 py-1.5">
      <div className="text-[9px] uppercase tracking-wide text-slate-400">{label}</div>
      <div className="text-[11px] font-semibold text-slate-800">{value}</div>
    </div>
  )
}

function NavBtn ({ children, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="px-2 py-0.5 rounded border border-slate-200 bg-white text-[10px] font-medium text-slate-600 hover:bg-slate-50"
    >
      {children}
    </button>
  )
}

function RawSnapshot ({ raw, selectedKpiKey }) {
  if (!raw) {
    return <p className="text-[10px] text-slate-400">Sin snapshot raw disponible para esta selección.</p>
  }
  const keys = [
    'country',
    'city',
    'business_slice_name',
    'fleet_display_name',
    selectedKpiKey,
    'trips_completed',
    'revenue_yego_net',
    'active_drivers',
    'cancel_rate_pct',
  ].filter(Boolean)
  const seen = new Set()
  const entries = keys
    .filter((key) => !seen.has(key) && seen.add(key) && raw[key] != null)
    .map((key) => [key, raw[key]])

  return (
    <div className="space-y-1">
      {entries.map(([key, value]) => (
        <div key={key} className="flex justify-between gap-3 text-[10px]">
          <span className="text-slate-400">{key}</span>
          <span className="text-slate-700 font-mono break-all text-right">{String(value)}</span>
        </div>
      ))}
    </div>
  )
}

function MetaRow ({ label, value }) {
  return (
    <div className="flex justify-between text-[9px]">
      <span className="text-gray-400">{label}</span>
      <span className="text-gray-600 font-mono truncate max-w-[140px]" title={String(value)}>{String(value)}</span>
    </div>
  )
}
