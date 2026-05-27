/**
 * DriverOperatingHub — FASE H3.1
 *
 * Driver Intelligence + Execution Operating System wrapper.
 * 4 capas: Command Center, Intelligence, Execution, Foundation.
 *
 * Principios:
 * - Análisis + Ejecución como capas conversantes
 * - Placeholders gobernados para caps no construidas
 * - NO oculta tabs, NO toca queries, NO implementa lógica nueva
 */
import { useMemo } from 'react'
import { getCapabilityMeta, MATURITY, ENGINE_OWNER } from '../../config/operationalMaturityRegistry.js'
import { DriverCapabilityBanner, EngineIndicator } from '../operational/MaturityIndicators.jsx'
import DriverDataFoundation from './DriverDataFoundation.jsx'
import DriverLifecycleSummary from './DriverLifecycleSummary.jsx'
import { ROLES, ROLE_VIEWS_REGISTRY, getPersistedRole, setPersistedRole } from '../../config/driverRoleViewsRegistry.js'

const TONE = {
  success: { dot: 'bg-emerald-500', text: 'text-emerald-700', border: 'border-emerald-200', bg: 'bg-emerald-50' },
  amber: { dot: 'bg-amber-500', text: 'text-amber-700', border: 'border-amber-200', bg: 'bg-amber-50' },
  blue: { dot: 'bg-blue-500', text: 'text-blue-700', border: 'border-blue-200', bg: 'bg-blue-50' },
  purple: { dot: 'bg-purple-500', text: 'text-purple-700', border: 'border-purple-200', bg: 'bg-purple-50' },
  gray: { dot: 'bg-gray-400', text: 'text-gray-500', border: 'border-gray-200', bg: 'bg-gray-50' },
  warning: { dot: 'bg-orange-500', text: 'text-orange-700', border: 'border-orange-200', bg: 'bg-orange-50' },
}

const DRIVER_KEYS = [
  'drivers_supply',
  'drivers_lifecycle',
  'drivers_diagnostic',
  'drivers_behavior_benchmarking',
  'drivers_behavioral_alerts',
  'drivers_fleet_leakage',
  'drivers_behavioral_patterns',
  'drivers_recoverability',
  'drivers_operational_intelligence',
  'drivers_action_queues',
  'drivers_pilot',
  'drivers_operational_workflows',
  'drivers_campaign_intelligence',
  'drivers_crm_bridge',
  'drivers_campaign_effectiveness',
  'drivers_data_foundation',
  'drivers_operational_health',
  'drivers_capability_governance',
]

const LAYER_MAP = {
  'Command Center': { color: TONE.amber, keys: ['drivers_supply'] },
  Intelligence: { color: TONE.blue, keys: ['drivers_lifecycle', 'drivers_diagnostic', 'drivers_behavior_benchmarking', 'drivers_behavioral_alerts', 'drivers_fleet_leakage', 'drivers_behavioral_patterns', 'drivers_recoverability', 'drivers_operational_intelligence'] },
  Execution: { color: TONE.purple, keys: ['drivers_action_queues', 'drivers_pilot', 'drivers_operational_workflows', 'drivers_campaign_intelligence', 'drivers_crm_bridge', 'drivers_campaign_effectiveness'] },
  Foundation: { color: TONE.gray, keys: ['drivers_data_foundation', 'drivers_operational_health', 'drivers_capability_governance'] },
}

function countByLayer () {
  const counts = {}
  for (const [layer, config] of Object.entries(LAYER_MAP)) {
    let productionReady = 0
    let inConstruction = 0
    let readyNext = 0
    let futureBlocked = 0
    for (const key of config.keys) {
      const meta = getCapabilityMeta(key)
      if (!meta) continue
      if (meta.productionReady) {
        productionReady++
      } else if (meta.maturity === MATURITY.READY_NEXT) {
        readyNext++
      } else if (meta.maturity === MATURITY.FUTURE || meta.maturity === MATURITY.BLOCKED) {
        futureBlocked++
      } else {
        inConstruction++
      }
    }
    counts[layer] = {
      total: config.keys.length,
      productionReady,
      inConstruction,
      readyNext,
      futureBlocked,
      color: config.color,
    }
  }
  return counts
}

