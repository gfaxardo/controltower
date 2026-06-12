export function formatNum(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return Number(n).toLocaleString()
}

export function formatPct(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return (Number(n) * 100).toFixed(1) + '%'
}

export function HealthDot({ status }) {
  const map = {
    HEALTHY: 'bg-green-400',
    WARNING: 'bg-yellow-400',
    DEGRADED: 'bg-orange-400',
    CRITICAL: 'bg-red-500',
    STALE: 'bg-yellow-400',
    FRESH: 'bg-green-400',
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${map[status] || 'bg-gray-300'}`} />
}

export function StatusBadge({ status, label }) {
  const map = {
    HEALTHY: 'bg-green-100 text-green-700',
    WARNING: 'bg-yellow-100 text-yellow-700',
    DEGRADED: 'bg-orange-100 text-orange-700',
    CRITICAL: 'bg-red-100 text-red-700',
    FRESH: 'bg-green-100 text-green-700',
    STALE: 'bg-yellow-100 text-yellow-700',
    OK: 'bg-green-100 text-green-700',
    MISSING: 'bg-red-100 text-red-700',
    BROKEN: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${map[status] || 'bg-gray-100 text-gray-600'}`}>
      <HealthDot status={status} />
      {label || status}
    </span>
  )
}

export function KPICard({ label, value, subtitle, color = 'blue' }) {
  const colors = {
    blue: 'border-blue-200 bg-blue-50',
    green: 'border-green-200 bg-green-50',
    amber: 'border-amber-200 bg-amber-50',
    red: 'border-red-200 bg-red-50',
    purple: 'border-purple-200 bg-purple-50',
  }
  return (
    <div className={`border rounded-lg p-4 flex flex-col ${colors[color] || colors.blue}`}>
      <span className="text-xs text-gray-500 uppercase tracking-wide">{label}</span>
      <span className="text-2xl font-bold text-gray-800 mt-1">{value}</span>
      {subtitle && <span className="text-xs text-gray-400 mt-0.5">{subtitle}</span>}
    </div>
  )
}

export function LoadingSpinner({ text = 'Cargando...' }) {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-3" />
        <p className="text-sm text-gray-500">{text}</p>
      </div>
    </div>
  )
}

export function ErrorBlock({ message, onRetry }) {
  return (
    <div className="bg-red-50 border border-red-200 rounded-lg p-4">
      <p className="text-sm font-medium text-red-800">Error</p>
      <p className="text-xs text-red-600 mt-1">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-xs text-red-600 underline hover:text-red-800">
          Reintentar
        </button>
      )}
    </div>
  )
}

export function TabButton({ active, onClick, label, count }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-all ${
        active
          ? 'border-blue-600 text-blue-600'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
    >
      {label}
      {count != null && (
        <span className={`ml-1.5 text-xs px-1.5 py-0.5 rounded-full ${active ? 'bg-blue-100 text-blue-600' : 'bg-gray-100 text-gray-500'}`}>
          {formatNum(count)}
        </span>
      )}
    </button>
  )
}

export function SectionHeader({ title, subtitle }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-bold text-gray-800">{title}</h2>
      {subtitle && <p className="text-xs text-gray-400 mt-0.5">{subtitle}</p>}
    </div>
  )
}
