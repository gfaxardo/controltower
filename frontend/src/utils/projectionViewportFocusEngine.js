/**
 * projectionViewportFocusEngine.js
 *
 * Engine de centrado operacional del viewport para Omniview Vs Proyección.
 *
 * OBJETIVO:
 * - Asegurar que HOY / semana actual / mes actual aparezca centrado
 *   en el viewport visible tras la carga de datos.
 * - Funciona con el scrollContainerRef real de la tabla.
 * - Respeta el zoom, compact, column widths.
 * - No hace "mini scroll" — centra operacionalmente.
 * - Proporciona visibilidad del período actual y límites de ventana temporal.
 *
 * REGLAS:
 * - NO tocar serving logic
 * - NO tocar momentum calculations
 * - NO tocar projection calculations
 * - NO romper virtualization
 * - NO romper sticky
 * - NO romper fullscreen
 */

/**
 * Obtiene la clave de período actual según el grano.
 * Coincide exactamente con getCurrentPeriodKey de omniviewMatrixUtils.js.
 */
function getCurrentPeriodKey(grain) {
  const now = new Date()
  if (grain === 'daily') {
    const y = now.getFullYear()
    const m = String(now.getMonth() + 1).padStart(2, '0')
    const d = String(now.getDate()).padStart(2, '0')
    return `${y}-${m}-${d}`
  }
  if (grain === 'weekly') {
    const day = now.getDay()
    const diff = now.getDate() - day + (day === 0 ? -6 : 1)
    const monday = new Date(now.getFullYear(), now.getMonth(), diff)
    const y = monday.getFullYear()
    const m = String(monday.getMonth() + 1).padStart(2, '0')
    const d = String(monday.getDate()).padStart(2, '0')
    return `${y}-${m}-${d}`
  }
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
}

/**
 * Encuentra el índice del período actual en allPeriods.
 * Si el período exacto no existe, busca el más cercano hacia atrás.
 */
export function findCurrentPeriodIndex(allPeriods, grain) {
  if (!allPeriods || !allPeriods.length) return -1
  const currentKey = getCurrentPeriodKey(grain)

  const exactIdx = allPeriods.indexOf(currentKey)
  if (exactIdx >= 0) return exactIdx

  for (let i = allPeriods.length - 1; i >= 0; i--) {
    if (grain === 'monthly') {
      if (allPeriods[i].startsWith(currentKey.slice(0, 7))) return i
    }
    if (allPeriods[i] <= currentKey) return i
  }
  return allPeriods.length - 1
}

/**
 * Encuentra el índice de un período específico en allPeriods.
 * Si no existe, busca el más cercano hacia atrás.
 */
export function findPeriodIndex(allPeriods, periodKey) {
  if (!allPeriods || !allPeriods.length || !periodKey) return -1
  const exactIdx = allPeriods.indexOf(periodKey)
  if (exactIdx >= 0) return exactIdx
  for (let i = allPeriods.length - 1; i >= 0; i--) {
    if (allPeriods[i] <= periodKey) return i
  }
  return allPeriods.length - 1
}

/**
 * Calcula el número de columnas visibles en el viewport actual.
 */
export function visibleColumnCount(container, colW, fixedCol1W, fixedCol2W) {
  if (!container) return 0
  const viewW = container.clientWidth
  const fixedW = fixedCol1W + fixedCol2W
  return Math.max(0, Math.floor((viewW - fixedW) / colW))
}

/**
 * Calcula el rango de períodos visibles [startIdx, endIdx].
 */
export function visibleWindowRange({ container, allPeriods, grain, colW, fixedCol1W, fixedCol2W }) {
  if (!container || !allPeriods || !allPeriods.length) return { start: 0, end: 0, currentIdx: -1 }

  const currentIdx = findCurrentPeriodIndex(allPeriods, grain)
  const visCount = visibleColumnCount(container, colW, fixedCol1W, fixedCol2W)

  const scrollLeft = container.scrollLeft
  const fixedW = fixedCol1W + fixedCol2W
  const startIdx = Math.max(0, Math.floor((scrollLeft - fixedW) / colW))
  const endIdx = Math.min(allPeriods.length, startIdx + visCount + 1)

  return {
    start: Math.max(0, startIdx),
    end: endIdx,
    currentIdx,
    currentIsVisible: currentIdx >= 0 && currentIdx >= startIdx && currentIdx <= endIdx,
  }
}

/**
 * Calcula la posición de scroll horizontal para centrar un período en el viewport.
 * Si anchorPeriodKey no se provee, usa findCurrentPeriodIndex por grain.
 */
export function computeViewportCenterScroll({ container, allPeriods, grain, fixedCol1W, fixedCol2W, colW, anchorPeriodKey = null }) {
  if (!container || !allPeriods || !allPeriods.length) return null

  const idx = anchorPeriodKey
    ? findPeriodIndex(allPeriods, anchorPeriodKey)
    : findCurrentPeriodIndex(allPeriods, grain)
  if (idx < 0) return null

  const fixedW = fixedCol1W + fixedCol2W
  const targetLeft = fixedW + (idx * colW)
  const viewportWidth = container.clientWidth

  if (viewportWidth <= 0) return null

  const scrollTo = Math.max(0, targetLeft - Math.floor(viewportWidth / 2) + Math.floor(colW / 2))

  const maxScroll = container.scrollWidth - container.clientWidth
  const clampedScroll = Math.min(scrollTo, Math.max(0, maxScroll))

  return { scrollLeft: clampedScroll, currentIdx: idx }
}

/**
 * Ejecuta el scroll centrado operacionalmente.
 */
export function executeViewportCenter(container, scrollLeft, behavior = 'smooth') {
  if (!container) return
  try {
    container.scrollTo({ left: scrollLeft, behavior })
  } catch {
    container.scrollLeft = scrollLeft
  }
}

/**
 * Función principal: centrar el viewport de proyección en el anchor period.
 * Si no se provee anchorPeriodKey, usa el período calendario actual.
 */
export function centerProjectionViewport({
  scrollContainerRef,
  projMatrix,
  grain,
  compact,
  isProjectionMode,
  force = false,
  anchorPeriodKey = null,
}) {
  if (!isProjectionMode) return false
  if (!projMatrix || !projMatrix.allPeriods || !projMatrix.allPeriods.length) return false

  const container = scrollContainerRef?.current
  if (!container) return false

  const allPeriods = projMatrix.allPeriods

  const colW = compact ? 78 : 100
  const fixedCol1W = 148
  const fixedCol2W = 160

  const result = computeViewportCenterScroll({
    container,
    allPeriods,
    grain,
    fixedCol1W,
    fixedCol2W,
    colW,
    anchorPeriodKey,
  })

  if (!result) return false

  executeViewportCenter(container, result.scrollLeft, 'auto')
  return true
}

/**
 * Verifica si el período actual ya es visible en el viewport.
 */
export function isCurrentPeriodVisible({ container, allPeriods, grain, colW, fixedCol1W, fixedCol2W }) {
  if (!container || !allPeriods || !allPeriods.length) return false

  const idx = findCurrentPeriodIndex(allPeriods, grain)
  if (idx < 0) return false

  const fixedW = fixedCol1W + fixedCol2W
  const colStart = fixedW + (idx * colW)
  const colEnd = colStart + colW
  const viewStart = container.scrollLeft
  const viewEnd = viewStart + container.clientWidth

  return colStart >= viewStart && colEnd <= viewEnd + colW
}
