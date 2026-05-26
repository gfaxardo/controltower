/**
 * MaturityBadge, PhaseIndicator, EngineIndicator, MaturityStatusBar — FASE 1H.4
 * DriverCapabilityBadge, DriverCapabilityBanner — FASE D1.1/D1.2
 * Indicadores visuales discretos de madurez operacional.
 * NO saturan la UI. Comunican confianza operacional sin ocultar tabs.
 */
import { MATURITY, ENGINE_OWNER, getMaturityBadgeInfo, getCapabilityMeta } from '../../config/operationalMaturityRegistry.js'

const TONE_MAP = {
  success: { dot: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-800 border-emerald-200', text: 'text-emerald-700' },
  amber: { dot: 'bg-amber-500', badge: 'bg-amber-100 text-amber-800 border-amber-200', text: 'text-amber-700' },
  blue: { dot: 'bg-blue-500', badge: 'bg-blue-100 text-blue-800 border-blue-200', text: 'text-blue-700' },
  purple: { dot: 'bg-purple-500', badge: 'bg-purple-100 text-purple-800 border-purple-200', text: 'text-purple-700' },
  gray: { dot: 'bg-gray-400', badge: 'bg-gray-100 text-gray-600 border-gray-200', text: 'text-gray-500' },
  warning: { dot: 'bg-orange-500', badge: 'bg-orange-100 text-orange-800 border-orange-200', text: 'text-orange-700' },
  red: { dot: 'bg-red-500', badge: 'bg-red-100 text-red-800 border-red-200', text: 'text-red-700' },
}

/**
 * Badge de madurez sutil.
 * Solo aparece para hardening, in_construction, ready_next, future, legacy, deprecated, blocked.
 * STABLE/ACTIVE no muestra badge.
 */
export function MaturityBadge ({ moduleKey, className = '' }) {
  const info = getMaturityBadgeInfo(moduleKey)
  if (!info) return null

  return (
    <span
      className={`inline-flex items-center px-1.5 py-px rounded-full text-[11px] font-medium border ${info.color} ${className}`}
      title={`Madurez: ${info.label}`}
    >
      {info.label}
    </span>
  )
}

/**
 * Indicador de fase sutil.
 */
export function PhaseIndicator ({ phase, className = '' }) {
  if (!phase || phase === 'BACKLOG') return null

  return (
    <span
      className={`inline-flex items-center px-1 py-px rounded text-[11px] font-mono font-medium text-gray-400 bg-gray-50 border border-gray-150 ${className}`}
      title={`Fase actual: ${phase}`}
    >
      {phase}
    </span>
  )
}

/**
 * Indicador de engine owner con colores por motor.
 */
export function EngineIndicator ({ engine, className = '' }) {
  if (!engine) return null

  const isControlFoundation = engine === ENGINE_OWNER.CONTROL_FOUNDATION
  const isDiagnostic = engine === ENGINE_OWNER.DIAGNOSTIC
  const isReachability = engine === ENGINE_OWNER.REACHABILITY
  const isDecisionSuggestion = engine === ENGINE_OWNER.DECISION_SUGGESTION

  const baseCls = 'inline-flex items-center px-1 py-px rounded text-[11px] font-medium border'
  const colorCls = isControlFoundation
    ? 'text-emerald-600 bg-emerald-50 border-emerald-100'
    : isDiagnostic
      ? 'text-blue-600 bg-blue-50 border-blue-100'
      : isReachability
        ? 'text-cyan-600 bg-cyan-50 border-cyan-100'
        : isDecisionSuggestion
          ? 'text-violet-600 bg-violet-50 border-violet-100'
          : 'text-gray-500 bg-gray-50 border-gray-150'

  return (
    <span className={`${baseCls} ${colorCls} ${className}`} title={`Motor: ${engine}`}>
      {engine}
    </span>
  )
}

/**
 * Barra de estado de madurez compacta para headers de vista.
 */
export function MaturityStatusBar ({ moduleKey, phase, engine, className = '' }) {
  return (
    <div className={`flex flex-wrap items-center gap-1.5 ${className}`}>
      <MaturityBadge moduleKey={moduleKey} />
      <PhaseIndicator phase={phase} />
      <EngineIndicator engine={engine} />
    </div>
  )
}

/**
 * DriverCapabilityBadge — FASE D1.1/D1.2
 *
 * Badge reutilizable que muestra el nivel de madurez de una capability de Drivers.
 * Usa la metadata del capability registry.
 *
 * Colores:
 *   ACTIVE → verde (no se muestra por defecto, es productionReady)
 *   HARDENING → ámbar
 *   READY NEXT → azul
 *   UNDER CONSTRUCTION → morado
 *   FUTURE → gris
 *   LEGACY → rojo oscuro
 *   BLOCKED → naranja/warning
 */
export function DriverCapabilityBadge ({ moduleKey, className = '' }) {
  const meta = getCapabilityMeta(moduleKey)
  if (!meta) return null
  if (meta.maturity === MATURITY.STABLE || meta.maturity === MATURITY.ACTIVE) return null

  const tone = TONE_MAP[meta.statusTone] || TONE_MAP.gray

  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium border ${tone.badge} ${className}`}
      title={`Motor: ${meta.engine} | Fase: ${meta.phase} | ${meta.governanceReason}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full ${tone.dot}`} />
      {meta.statusLabel}
    </span>
  )
}

/**
 * DriverCapabilityBanner — FASE D1.1/D1.2
 *
 * Banner informativo que aparece dentro de tabs NO productionReady.
 * Muestra motor, fase, dependencia principal y qué falta para GO.
 * NO bloquea navegación. NO rompe contenido. NO oculta tab.
 */
export function DriverCapabilityBanner ({ moduleKey, className = '' }) {
  const meta = getCapabilityMeta(moduleKey)
  if (!meta) return null
  if (meta.productionReady) return null

  const tone = TONE_MAP[meta.statusTone] || TONE_MAP.blue
  const primaryDependency = meta.dependencies && meta.dependencies.length > 0 ? meta.dependencies[0] : null

  return (
    <div className={`border rounded-lg p-3 mb-3 ${tone.badge.replace('text-', 'border-').replace('bg-', 'border-')} bg-white/60 ${className}`}>
      <div className='flex items-start gap-2.5'>
        <div className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${tone.dot}`} />
        <div className='flex-1 min-w-0'>
          <div className='flex items-center gap-2 flex-wrap mb-1'>
            <span className={`text-xs font-semibold ${tone.text}`}>
              {meta.statusLabel}
            </span>
            <span className='text-[10px] text-gray-400 font-mono'>{meta.phase}</span>
            <EngineIndicator engine={meta.engine} />
          </div>
          <p className='text-xs text-gray-500 leading-relaxed'>
            Esta capacidad está visible como parte del roadmap de Drivers, pero todavía no está habilitada como capacidad operacional madura.
          </p>
          {primaryDependency && (
            <p className='text-[11px] text-gray-400 mt-1'>
              Dependencia principal: <span className='font-medium text-gray-500'>{primaryDependency}</span>
            </p>
          )}
          {meta.governanceReason && (
            <p className='text-[11px] text-gray-400 mt-0.5'>
              Qué falta para GO: <span className='text-gray-500'>{meta.governanceReason}</span>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}
