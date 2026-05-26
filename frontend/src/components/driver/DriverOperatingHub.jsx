/**
 * DriverOperatingHub — FASE D1.3
 *
 * Driver Operating System wrapper. Transforma la seccion Drivers de
 * "9 modulos aislados" a "1 sistema operacional cohesivo".
 *
 * Principios:
 * - Supply Overview como nucleo dominante
 * - Agrupacion por capability group (Foundation / Diagnostic / Future)
 * - Single operational flow, progressive disclosure
 * - NO oculta tabs, NO toca queries, NO implementa logica nueva
 */
import { useMemo } from 'react'
import { getCapabilityMeta, MATURITY, ENGINE_OWNER } from '../../config/operationalMaturityRegistry.js'
import { DriverCapabilityBanner, EngineIndicator } from '../operational/MaturityIndicators.jsx'
import DriverDataFoundation from './DriverDataFoundation.jsx'
import DriverLifecycleSummary from './DriverLifecycleSummary.jsx'

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
  'drivers_operational_intelligence',
  'drivers_recoverability',
]

function countByMaturity () {
  const counts = { productionReady: 0, inConstruction: 0, readyNext: 0, futureBlocked: 0 }
  for (const key of DRIVER_KEYS) {
    const meta = getCapabilityMeta(key)
    if (!meta) continue
    if (meta.productionReady) { counts.productionReady++ } else if (meta.maturity === MATURITY.READY_NEXT) { counts.readyNext++ } else if (meta.maturity === MATURITY.FUTURE || meta.maturity === MATURITY.BLOCKED) { counts.futureBlocked++ } else { counts.inConstruction++ }
  }
  return counts
}

/**
 * Barra resumen de capabilities.
 * Muestra distribucion de madurez con dots + contadores.
 * Ligera, no consume espacio vertical.
 */
function CapabilitySummaryBar () {
  const counts = useMemo(() => countByMaturity(), [])

  const segments = [
    { label: 'Operational', count: counts.productionReady + counts.inConstruction, dot: TONE.amber.dot, text: TONE.amber.text },
    { label: 'Diagnostic', count: counts.readyNext, dot: TONE.blue.dot, text: TONE.blue.text },
    { label: 'Future', count: counts.futureBlocked, dot: TONE.gray.dot, text: TONE.gray.text },
  ]

  return (
    <div className='flex items-center gap-3 flex-wrap'>
      {segments.map((seg) => (
        <span key={seg.label} className='inline-flex items-center gap-1 text-[11px]'>
          <span className={`w-1.5 h-1.5 rounded-full ${seg.dot}`} />
          <span className={`font-medium ${seg.text}`}>{seg.count}</span>
          <span className='text-gray-400'>{seg.label}</span>
        </span>
      ))}
    </div>
  )
}

/**
 * Header del sistema operacional Drivers.
 * Muestra titulo, subtitulo y resumen de capabilities.
 */
function DriverSystemHeader () {
  return (
    <div className='mb-3 pb-3 border-b border-ct-border'>
      <div className='flex items-baseline gap-2 flex-wrap'>
        <h1 className='text-lg font-semibold text-ct-text tracking-tight'>
          Drivers
        </h1>
        <span className='text-xs text-ct-text3 font-medium'>
          Driver Operating System
        </span>
      </div>
      <p className='text-xs text-ct-text3 mt-0.5'>
        Operational control center for driver supply, lifecycle and execution.
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
export default function DriverOperatingHub ({ activeSub, refreshKey, children }) {
  const activeMeta = getCapabilityMeta(activeSub)

  return (
    <div>
      <DriverSystemHeader />

      {/* Data Foundation + Lifecycle cards — Supply, Action Queues & Lifecycle tabs */}
      {(activeSub === 'drivers_supply' || activeSub === 'drivers_action_queues' || activeSub === 'drivers_lifecycle') && (
        <>
          {activeSub === 'drivers_supply' && <DriverDataFoundation />}
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

export { DRIVER_KEYS, countByMaturity }
