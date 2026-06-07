import FreshnessBadge from './FreshnessBadge.jsx'
import ExplainabilityTooltip from './ExplainabilityTooltip.jsx'
import { getStatusSemantic, getAlertSeveritySemantic } from '../design/semanticRegistry.js'

export function formatNum(n) { if (n == null) return '—'; const num = Number(n); if (isNaN(num)) return '—'; return num.toLocaleString('es-PE') }

export function LoadingState({ text = 'Cargando...', showDelay = false }) {
  // Show immediately for first load, after 2s delay for subsequent loads
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#06244a] mx-auto mb-3" />
      <p className="text-sm text-gray-400">{text}</p>
    </div>
  )
}

export function ErrorState({ message = 'Error al cargar', onRetry, remediation }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <svg className="w-10 h-10 text-red-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
      </svg>
      <p className="text-sm font-medium text-red-600">{message}</p>
      {remediation && <p className="text-xs text-red-400 mt-1 max-w-xs">{remediation}</p>}
      {onRetry && <button onClick={onRetry} className="mt-3 text-xs text-[#06244a] underline">Reintentar</button>}
    </div>
  )
}

export function EmptyState({ title = 'Sin datos', message = '', remediation, onAction }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <svg className="w-10 h-10 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
      </svg>
      <p className="text-sm font-medium text-gray-500">{title}</p>
      {message && <p className="text-xs text-gray-400 mt-1 max-w-xs">{message}</p>}
      {remediation && <p className="text-xs text-blue-500 mt-1 max-w-xs">{remediation}</p>}
      {onAction && <button onClick={onAction} className="mt-3 text-xs text-[#06244a] underline">{onAction.label || 'Accion'}</button>}
    </div>
  )
}

export function StaleDataBanner({ freshness, className = '' }) {
  if (!freshness) return null
  const status = freshness.status
  if (status === 'FRESH' || !status) return null
  const s = status === 'STALE' ? { bg: 'bg-red-50 border-red-200', text: 'text-red-700' }
    : status === 'WARNING' ? { bg: 'bg-yellow-50 border-yellow-200', text: 'text-yellow-700' }
    : { bg: 'bg-gray-50 border-gray-200', text: 'text-gray-500' }
  return (
    <div className={`${s.bg} border ${s.text} rounded-lg p-2 text-xs ${className}`}>
      {status === 'STALE' && `Datos desactualizados (${freshness.age_minutes || '?'}min). `}
      {status === 'WARNING' && `Datos cerca del umbral. `}
      {status === 'UNKNOWN' && `Timestamp no disponible. `}
      {freshness.remediation && <span>{freshness.remediation}</span>}
    </div>
  )
}

export function SectionLoadingFallback({ isLoading, error, data, children, emptyMessage, errorMessage }) {
  if (isLoading && !data) return <LoadingState text="Cargando..." />
  if (error) return <ErrorState message={errorMessage || error} />
  if (!data && !isLoading) return <EmptyState title="Sin datos" message={emptyMessage} />
  return children
}

export function MetricCard({ label, value, color = '#1a56db', subtitle, tooltip, explainability }) {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 relative group" style={{ borderTopWidth: 3, borderTopColor: color }} title={tooltip || ''}>
      <div className="flex items-center gap-1">
        <span className="text-xs text-gray-400 uppercase tracking-wide">{label}</span>
        <ExplainabilityTooltip explainability={explainability} />
      </div>
      <span className="text-2xl font-bold text-gray-800 mt-1 block">{value}</span>
      {subtitle != null && subtitle !== '' && <span className="text-xs text-gray-400 mt-1 block">{subtitle}</span>}
    </div>
  )
}

export function SectionCard({ title, color = '#1a56db', children, badge, freshness }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-50 flex items-center gap-2" style={{ borderLeftWidth: 4, borderLeftColor: color }}>
        <span className="text-sm font-semibold text-gray-700">{title}</span>
        {badge && <span className={`text-[10px] px-2 py-0.5 rounded font-medium ${badge.color || 'bg-gray-100 text-gray-500'}`}>{badge.text}</span>}
        {freshness && <FreshnessBadge freshness={freshness} compact />}
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

export function StatusBadge({ status }) {
  const s = getStatusSemantic(status)
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${s.bg} ${s.color}`}>{s.label}</span>
}

export function HealthDot({ status }) {
  const s = getAlertSeveritySemantic(status === 'green' ? 'INFO' : status === 'yellow' ? 'WARNING' : status === 'red' ? 'HIGH' : 'INFO')
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2.5 h-2.5 rounded-full ${s.dot}`} />
      <span className="text-xs text-gray-500">{s.label}</span>
    </span>
  )
}

export function SemanticBanner({ severity = 'INFO', children, className = '' }) {
  const s = getAlertSeveritySemantic(severity)
  return (
    <div className={`${s.bg} ${s.border} border rounded-lg p-3 text-xs ${s.color} ${className}`}>
      {children}
    </div>
  )
}
