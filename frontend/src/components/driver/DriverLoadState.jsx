import { useState } from 'react'

const STATUS_CONFIG = {
  loading: {
    border: 'border-ct-border',
    bg: 'bg-white/40',
  },
  error: {
    border: 'border-red-200',
    bg: 'bg-red-50/60',
    icon: '\u26A0',
    label: 'Error t\u00e9cnico',
    textColor: 'text-red-700',
  },
  blocked: {
    border: 'border-red-200',
    bg: 'bg-red-50/60',
    icon: '\u26D4',
    label: 'Fuente no disponible',
    textColor: 'text-red-700',
  },
  stale: {
    border: 'border-amber-200',
    bg: 'bg-amber-50/60',
    icon: '\u23F3',
    label: 'Data pendiente de refresco',
    textColor: 'text-amber-700',
  },
  empty: {
    border: 'border-gray-200',
    bg: 'bg-gray-50/60',
    icon: '\u2205',
    label: 'Sin datos',
    textColor: 'text-gray-600',
  },
}

export function DriverLoadingSkeleton ({ lines = 3, label }) {
  return (
    <div className='border border-ct-border rounded-lg p-4 bg-white/40'>
      <div className='animate-pulse space-y-2'>
        {label && <div className='text-[11px] text-gray-400 mb-1'>{label}</div>}
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className={`h-3 bg-gray-100 rounded ${i === 0 ? 'w-40' : i === 1 ? 'w-full' : 'w-3/4'}`} />
        ))}
      </div>
    </div>
  )
}

export function DriverErrorState ({ status = 'error', message, remediation, onRetry, compact }) {
  const [showDetail, setShowDetail] = useState(false)
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.error

  return (
    <div className={`border ${cfg.border} rounded-lg ${compact ? 'p-3' : 'p-4'} ${cfg.bg}`}>
      <div className='flex items-start justify-between gap-2'>
        <div className='flex items-start gap-2 min-w-0'>
          <span className='text-sm flex-shrink-0'>{cfg.icon}</span>
          <div className='min-w-0'>
            <div className={`text-xs font-semibold ${cfg.textColor}`}>{cfg.label}</div>
            {message && (
              <button
                type='button'
                onClick={() => setShowDetail(!showDetail)}
                className='text-[10px] text-gray-400 hover:text-gray-600 mt-0.5 underline'
              >
                {showDetail ? 'Ocultar detalle' : 'Ver detalle'}
              </button>
            )}
            {showDetail && message && (
              <div className='text-[10px] text-gray-500 mt-1 break-words font-mono bg-white/60 rounded px-2 py-1'>
                {message}
              </div>
            )}
          </div>
        </div>
        {onRetry && (
          <button
            type='button'
            onClick={onRetry}
            className='flex-shrink-0 px-2.5 py-1 text-[10px] font-medium rounded border border-gray-300 bg-white text-gray-600 hover:bg-gray-50 hover:text-gray-800 transition-colors'
          >
            Reintentar
          </button>
        )}
      </div>
      {remediation && (
        <div className='mt-2 pt-2 border-t border-gray-200/50'>
          <div className='text-[10px] text-gray-500'>
            <span className='font-medium'>Remediaci\u00f3n:</span> {remediation}
          </div>
        </div>
      )}
    </div>
  )
}

export function DriverFreshnessStrip ({ status, refreshedAt, source, maxPeriod }) {
  if (!status) return null
  const color = status === 'fresh' ? 'text-emerald-600' : status === 'stale' ? 'text-amber-600' : 'text-red-500'
  const dot = status === 'fresh' ? 'bg-emerald-500' : status === 'stale' ? 'bg-amber-500' : 'bg-red-500'

  return (
    <div className='flex items-center gap-3 flex-wrap text-[10px] text-gray-400 px-1 py-1'>
      <span className='inline-flex items-center gap-1'>
        <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
        <span className={`font-medium ${color}`}>{status}</span>
      </span>
      {refreshedAt && <span>Actualizado: {refreshedAt}</span>}
      {maxPeriod && <span>Hasta: {maxPeriod}</span>}
      {source && <span className='text-gray-300'>| {source}</span>}
    </div>
  )
}

export function DriverRefreshHint () {
  const [copied, setCopied] = useState(false)
  const cmd = 'cd backend && python scripts/refresh_driver_supply_facts.py'

  const handleCopy = () => {
    navigator.clipboard?.writeText(cmd).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  return (
    <div className='bg-slate-50 border border-slate-200 rounded-lg px-4 py-3'>
      <div className='text-[10px] text-slate-500 mb-1 font-medium'>Para refrescar datos de Drivers:</div>
      <div className='flex items-center gap-2'>
        <code className='text-[10px] bg-white rounded px-2 py-1 border border-slate-200 text-slate-700 flex-1 font-mono'>
          {cmd}
        </code>
        <button
          type='button'
          onClick={handleCopy}
          className='text-[10px] px-2 py-1 rounded border border-slate-300 bg-white text-slate-600 hover:bg-slate-50'
        >
          {copied ? 'Copiado' : 'Copiar'}
        </button>
      </div>
    </div>
  )
}
