/**
 * Lima Growth V2 — Semantic Design Registry
 * Single source of truth for all visual tokens.
 *
 * Usage:
 *   import { STATUS_REGISTRY, getStatusSemantic } from './design/semanticRegistry.js'
 *   const s = getStatusSemantic('READY')  // { label, color, bg, border, icon, ... }
 */

// ── BASE COLORS ──

export const SEMANTIC_COLORS = {
  green:  { color: 'text-green-700',  bg: 'bg-green-100',  border: 'border-green-200',  dot: 'bg-green-400'  },
  yellow: { color: 'text-yellow-700', bg: 'bg-yellow-100', border: 'border-yellow-200', dot: 'bg-yellow-400' },
  red:    { color: 'text-red-700',    bg: 'bg-red-100',    border: 'border-red-200',    dot: 'bg-red-400'    },
  blue:   { color: 'text-blue-700',   bg: 'bg-blue-100',   border: 'border-blue-200',   dot: 'bg-blue-400'   },
  purple: { color: 'text-purple-700', bg: 'bg-purple-100', border: 'border-purple-200', dot: 'bg-purple-400' },
  cyan:   { color: 'text-cyan-700',   bg: 'bg-cyan-50',    border: 'border-cyan-200',   dot: 'bg-cyan-400'   },
  gray:   { color: 'text-gray-600',   bg: 'bg-gray-100',   border: 'border-gray-200',   dot: 'bg-gray-300'   },
  amber:  { color: 'text-amber-700',  bg: 'bg-amber-100',  border: 'border-amber-200',  dot: 'bg-amber-400'  },
}

const UNKNOWN_SEMANTIC = {
  label: 'UNKNOWN', color: 'text-gray-400', bg: 'bg-gray-100', border: 'border-gray-100',
  dot: 'bg-gray-300', icon: '?', description: 'Estado desconocido', severity: 'INFO'
}

// ── QUEUE / OPERATIONAL STATUSES ──

export const QUEUE_STATUS_REGISTRY = {
  READY:    { label: 'READY',     ...SEMANTIC_COLORS.green,  icon: '✓', description: 'Listo para exportar',         severity: 'OK' },
  HELD:     { label: 'HELD',      ...SEMANTIC_COLORS.yellow, icon: '⊘', description: 'Retenido — necesita atencion',severity: 'WARNING' },
  EXPORTED: { label: 'EXPORTED',  ...SEMANTIC_COLORS.purple, icon: '→', description: 'Exportado a LoopControl',     severity: 'OK' },
  UNASSIGNED:{label: 'UNASSIGNED',...SEMANTIC_COLORS.red,    icon: '∅', description: 'Sin canal asignado',          severity: 'HIGH' },
  NOT_BUILT:{ label: 'NOT_BUILT', ...SEMANTIC_COLORS.gray,   icon: '—', description: 'Cola no construida',          severity: 'INFO' },
  FAILED:   { label: 'FAILED',    ...SEMANTIC_COLORS.red,    icon: '✗', description: 'Fallo en operacion',          severity: 'CRITICAL' },
  LIVE:     { label: 'LIVE',      ...SEMANTIC_COLORS.green,  icon: '●', description: 'LoopControl activo',          severity: 'OK' },
  DRY_RUN:  { label: 'DRY_RUN',   ...SEMANTIC_COLORS.yellow, icon: '○', description: 'LoopControl en modo prueba',  severity: 'INFO' },
}

// ── PROGRAM STATUSES ──

export const PROGRAM_STATUS_REGISTRY = {
  READY:   { label: 'READY',   ...SEMANTIC_COLORS.green,  description: 'Programa listo con accionables',   severity: 'OK' },
  ACTIVE:  { label: 'ACTIVE',  ...SEMANTIC_COLORS.blue,   description: 'Programa activo con elegibles',    severity: 'OK' },
  EMPTY:   { label: 'EMPTY',   ...SEMANTIC_COLORS.gray,   description: 'Sin elegibles',                    severity: 'INFO' },
  STALE:   { label: 'STALE',   ...SEMANTIC_COLORS.red,    description: 'Datos desactualizados',            severity: 'WARNING' },
  UNKNOWN: { ...UNKNOWN_SEMANTIC,                        description: 'Estado no determinado' },
  BLOCKED: { label: 'BLOCKED', ...SEMANTIC_COLORS.red,    description: 'Bloqueado por dependencia',         severity: 'HIGH' },
}

