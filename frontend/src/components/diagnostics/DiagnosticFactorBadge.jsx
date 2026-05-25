/**
 * DiagnosticFactorBadge — Badge compacto de factor diagnóstico.
 * Muestra UN factor causal en formato "label: detail".
 * 
 * Motor: Diagnostic Engine (temprano)
 */
import { FACTOR_LABEL } from '../../utils/diagnosticExplanationEngine'

const SEVERITY_FACTOR_STYLE = {
  freshness_degraded: 'bg-red-50 text-red-800 border-red-200',
  trust_degraded: 'bg-red-50 text-red-800 border-red-200',
  missing_serving: 'bg-red-50 text-red-800 border-red-200',
  blocked_comparison: 'bg-red-50 text-red-800 border-red-200',
  missing_comparable: 'bg-amber-50 text-amber-800 border-amber-200',
  missing_plan: 'bg-amber-50 text-amber-800 border-amber-200',
  projection_missing: 'bg-amber-50 text-amber-800 border-amber-200',
  severe_gap: 'bg-red-50 text-red-700 border-red-100',
  unit_alert_triggered: 'bg-red-50 text-red-700 border-red-100',
  sustained_negative: 'bg-amber-50 text-amber-700 border-amber-100',
  weekly_deterioration: 'bg-amber-50/50 text-amber-600 border-amber-100',
  monthly_deterioration: 'bg-amber-50/50 text-amber-600 border-amber-100',
  confidence_degraded: 'bg-amber-50 text-amber-700 border-amber-100',
  stale_data: 'bg-amber-50 text-amber-700 border-amber-100',
  config_incomplete: 'bg-blue-50 text-blue-700 border-blue-100',
  data_incomplete: 'bg-amber-50 text-amber-700 border-amber-100',
  attainment_gap: 'bg-amber-50/50 text-amber-600 border-amber-100',
  insufficient_signal: 'bg-gray-50 text-gray-500 border-gray-200',
}

/**
 * @param {object} props
 * @param {string} props.factor - DIAGNOSTIC_FACTOR key
 * @param {string} [props.detail] - Detail text
 * @param {boolean} [props.showDetail] - Show detail text (default: true)
 * @param {string} [props.className]
 */
export default function DiagnosticFactorBadge({
  factor,
  detail,
  showDetail = true,
  className = '',
}) {
  if (!factor) return null

  const label = FACTOR_LABEL[factor] || factor
  const style = SEVERITY_FACTOR_STYLE[factor] || 'bg-gray-50 text-gray-500 border-gray-200'

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-px rounded border text-[11px] font-medium ${style} ${className}`}
      title={detail || undefined}
    >
      {label}
      {showDetail && detail && (
        <span className="opacity-70 font-normal truncate max-w-[160px]">: {detail}</span>
      )}
    </span>
  )
}
