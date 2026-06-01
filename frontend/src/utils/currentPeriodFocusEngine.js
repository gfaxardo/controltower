/**
 * currentPeriodFocusEngine.js
 *
 * Centraliza la lógica de foco temporal para Omniview:
 * - Resolución del periodo actual (hoy / semana / mes)
 * - Último día operativo disponible (fallback si no hay data para hoy)
 * - Cálculo de scroll target
 * - Prioridad visual del periodo actual
 * - Guard de auto-scroll (no pelear con navegación del usuario)
 */

const DAYS_ES = ['DOM', 'LUN', 'MAR', 'MIE', 'JUE', 'VIE', 'SAB']

function toDateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function getMondayOfISOWeek(d) {
  const date = new Date(d)
  const day = date.getDay()
  const diff = day === 0 ? -6 : 1 - day
  date.setDate(date.getDate() + diff)
  return date
}

export function resolveCurrentPeriodKey(grain) {
  const now = new Date()
  if (grain === 'daily') return toDateKey(now)
  if (grain === 'weekly') {
    const monday = getMondayOfISOWeek(now)
    return toDateKey(monday)
  }
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
}

export function resolveOperationalDay(grain, allPeriods) {
  if (!allPeriods?.length) return null
  const target = resolveCurrentPeriodKey(grain)
  if (allPeriods.includes(target)) return target
  for (let i = allPeriods.length - 1; i >= 0; i--) {
    if (grain === 'monthly') {
      if (allPeriods[i].startsWith(target.slice(0, 7))) return allPeriods[i]
    }
    if (allPeriods[i] <= target) return allPeriods[i]
  }
  return allPeriods[allPeriods.length - 1]
}

export function resolveCurrentPeriodIndex(allPeriods, grain) {
  if (!allPeriods?.length) return -1
  const currentKey = resolveCurrentPeriodKey(grain)
  const idx = allPeriods.indexOf(currentKey)
  if (idx >= 0) return idx
  for (let i = allPeriods.length - 1; i >= 0; i--) {
    if (grain === 'monthly') {
      if (allPeriods[i].startsWith(currentKey.slice(0, 7))) return i
    }
    if (allPeriods[i] <= currentKey) return i
  }
  return allPeriods.length - 1
}

export function isCurrentPeriod(pk, grain) {
  return pk === resolveCurrentPeriodKey(grain)
}

export function getCurrentPeriodBadge(grain) {
  if (grain === 'daily') return 'HOY'
  if (grain === 'weekly') return 'SEMANA ACTUAL'
  return 'MES ACTUAL'
}

export function calculateScrollTarget(idx, colW, fixedW, viewportW, grain = 'daily') {
  if (idx < 0) return 0
  const targetLeft = fixedW + (idx * colW)
  // Daily: present ~30% from left (show recent past + present + some future)
  // Weekly/Monthly: center the period
  const offset = grain === 'daily'
    ? viewportW * 0.30
    : viewportW / 2 - colW / 2
  return Math.max(0, targetLeft - offset)
}

export function getCurrentPeriodVisualPriority(grain) {
  return {
    fontSizeMultiplier: 1.15,
    weight: 'extra-bold',
    badgeSize: 'sm',
    backgroundIntensity: 'medium',
    borderIntensity: 'high',
  }
}

export function isPeriodNear(grain, periodKey, currentKey, allPeriods) {
  if (!allPeriods?.length) return false
  const currentIdx = allPeriods.indexOf(currentKey)
  const periodIdx = allPeriods.indexOf(periodKey)
  if (currentIdx < 0 || periodIdx < 0) return false
  const distance = Math.abs(periodIdx - currentIdx)
  if (grain === 'daily') return distance <= 3
  if (grain === 'weekly') return distance <= 2
  return distance <= 1
}

export function isPeriodDistant(grain, periodKey, currentKey, allPeriods) {
  if (!allPeriods?.length) return false
  const currentIdx = allPeriods.indexOf(currentKey)
  const periodIdx = allPeriods.indexOf(periodKey)
  if (currentIdx < 0 || periodIdx < 0) return false
  const distance = Math.abs(periodIdx - currentIdx)
  if (grain === 'daily') return distance > 14
  if (grain === 'weekly') return distance > 8
  return distance > 6
}

export function shouldAutoScrollReset(prevGrain, nextGrain, prevViewMode, nextViewMode) {
  return prevGrain !== nextGrain || prevViewMode !== nextViewMode
}
