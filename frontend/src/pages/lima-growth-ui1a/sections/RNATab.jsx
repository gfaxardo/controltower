import { useEffect, useState } from 'react'
import { LoadingSpinner, ErrorBlock, SectionHeader, formatNum, KPICard } from '../components/SharedComponents.jsx'
import api from '../../../services/api.js'

const BAND_COLORS = { HOT: 'red', WARM: 'amber', COLD: 'blue' }

export default function RNATab({ data, loading, errors, onRetry, onDrilldown }) {
  const loyaltyLoading = loading.loyaltySummary || loading.loyaltyKPIs
  const loyaltyError = errors.loyaltySummary || errors.loyaltyKPIs
  const loyalty = data.loyaltySummary
  const kpis = data.loyaltyKPIs
  const cityComp = data.loyaltyCityComp

  const [priority, setPriority] = useState(null)
  const [topHot, setTopHot] = useState(null)

  useEffect(() => {
    api.get('/yego-lima-growth/rna-priority/summary', { timeout: 30000 }).then(r => setPriority(r.data)).catch(() => {})
    api.get('/yego-lima-growth/rna-priority/drivers?band=HOT&limit=10', { timeout: 30000 }).then(r => setTopHot(r.data)).catch(() => {})
  }, [])

  if (loyaltyError && !loyalty) {
    return <ErrorBlock message={loyaltyError} onRetry={onRetry} />
  }
  if (loyaltyLoading && !loyalty) {
    return <LoadingSpinner text="Cargando datos RNA..." />
  }

  const totalRna = loyalty?.total_rna ?? loyalty?.rna_total ?? 0
  const newRna = loyalty?.rna_new ?? loyalty?.new_drivers ?? 0
  const reactivable = loyalty?.rna_reactivable ?? loyalty?.reactivable ?? 0
  const withPhone = loyalty?.with_phone ?? loyalty?.contactable ?? 0
  const withoutPhone = loyalty?.without_phone ?? loyalty?.not_contactable ?? 0
  const cancelledCount = loyalty?.cancelled_signals ?? loyalty?.cancelled ?? 0
  const contactabilityPct = (withPhone + withoutPhone) > 0 ? ((withPhone / (withPhone + withoutPhone)) * 100).toFixed(1) : '—'
  const cityData = cityComp?.cities || cityComp?.data || []
  const hotCount = priority?.hot || 0
  const warmCount = priority?.warm || 0
  const coldCount = priority?.cold || 0
  const topDrivers = topHot?.drivers || []

  return (
    <div>
      <SectionHeader title="RNA — Prioritization Engine" subtitle="Registered Not Activated drivers ranked by priority" />

      {/* RNA KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <KPICard label="Total RNA" value={formatNum(totalRna)} color="purple" />
        <KPICard label="Nuevos (N)" value={formatNum(newRna)} color="blue" />
        <KPICard label="Reactivables (R)" value={formatNum(reactivable)} color="amber" />
        <KPICard label="Contactability" value={`${contactabilityPct}%`} color="green" />
      </div>

      {/* Priority Bands */}
      {priority && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-center">
            <p className="text-xs text-red-600 uppercase font-bold">HOT</p>
            <p className="text-3xl font-bold text-red-700">{formatNum(hotCount)}</p>
            <p className="text-xs text-red-500">Score ≥ 35</p>
          </div>
          <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center">
            <p className="text-xs text-amber-600 uppercase font-bold">WARM</p>
            <p className="text-3xl font-bold text-amber-700">{formatNum(warmCount)}</p>
            <p className="text-xs text-amber-500">Score 15–34</p>
          </div>
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
            <p className="text-xs text-blue-600 uppercase font-bold">COLD</p>
            <p className="text-3xl font-bold text-blue-700">{formatNum(coldCount)}</p>
            <p className="text-xs text-blue-500">Score &lt; 15</p>
          </div>
        </div>
      )}

      {/* Top Priority Drivers */}
      {topDrivers.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-red-700">Top HOT Drivers</h3>
            <button
              onClick={() => onDrilldown && onDrilldown({ rna: true })}
              className="text-xs text-red-600 hover:text-red-800 underline"
            >
              Export HOT →
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-gray-500">
                  <th className="text-left py-2 px-2">Driver</th>
                  <th className="text-right py-2 px-2">Score</th>
                  <th className="text-left py-2 px-2">Lifecycle</th>
                  <th className="text-left py-2 px-2">Value</th>
                  <th className="text-left py-2 px-2">Signals</th>
                </tr>
              </thead>
              <tbody>
                {topDrivers.map((d, i) => (
                  <tr key={i} className="border-b last:border-0 hover:bg-red-50">
                    <td className="py-2 px-2 font-mono text-gray-700">{d.driver_id?.slice(0, 12)}...</td>
                    <td className="py-2 px-2 text-right font-bold text-red-600">{d.score}</td>
                    <td className="py-2 px-2 text-gray-600">{d.lifecycle || '—'}</td>
                    <td className="py-2 px-2 text-gray-600">{d.value_tier || '—'}</td>
                    <td className="py-2 px-2 text-gray-500">
                      {Object.entries(d.signals || {}).slice(0, 3).map(([k, v]) =>
                        <span key={k} className="mr-1 px-1 py-0.5 bg-gray-100 rounded text-[10px]">{k}:{v}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Contactability */}
      <div className="bg-white border rounded-lg p-4 mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Contactability</h3>
        <div className="flex items-center gap-4">
          <div className="text-center"><span className="text-xl font-bold text-green-600">{formatNum(withPhone)}</span><p className="text-xs text-gray-400">Con telefono</p></div>
          <div className="text-center"><span className="text-xl font-bold text-red-500">{formatNum(withoutPhone)}</span><p className="text-xs text-gray-400">Sin telefono</p></div>
          <div className="flex-1"><div className="w-full bg-gray-100 rounded-full h-2.5"><div className="bg-green-500 h-2.5 rounded-full" style={{width:`${Math.min(Number(contactabilityPct)||0,100)}%`}}/></div><p className="text-xs text-gray-400 mt-1">{contactabilityPct}%</p></div>
        </div>
      </div>

      {/* Cancelled Signals */}
      <div className="bg-white border rounded-lg p-4 mb-4">
        <h3 className="text-sm font-semibold text-gray-700 mb-2">Cancelled Signals</h3>
        <p className="text-2xl font-bold text-red-600">{formatNum(cancelledCount)} <span className="text-xs text-gray-400 font-normal">cancelled post-contact</span></p>
      </div>

      {/* City Comparison */}
      {cityData.length > 0 && (
        <div className="bg-white border rounded-lg p-4 mb-4">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">City Comparison</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="border-b text-gray-500"><th className="text-left py-2 px-2">City</th><th className="text-right py-2 px-2">RNA</th><th className="text-right py-2 px-2">Contact%</th><th className="text-right py-2 px-2">Activation%</th></tr></thead>
              <tbody>{cityData.map((c,i)=>(<tr key={i} className="border-b last:border-0"><td className="py-2 px-2 font-medium">{c.city||c.name||'—'}</td><td className="py-2 px-2 text-right">{formatNum(c.rna_count||c.count||0)}</td><td className="py-2 px-2 text-right">{c.contact_pct!=null?`${(c.contact_pct*100).toFixed(1)}%`:'—'}</td><td className="py-2 px-2 text-right">{c.activation_pct!=null?`${(c.activation_pct*100).toFixed(1)}%`:'—'}</td></tr>))}</tbody>
            </table>
          </div>
        </div>
      )}

      {/* Scoring Model */}
      <details className="bg-purple-50 border border-purple-200 rounded-lg p-4 mb-4">
        <summary className="text-sm font-medium text-purple-700 cursor-pointer">Why this priority score?</summary>
        <div className="mt-3 space-y-1 text-xs text-purple-600">
          <p><strong>+20</strong> Contactable (has phone)</p>
          <p><strong>+15</strong> Cancelled signal (previously engaged)</p>
          <p><strong>+15</strong> Recent activity (trips in 7d)</p>
          <p><strong>+10</strong> High value tier (top 20%)</p>
          <p><strong>+10</strong> Rising momentum</p>
          <p><strong>+10</strong> Has program assigned</p>
          <p><strong>+5</strong> Positive movement score</p>
          <p><strong>−10</strong> Dormant 30+ days</p>
          <p><strong>−15</strong> Churned/Declining lifecycle</p>
          <p className="mt-2 text-purple-400">HOT ≥ 35 | WARM 15–34 | COLD &lt; 15</p>
        </div>
      </details>

      {/* Pilot Measurement */}
      <PilotSection />
    </div>
  )
}

function PilotSection() {
  const [data, setData] = useState(null)
  useEffect(() => {
    api.get('/yego-lima-growth/rna-pilot/summary', { timeout: 30000 }).then(r => setData(r.data)).catch(() => {})
  }, [])

  if (!data) return null

  const bands = data.bands || []
  const dq = data.data_quality || []

  return (
    <div className="mt-6 border-t pt-4">
      <h2 className="text-lg font-bold text-gray-800 mb-1">RNA Pilot Measurement</h2>
      <p className="text-xs text-gray-400 mb-4">
        {data.ready
          ? 'Measuring conversion from RNA priority to actual contact and activation.'
          : 'Pilot measurement active. Waiting for contact data from LoopControl.'}
      </p>

      {/* Data Quality */}
      {dq.length > 0 && (
        <div className="flex gap-2 mb-4">
          {dq.map((q) => (
            <span key={q.quality} className={`px-2 py-1 rounded text-xs font-medium ${
              q.quality === 'HAS_CONTACT_DATA' ? 'bg-green-100 text-green-700' :
              q.quality === 'EXPORTED_ONLY' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-500'
            }`}>
              {q.quality}: {formatNum(q.count)}
            </span>
          ))}
        </div>
      )}

      {/* Band Comparison */}
      {bands.length > 0 && (
        <div className="grid grid-cols-3 gap-3 mb-4">
          {bands.map((b) => (
            <div key={b.band} className={`border rounded-lg p-3 text-center ${
              b.band === 'HOT' ? 'bg-red-50 border-red-200' :
              b.band === 'WARM' ? 'bg-amber-50 border-amber-200' : 'bg-blue-50 border-blue-200'
            }`}>
              <p className="text-xs font-bold uppercase">{b.band}</p>
              <p className="text-sm text-gray-600">Contacted: <strong>{formatNum(b.contacted)}</strong> ({b.contact_rate}%)</p>
              <p className="text-sm text-gray-600">Activated: <strong>{formatNum(b.activated)}</strong> ({b.activation_rate}%)</p>
            </div>
          ))}
        </div>
      )}

      {!data.ready && (
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-700">
          Pilot measurement not yet statistically ready. {data.total_measured} drivers measured, {data.with_contact_data} with contact data ({data.contact_data_pct}%).
        </div>
      )}

      {data.ready && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-xs text-green-700">
          Pilot measurement active. {data.total_measured} drivers tracked, {data.with_contact_data} with contact outcomes.
        </div>
      )}
    </div>
  )
}
