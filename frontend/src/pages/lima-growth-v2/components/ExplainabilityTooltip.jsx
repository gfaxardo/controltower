import { useState } from 'react'

export default function ExplainabilityTooltip({ explainability, compact = false }) {
  const [open, setOpen] = useState(false)
  if (!explainability) return null

  const { title, definition, calculation, reason, operational_meaning, dependencies, freshness_status, remediation } = explainability

  return (
    <span className="relative inline-flex items-center">
      <button
        onClick={() => setOpen(!open)}
        onBlur={() => setTimeout(() => setOpen(false), 200)}
        className="ml-1 text-gray-300 hover:text-gray-500 focus:outline-none"
        title="Explicacion del KPI"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>
      {open && (
        <div className="absolute z-50 bottom-full left-0 mb-2 w-72 bg-gray-900 text-white text-xs rounded-xl shadow-2xl p-3 pointer-events-none">
          <div className="font-semibold text-white/90 mb-1">{title}</div>
          <div className="space-y-1.5 text-white/70">
            <div><span className="text-white/50">Que es:</span> {definition}</div>
            <div><span className="text-white/50">Calculo:</span> {calculation}</div>
            <div><span className="text-white/50">Por que:</span> {reason}</div>
            {operational_meaning && <div><span className="text-white/50">Significado:</span> {operational_meaning}</div>}
            {freshness_status && (
              <div>
                <span className="text-white/50">Freshness:</span>{' '}
                <span className={freshness_status === 'FRESH' ? 'text-green-400' : freshness_status === 'STALE' ? 'text-red-400' : 'text-yellow-400'}>
                  {freshness_status}
                </span>
              </div>
            )}
            {dependencies && dependencies.length > 0 && (
              <div>
                <span className="text-white/50">Dependencias:</span>{' '}
                {dependencies.map((d, i) => (
                  <span key={i} className="text-white/50">{d.name}={d.value}{i < dependencies.length - 1 ? ', ' : ''}</span>
                ))}
              </div>
            )}
            {remediation && (
              <div className="text-yellow-300 mt-1 pt-1 border-t border-white/10">
                {remediation}
              </div>
            )}
          </div>
        </div>
      )}
    </span>
  )
}