// ── POLICY STATUSES ──

export const POLICY_STATUS_REGISTRY = {
  DRAFT:     { label: 'DRAFT',     ...SEMANTIC_COLORS.yellow, description: 'Borrador — no afecta operacion',     severity: 'INFO' },
  VALIDATED: { label: 'VALIDATED', ...SEMANTIC_COLORS.blue,   description: 'Validado — listo para activar',      severity: 'OK' },
  ACTIVE:    { label: 'ACTIVE',    ...SEMANTIC_COLORS.green,  description: 'Activo — gobernando builds',         severity: 'OK' },
  RETIRED:   { label: 'RETIRED',   ...SEMANTIC_COLORS.gray,   description: 'Retirado — conservado para auditoria',severity: 'INFO' },
  REJECTED:  { label: 'REJECTED',  ...SEMANTIC_COLORS.red,    description: 'Rechazado — no paso validacion',     severity: 'HIGH' },
}

// ── ALLOCATION MODES ──

export const ALLOCATION_MODE_REGISTRY = {
  STRICT_PRIORITY: { label: 'STRICT_PRIORITY', ...SEMANTIC_COLORS.blue,   description: 'Asignacion secuencial por prioridad', icon: '↓' },
  PROPORTIONAL:    { label: 'PROPORTIONAL',    ...SEMANTIC_COLORS.purple, description: 'Distribucion proporcional',          icon: '↔' },
  HYBRID:          { label: 'HYBRID',          ...SEMANTIC_COLORS.green,  description: 'Mixto: prioridad + caps + floors', icon: '⚖' },
  FALLBACK:        { label: 'FALLBACK',        ...SEMANTIC_COLORS.yellow, description: 'Usando politica por defecto',       icon: '⟳' },
}

// ── CHANNELS ──

export const CHANNEL_REGISTRY = {
  CALL_CENTER: { label: 'Call Center',   ...SEMANTIC_COLORS.blue,   icon: '📞' },
  SAC:         { label: 'SAC',           ...SEMANTIC_COLORS.purple, icon: '🎧' },
  BOT:         { label: 'Bot / WhatsApp',...SEMANTIC_COLORS.cyan,   icon: '🤖' },
  UNASSIGNED:  { label: 'Sin canal',      ...SEMANTIC_COLORS.red,   icon: '∅' },
}

// ── FRESHNESS ──

export const FRESHNESS_REGISTRY = {
  FRESH:   { label: 'FRESH',   ...SEMANTIC_COLORS.green,  description: 'Datos actualizados dentro del umbral', severity: 'OK' },
  WARNING: { label: 'WARNING', ...SEMANTIC_COLORS.yellow, description: 'Datos cerca del umbral de staleness',  severity: 'WARNING' },
  STALE:   { label: 'STALE',   ...SEMANTIC_COLORS.red,    description: 'Datos desactualizados',                severity: 'HIGH' },
  UNKNOWN: { ...UNKNOWN_SEMANTIC,                        description: 'Sin timestamp de actualizacion' },
}

// ── ALERT SEVERITY ──

export const ALERT_SEVERITY_REGISTRY = {
  INFO:     { label: 'INFO',     ...SEMANTIC_COLORS.blue,   description: 'Informativo' },
  WARNING:  { label: 'WARNING',  ...SEMANTIC_COLORS.yellow, description: 'Requiere atencion' },
  HIGH:     { label: 'HIGH',     ...SEMANTIC_COLORS.red,    description: 'Accion requerida' },
  CRITICAL: { label: 'CRITICAL', ...SEMANTIC_COLORS.red,    description: 'Bloqueante', border: 'border-red-500' },
}

// ── EXPORT STATUSES ──

export const EXPORT_STATUS_REGISTRY = {
  exported:       { label: 'EXPORTED',       ...SEMANTIC_COLORS.green,  description: 'Exportado exitosamente' },
  failed:         { label: 'FAILED',         ...SEMANTIC_COLORS.red,    description: 'Export fallido' },
  draft:          { label: 'DRAFT',          ...SEMANTIC_COLORS.gray,   description: 'Borrador de campana' },
  draft_dry_run:  { label: 'DRY_RUN',        ...SEMANTIC_COLORS.blue,   description: 'Simulacion de export' },
}

