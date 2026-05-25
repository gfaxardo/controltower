/**
 * OmniviewCommandHeader — Header de comando para Omniview Matrix.
 * Proporciona contexto operacional compacto encima de la matrix.
 * Motor: Control Foundation + Diagnostic Engine
 */
import OmniviewAttentionSummary from './OmniviewAttentionSummary'
import OmniviewModeSelector, { OMNIVIEW_MODES } from './OmniviewModeSelector'

const GRAIN_LABELS = { monthly: 'Mensual', weekly: 'Semanal', daily: 'Diario' }

export default function OmniviewCommandHeader({
  viewMode, grain, year, month,
  freshnessInfo, coverageSummary, matrixTrust,
  rows = [], compact = false,
  operationalMode = OMNIVIEW_MODES.OPERATIONAL,
  onOperationalModeChange,
  children,
  controls,
}) {
  const modeLabel = viewMode === 'projection' ? 'Projection' : 'Evolution'
  const grainLabel = GRAIN_LABELS[grain] || grain
  const periodLabel = grain === 'monthly' ? `${year}` : `${year}-${String(month || '').padStart(2, '0')}`
  const coveragePct = coverageSummary?.coverage_pct
  const isCoverageOk = coveragePct == null || coveragePct >= 92
  const trustStatus = matrixTrust?.trust_status
  const isTrustOk = trustStatus === 'ok' || !trustStatus
  const freshnessStatus = freshnessInfo?.status
  const isFreshnessOk = freshnessStatus === 'fresh' || freshnessStatus === 'fresca' || !freshnessStatus

  return (
    <div className="overflow-hidden shadow-sm" style={{
      borderRadius: 'var(--ct-radius-lg)',
      border: '1px solid var(--tw-bg-ct-border)',
      borderLeft: '3px solid var(--tw-bg-ct-accent)',
      background: 'var(--tw-bg-ct-card)',
    }}>
      {/* Command strip */}
      <div className="flex flex-wrap items-center gap-x-2_5 gap-y-0.5 px-3 text-xs text-ct-text3" style={{minHeight: 28}} role="status" aria-label="Omniview command header">
        {/* Mode selector — segmented control in header */}
        <OmniviewModeSelector mode={operationalMode} onChange={onOperationalModeChange} />

        <span className="text-ct-border/50">|</span>

        <span className="inline-flex items-center gap-1.5 font-semibold text-ct-text">
          <span className="text-ct-accent text-xs">{modeLabel}</span>
          <span className="text-xs font-normal text-ct-text3">{grainLabel} · {periodLabel}</span>
        </span>

        <span className="text-ct-border/50">|</span>

        {/* Health indicators */}
        <span className="inline-flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${isFreshnessOk ? 'bg-emerald-500' : freshnessStatus === 'stale' || freshnessStatus === 'parcial_esperada' ? 'bg-amber-500' : 'bg-red-500'}`} />
          <span className={isFreshnessOk ? '' : 'font-medium text-amber-700'}>
            {isFreshnessOk ? 'Fresh' : freshnessStatus || '—'}
          </span>
        </span>

        <span className="text-ct-border/50">|</span>

        <span className="inline-flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${isTrustOk ? 'bg-emerald-500' : trustStatus === 'warning' ? 'bg-amber-500' : 'bg-red-500'}`} />
          <span className={isTrustOk ? '' : 'font-medium text-amber-700'}>
            {isTrustOk ? 'Trust OK' : trustStatus || '—'}
          </span>
        </span>

        <span className="text-ct-border/50">|</span>

        <span className="inline-flex items-center gap-1">
          <span className={`w-1.5 h-1.5 rounded-full ${isCoverageOk ? 'bg-emerald-500' : 'bg-amber-500'}`} />
          <span className={isCoverageOk ? '' : 'font-medium text-amber-700'}>
            {coveragePct != null ? `Cov ${coveragePct}%` : 'Cov —'}
          </span>
        </span>

        {compact && (
          <>
            <span className="text-ct-border/50">|</span>
            <span className="text-ct-accent font-medium">Compact</span>
          </>
        )}

        {/* Attention summary — right-aligned */}
        <span className="inline-flex items-center gap-1" style={{marginLeft: 'auto'}}>
          <OmniviewAttentionSummary rows={rows} matrixTrust={matrixTrust} freshnessStatus={freshnessStatus} />
        </span>
      </div>
      {children && (
        <div className="px-3 py-1 border-t border-ct-border/30">
          {children}
        </div>
      )}
      {controls && (
        <div className="px-2 py-1.5 border-t border-ct-border/30">
          {controls}
        </div>
      )}
    </div>
  )
}
