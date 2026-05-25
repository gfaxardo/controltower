/**
 * DiagnosticBreakdownTooltip — Breakdown expandible vía tooltip.
 * 
 * Muestra el factor dominante visible, y al hacer hover revela:
 * - Factor dominante
 * - Factores secundarios (max 2)
 * - Señales crudas resumidas
 * 
 * Motor: Diagnostic Engine (temprano)
 */
import { useState, useMemo, useRef, useEffect } from 'react'
import { buildDiagnosticExplanation, summarizeDiagnosticSignals } from '../../utils/diagnosticExplanationEngine'
import DiagnosticFactorBadge from './DiagnosticFactorBadge'
import DecisionSeverityBadge from '../operational/DecisionSeverityBadge'

/**
 * @param {object} props
 * @param {object} props.signals - Operational signals
 * @param {boolean} [props.showSeverity] - Show severity dot (default: true)
 * @param {string} [props.className]
 */
export default function DiagnosticBreakdownTooltip({
  signals,
  showSeverity = true,
  className = '',
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  const explanation = useMemo(() => buildDiagnosticExplanation(signals), [signals])

  useEffect(() => {
    function handleClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
      return () => document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [open])

  const { severity, dominantFactor, secondaryFactors } = explanation
  if (!dominantFactor) return null
  if (severity === 'normal') return null

  const signalSummary = summarizeDiagnosticSignals(signals)

  return (
    <div ref={ref} className={`relative inline-flex items-center gap-1 ${className}`}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center gap-1 text-xs text-ct-text3 hover:text-ct-text transition-colors cursor-help"
        title="Diagnostic breakdown"
      >
        {showSeverity && <DecisionSeverityBadge severity={severity} compact />}
        <span className="font-medium underline decoration-dotted underline-offset-2">
          {severity === 'blocked' ? 'Blocked' : severity === 'critical' ? 'Critical' : severity === 'elevated' ? 'Elevated' : severity === 'warning' ? 'Warning' : 'Unknown'}
        </span>
      </button>

      {/* Tooltip */}
      {open && (
        <div className="absolute bottom-full left-0 mb-1 z-50 rounded-md border border-ct-border bg-ct-card p-3 shadow-lg min-w-[260px] max-w-[340px] text-left">
          <div className="flex items-center gap-2 mb-2">
            <DecisionSeverityBadge severity={severity} compact />
            <span className="text-xs font-semibold text-ct-text">
              {severity === 'blocked' ? 'Blocked' : severity === 'critical' ? 'Critical' : severity === 'elevated' ? 'Elevated' : 'Warning'}
            </span>
          </div>

          {/* Dominant */}
          <div className="mb-2">
            <span className="text-[10px] text-ct-text3 uppercase tracking-wider block mb-1">Primary cause</span>
            <DiagnosticFactorBadge factor={dominantFactor.factor} detail={dominantFactor.detail} />
          </div>

          {/* Secondary */}
          {secondaryFactors.length > 0 && (
            <div className="mb-2">
              <span className="text-[10px] text-ct-text3 uppercase tracking-wider block mb-1">Contributing</span>
              <div className="flex flex-col gap-0.5">
                {secondaryFactors.map((f, i) => (
                  <DiagnosticFactorBadge key={i} factor={f.factor} detail={f.detail} />
                ))}
              </div>
            </div>
          )}

          {/* Raw signals */}
          <div className="pt-2 border-t border-ct-border">
            <span className="text-[10px] text-ct-text3 uppercase tracking-wider block mb-1">Signals</span>
            <span className="text-[11px] text-ct-text2 leading-snug">{signalSummary}</span>
          </div>
        </div>
      )}
    </div>
  )
}
