/**
 * MaturityBadge, PhaseIndicator, EngineIndicator — FASE 1H.4
 * Indicadores visuales discretos de madurez operacional.
 * NO saturan la UI. Comunican confianza operacional.
 */
import { MATURITY, ENGINE_OWNER, getMaturityBadgeInfo } from '../../config/operationalMaturityRegistry.js'

/**
 * Badge de madurez sutil.
 * Solo aparece para hardening, in_construction, experimental, legacy, deprecated.
 * STABLE no muestra badge.
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
 * Muestra "Fase 1H", "Fase 2A", etc.
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
 * Indicador de engine owner.
 */
export function EngineIndicator ({ engine, className = '' }) {
  if (!engine) return null

  const isControlFoundation = engine === ENGINE_OWNER.CONTROL_FOUNDATION
  const isDiagnostic = engine === ENGINE_OWNER.DIAGNOSTIC

  const baseCls = 'inline-flex items-center px-1 py-px rounded text-[11px] font-medium border'
  const colorCls = isControlFoundation
    ? 'text-emerald-600 bg-emerald-50 border-emerald-100'
    : isDiagnostic
      ? 'text-blue-600 bg-blue-50 border-blue-100'
      : 'text-gray-500 bg-gray-50 border-gray-150'

  return (
    <span
      className={`${baseCls} ${colorCls} ${className}`}
      title={`Motor: ${engine}`}
    >
      {engine}
    </span>
  )
}

/**
 * Barra de estado de madurez compacta para usar en headers de vista.
 * Combina MaturityBadge + PhaseIndicator + EngineIndicator.
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
