import { useState, useEffect } from 'react'
import { getDriverExplainability } from '../../../services/api.js'
import { formatNum, HealthDot } from './SharedComponents.jsx'

const DOMAINS = [
  { key: 'lifecycle', label: 'Lifecycle', icon: '🔄' },
  { key: 'segment', label: 'Segment', icon: '📊' },
  { key: 'program', label: 'Program', icon: '🎯' },
  { key: 'movement', label: 'Movement', icon: '↔️' },
  { key: 'rna', label: 'RNA', icon: '📋' },
]

function DomainSection({ domain, data }) {
  if (!data) {
    return (
      <div className="p-4 text-center text-xs text-gray-400">
        No explanation data available for {domain}.
      </div>
    )
  }

  const renderField = (label, value, highlight = false) => {
    if (value === null || value === undefined) return null
    const display = typeof value === 'object' ? JSON.stringify(value).slice(0, 120) : String(value)
    return (
      <div className="flex justify-between py-1.5 border-b border-gray-50 last:border-0">
        <span className="text-xs text-gray-500">{label}</span>
        <span className={`text-xs text-right ml-4 max-w-[300px] truncate ${highlight ? 'font-semibold text-gray-800' : 'text-gray-600'}`}>
          {display}
        </span>
      </div>
    )
  }

  return (
    <div className="space-y-0.5">
      {Object.entries(data).map(([key, value]) => {
        if (key === 'evidence' || key === 'matched_rules' || key === 'failed_rules' || key === 'rule_deltas' || key === 'eligible_programs') {
          return renderField(key, value, false)
        }
        if (key === 'reason' || key === 'selection_reason' || key === 'trigger_reason') {
          return renderField(key, value, true)
        }
        if (key === 'source_date') return renderField('source_date', value, false)
        return renderField(key, value, false)
      })}
    </div>
  )
}

export default function ExplainabilityPanel({ driverId, onClose }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeDomain, setActiveDomain] = useState('lifecycle')

  useEffect(() => {
    if (!driverId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    getDriverExplainability(driverId)
      .then((result) => {
        if (cancelled) return
        setData(result)
      })
      .catch((e) => {
        if (cancelled) return
        setError(e?.response?.data?.detail || e.message || 'Failed to load explainability')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [driverId])

  const domains = data?.domains || {}
  const hasData = Object.keys(domains).length > 0
  const firstAvailable = Object.keys(domains)[0] || 'lifecycle'

  useEffect(() => {
    if (firstAvailable) setActiveDomain(firstAvailable)
  }, [firstAvailable])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b">
          <div>
            <h3 className="text-sm font-bold text-gray-800">Why this driver?</h3>
            <p className="text-xs text-gray-400 font-mono">{driverId}</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
        </div>

        {/* Domain Tabs */}
        <div className="flex border-b px-2">
          {DOMAINS.map((d) => {
            const hasDomain = !!domains[d.key]
            return (
              <button
                key={d.key}
                onClick={() => setActiveDomain(d.key)}
                className={`px-3 py-2 text-xs font-medium border-b-2 transition-all ${
                  activeDomain === d.key
                    ? 'border-blue-600 text-blue-600'
                    : hasDomain
                      ? 'border-transparent text-gray-500 hover:text-gray-700'
                      : 'border-transparent text-gray-300 cursor-not-allowed'
                }`}
                disabled={!hasDomain}
                title={!hasDomain ? `No ${d.label} data` : d.label}
              >
                <span className="mr-1">{d.icon}</span>
                {d.label}
              </button>
            )
          })}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading && (
            <div className="flex items-center justify-center py-20">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
              {error}
            </div>
          )}

          {!loading && !error && !hasData && (
            <div className="text-center py-10 text-sm text-gray-400">
              No explainability data found for this driver.
            </div>
          )}

          {!loading && !error && hasData && (
            <>
              <div className="mb-3 text-xs text-gray-400 uppercase tracking-wide font-medium">
                {DOMAINS.find((d) => d.key === activeDomain)?.label} Explanation
              </div>

              <div className="bg-gray-50 rounded-lg p-4 mb-4">
                <div className="text-sm font-medium text-gray-700 mb-0.5">DECISION</div>
                <div className="text-xs text-gray-600">
                  {activeDomain === 'lifecycle' && `Lifecycle status: ${domains.lifecycle?.status || 'Unknown'}`}
                  {activeDomain === 'segment' && `Segment: ${domains.segment?.operational_status || 'Unknown'} / ${domains.segment?.persona || ''}`}
                  {activeDomain === 'program' && `Program: ${domains.program?.selected_program || 'No program'}`}
                  {activeDomain === 'movement' && `Movement: ${domains.movement?.transition_type || 'No transitions'}`}
                  {activeDomain === 'rna' && `RNA: ${domains.rna?.is_rna ? 'YES' : 'NO'}`}
                </div>
              </div>

              <div className="bg-blue-50 rounded-lg p-4 mb-4">
                <div className="text-sm font-medium text-blue-700 mb-0.5">RAZONES</div>
                <div className="text-xs text-blue-600">
                  {activeDomain === 'lifecycle' && (domains.lifecycle?.reason || 'No reason recorded')}
                  {activeDomain === 'segment' && `Matched ${(domains.segment?.matched_rules && typeof domains.segment.matched_rules === 'object' ? Object.keys(domains.segment.matched_rules).length : 0)} rules, failed ${(domains.segment?.failed_rules && typeof domains.segment.failed_rules === 'object' ? Object.keys(domains.segment.failed_rules).length : 0)}`}
                  {activeDomain === 'program' && (domains.program?.selection_reason || 'No reason recorded')}
                  {activeDomain === 'movement' && (domains.movement?.trigger_reason || 'No trigger reason')}
                  {activeDomain === 'rna' && (domains.rna?.reason || 'No reason available')}
                </div>
              </div>

              <div className="bg-white border rounded-lg p-4 mb-4">
                <div className="text-sm font-medium text-gray-700 mb-2">EVIDENCIA</div>
                <DomainSection domain={activeDomain} data={domains[activeDomain]} />
              </div>

              <div className="text-xs text-gray-400">
                FUENTE: {domains[activeDomain]?.source_date || 'Unknown date'}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
