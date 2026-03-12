/**
 * Glosario de definiciones del módulo Driver Supply Dynamics.
 * Muestra definiciones oficiales y leyenda de segmentos (7: Dormant, Occasional, Casual, PT, FT, Elite, Legend).
 * Usa segmentConfig desde API cuando está disponible; si no, fallback a SEGMENT_LEGEND_MINIMAL.
 */
import { useState, useEffect } from 'react'
import { getSupplyDefinitions, getSupplySegmentConfig } from '../services/api'
import { SEGMENT_LEGEND_MINIMAL } from '../constants/segmentSemantics'

const TERMS = [
  { key: 'active_supply', label: 'Active Supply' },
  { key: 'active_drivers', label: 'Active drivers' },
  { key: 'week_supply', label: 'Week supply' },
  { key: 'churned', label: 'Churned' },
  { key: 'reactivated', label: 'Reactivated' },
  { key: 'net_growth', label: 'Net growth' },
  { key: 'segments', label: 'Segments' },
  { key: 'migration', label: 'Migration' },
  { key: 'growth_rate', label: 'Growth rate' },
  { key: 'activations', label: 'Activations' }
]

function segmentDesc (c) {
  if (c.min_trips != null && c.max_trips != null) return `${c.min_trips}–${c.max_trips} viajes/semana`
  if (c.min_trips != null) return `${c.min_trips}+ viajes/semana`
  return '0 viajes/semana'
}

export default function DriverSupplyGlossary () {
  const [open, setOpen] = useState(false)
  const [definitions, setDefinitions] = useState({})
  const [segmentConfig, setSegmentConfig] = useState([])

  useEffect(() => {
    getSupplyDefinitions().then(setDefinitions).catch(() => setDefinitions({}))
    getSupplySegmentConfig().then(setSegmentConfig).catch(() => setSegmentConfig([]))
  }, [])

  const segmentList = segmentConfig.length > 0
    ? segmentConfig.map(c => ({ segment: c.segment, label: c.segment, desc: segmentDesc(c) }))
    : SEGMENT_LEGEND_MINIMAL.map(({ segment, label, desc }) => ({ segment, label, desc }))

  return (
    <div className="inline">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="text-sm text-blue-600 hover:underline"
      >
        Ver definiciones
      </button>
      {open && (
        <div className="mt-3 p-4 bg-slate-50 border border-slate-200 rounded-lg shadow max-w-2xl">
          <h3 className="text-sm font-semibold text-slate-800 mb-3">Definiciones — Driver Supply Dynamics</h3>
          <dl className="space-y-2 text-sm">
            {TERMS.map(({ key, label }) => (
              <div key={key}>
                <dt className="font-medium text-slate-700">{label}</dt>
                <dd className="text-slate-600 ml-0 mt-0.5">
                  {definitions[key] ?? '—'}
                  {key === 'segments' && (
                    <ul className="mt-2 list-disc list-inside text-slate-600 space-y-0.5">
                      {segmentList.map(({ segment, label: segLabel, desc }) => (
                        <li key={segment}><strong>{segLabel}</strong>: {desc}</li>
                      ))}
                    </ul>
                  )}
                </dd>
              </div>
            ))}
          </dl>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="mt-3 text-sm text-slate-500 hover:text-slate-700"
          >
            Cerrar
          </button>
        </div>
      )}
    </div>
  )
}