// ── OPERATIONAL STATUSES (Today's Action Plan) ──

export const OPERATIONAL_STATUS_REGISTRY = {
  QUEUE_NOT_BUILT:     { label: 'COLA NO CONSTRUIDA',  ...SEMANTIC_COLORS.red,    icon: '⛔', description: 'Debe construir la cola primero' },
  QUEUE_EMPTY:         { label: 'COLA VACIA',          ...SEMANTIC_COLORS.gray,   icon: '○', description: 'Sin registros en cola' },
  READY_TO_EXPORT:     { label: 'LISTO PARA EXPORTAR', ...SEMANTIC_COLORS.green,  icon: '✓', description: 'Todo listo — exportar' },
  READY_WITH_BLOCKERS: { label: 'LISTO CON BLOQUEOS',  ...SEMANTIC_COLORS.yellow, icon: '⚠', description: 'Hay HELD — resolver primero' },
  ALL_HELD:            { label: 'TODO RETENIDO',       ...SEMANTIC_COLORS.red,    icon: '⊘', description: 'Todos los registros estan HELD' },
  ALL_EXPORTED:        { label: 'TODO EXPORTADO',      ...SEMANTIC_COLORS.blue,   icon: '→', description: 'Trabajo del dia completo' },
  IDLE:                { label: 'INACTIVO',            ...SEMANTIC_COLORS.gray,   icon: '—', description: 'Sin actividad' },
}

// ── COMPOSITE REGISTRY (for StatusBadge) ──

export const STATUS_REGISTRY = {
  ...QUEUE_STATUS_REGISTRY,
  ...PROGRAM_STATUS_REGISTRY,
  ...POLICY_STATUS_REGISTRY,
  ...EXPORT_STATUS_REGISTRY,
  ...OPERATIONAL_STATUS_REGISTRY,
}

// ── HELPER FUNCTIONS ──

function _normalizeKey(key) {
  if (!key) return ''
  return String(key).trim().toUpperCase().replace(/\s+/g, '_')
}

export function getStatusSemantic(status) {
  return STATUS_REGISTRY[_normalizeKey(status)] ||
         STATUS_REGISTRY[status] ||
         UNKNOWN_SEMANTIC
}

export function getFreshnessSemantic(status) {
  return FRESHNESS_REGISTRY[_normalizeKey(status)] ||
         FRESHNESS_REGISTRY[status] ||
         FRESHNESS_REGISTRY.UNKNOWN
}

export function getQueueStatusSemantic(status) {
  return QUEUE_STATUS_REGISTRY[_normalizeKey(status)] ||
         QUEUE_STATUS_REGISTRY[status] ||
         QUEUE_STATUS_REGISTRY.NOT_BUILT
}

export function getProgramStatusSemantic(status) {
  return PROGRAM_STATUS_REGISTRY[_normalizeKey(status)] ||
         PROGRAM_STATUS_REGISTRY[status] ||
         PROGRAM_STATUS_REGISTRY.UNKNOWN
}

export function getChannelSemantic(channel) {
  return CHANNEL_REGISTRY[_normalizeKey(channel)] ||
         CHANNEL_REGISTRY[channel] ||
         CHANNEL_REGISTRY.UNASSIGNED
}

export function getPolicyStatusSemantic(status) {
  return POLICY_STATUS_REGISTRY[_normalizeKey(status)] ||
         POLICY_STATUS_REGISTRY[status] ||
         POLICY_STATUS_REGISTRY.DRAFT
}

export function getAllocationModeSemantic(mode) {
  return ALLOCATION_MODE_REGISTRY[_normalizeKey(mode)] ||
         ALLOCATION_MODE_REGISTRY[mode] ||
         ALLOCATION_MODE_REGISTRY.FALLBACK
}

export function getAlertSeveritySemantic(severity) {
  return ALERT_SEVERITY_REGISTRY[_normalizeKey(severity)] ||
         ALERT_SEVERITY_REGISTRY[severity] ||
         ALERT_SEVERITY_REGISTRY.INFO
}
