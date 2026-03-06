/**
 * Glosario de definiciones del módulo Driver Supply Dynamics.
 * Muestra definiciones oficiales: Active Supply, Churn, Reactivation, Segments, Migration.
 */
import { useState, useEffect } from 'react'
import { getSupplyDefinitions } from '../services/api'

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

export default function DriverSupplyGlossary () {
  const [open, setOpen] = useState(false)
  const [definitions, setDefinitions] = useState({})

  useEffect(() => {
    getSupplyDefinitions()
      .then(setDefinitions)
      .catch(() => setDefinitions({}))
  }, [])

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
                <dd className="text-slate-600 ml-0 mt-0.5">{definitions[key] ?? '—'}</dd>
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
