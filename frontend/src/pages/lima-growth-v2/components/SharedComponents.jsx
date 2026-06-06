import FreshnessBadge from './FreshnessBadge.jsx'
import ExplainabilityTooltip from './ExplainabilityTooltip.jsx'

export function formatNum(n) { if (n == null) return '—'; const num = Number(n); if (isNaN(num)) return '—'; return num.toLocaleString('es-PE') }

export function LoadingState({ text = 'Cargando...' }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-[#06244a] mx-auto mb-3" />
      <p className="text-sm text-gray-400">{text}</p>
    </div>
  )
}

export function ErrorState({ message = 'Error al cargar', onRetry }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <svg className="w-10 h-10 text-red-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
      </svg>
      <p className="text-sm font-medium text-red-600">{message}</p>
      {onRetry && <button onClick={onRetry} className="mt-3 text-xs text-[#06244a] underline">Reintentar</button>}
    </div>
  )
}

export function EmptyState({ title = 'Sin datos', message = '' }) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <svg className="w-10 h-10 text-gray-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
      </svg>
      <p className="text-sm font-medium text-gray-500">{title}</p>
      {message && <p className="text-xs text-gray-400 mt-1 max-w-xs">{message}</p>}
    </div>
  )
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
  const map = {
    exported: 'bg-green-100 text-green-800',
    failed: 'bg-red-100 text-red-800',
    draft: 'bg-gray-100 text-gray-600',
    draft_dry_run: 'bg-blue-100 text-blue-800',
    LIVE: 'bg-green-100 text-green-800',
    DRY_RUN: 'bg-yellow-100 text-yellow-800',
    READY: 'bg-green-100 text-green-700',
    HELD: 'bg-yellow-100 text-yellow-700',
  }
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${map[status] || 'bg-gray-100 text-gray-600'}`}>{status}</span>
}

export function HealthDot({ status }) {
  const label = { green: 'Operativo', yellow: 'Degradado', red: 'Caido' }
  const color = { green: 'bg-green-400', yellow: 'bg-yellow-400', red: 'bg-red-400' }
  return (
    <span className="flex items-center gap-1.5">
      <span className={`w-2.5 h-2.5 rounded-full ${color[status] || 'bg-gray-300'}`} />
      <span className="text-xs text-gray-500">{label[status] || status}</span>
    </span>
  )
}