function CapabilitySummaryBar () {
  const counts = useMemo(() => countByLayer(), [])

  return (
    <div className='flex items-center gap-3 flex-wrap'>
      {Object.entries(counts).map(([layer, c]) => (
        <span key={layer} className='inline-flex items-center gap-1 text-[11px]'>
          <span className={`w-1.5 h-1.5 rounded-full ${c.color.dot}`} />
          <span className={`font-medium ${c.color.text}`}>{c.total}</span>
          <span className='text-gray-400'>{layer}</span>
        </span>
      ))}
    </div>
  )
}

/**
 * Capability Group Cards — mini cards por capa en el header.
 */
function CapabilityGroupCards () {
  const counts = useMemo(() => countByLayer(), [])

  return (
    <div className='grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3'>
      {Object.entries(counts).map(([layer, c]) => (
        <div key={layer} className={`rounded-lg border px-3 py-2 ${c.color.bg} ${c.color.border}`}>
          <div className='text-[10px] font-medium text-ct-text3 uppercase tracking-wide mb-1'>{layer}</div>
          <div className='flex items-center gap-2 text-[11px]'>
            <span className='font-semibold text-ct-text'>{c.total} caps</span>
            {c.productionReady > 0 && <span className='text-emerald-600'>{c.productionReady} ready</span>}
            {c.inConstruction > 0 && <span className='text-purple-600'>{c.inConstruction} building</span>}
            {c.readyNext > 0 && <span className='text-blue-600'>{c.readyNext} next</span>}
            {c.futureBlocked > 0 && <span className='text-gray-500'>{c.futureBlocked} blocked</span>}
          </div>
        </div>
      ))}
    </div>
  )
}

function DriverSystemHeader ({ role, onRoleChange }) {
  return (
    <div className='mb-3 pb-3 border-b border-ct-border'>
      <div className='flex items-baseline gap-2 flex-wrap justify-between'>
        <div className='flex items-baseline gap-2 flex-wrap'>
          <h1 className='text-lg font-semibold text-ct-text tracking-tight'>
            Drivers
          </h1>
          <span className='text-xs text-ct-text3 font-medium'>
            Driver Intelligence + Execution OS
          </span>
        </div>

        {/* Role Switcher */}
        <div className='flex items-center gap-1.5'>
          <span className='text-[10px] text-ct-text3'>View as:</span>
          <div className='flex gap-0.5 bg-ct-border/30 rounded-lg p-0.5'>
            {Object.entries(ROLE_VIEWS_REGISTRY).map(([key, r]) => (
              <button
                key={key}
                type='button'
                onClick={() => { setPersistedRole(key); onRoleChange && onRoleChange(key) }}
                className={`px-2 py-1 rounded text-[10px] font-medium transition-all ${
                  role === key ? 'bg-ct-accent text-white shadow-sm' : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border/50'
                }`}
                title={r.description}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      <p className='text-xs text-ct-text3 mt-0.5'>
        Analiza el universo conductor, crea cohorts accionables y mide ejecución vía CRM/workflows.
      </p>
      <div className='mt-2'>
        <CapabilitySummaryBar />
      </div>
    </div>
  )
}

/**
 * DriverOperatingHub
 *
 * Wrapper unificado para la seccion Drivers.
 * Proporciona header operacional y renderiza contenido con governance.
 *
 * Props:
 *  - activeSub: key del sub-tab activo
 *  - refreshKey: key para forzar re-render
 *  - children: contenido renderizado por App.jsx (los componentes de cada tab)
 */
export default function DriverOperatingHub ({ activeSub, refreshKey, children, role, onRoleChange }) {
  const activeMeta = getCapabilityMeta(activeSub)
  const currentRole = role || getPersistedRole()

  return (
    <div>
      <DriverSystemHeader role={currentRole} onRoleChange={onRoleChange} />
      <CapabilityGroupCards />

      {/* Data Foundation + Lifecycle cards — Supply, Pilot, Action Queues & Lifecycle tabs */}
      {(activeSub === 'drivers_supply' || activeSub === 'drivers_pilot' || activeSub === 'drivers_action_queues' || activeSub === 'drivers_lifecycle') && (
        <>
          {(activeSub === 'drivers_supply' || activeSub === 'drivers_pilot') && <DriverDataFoundation />}
          {activeSub !== 'drivers_lifecycle' && <DriverLifecycleSummary />}
        </>
      )}

      {/* Governance banner para tab NO productionReady */}
      {activeMeta && !activeMeta.productionReady && (
        <DriverCapabilityBanner moduleKey={activeSub} />
      )}

      {/* Contenido */}
      <div>
        {children}
      </div>
    </div>
  )
}

export { DRIVER_KEYS, countByLayer }
