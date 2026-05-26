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
  // monthly: first day of current month
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-01`
}

/**
 * Encuentra el índice del período actual en allPeriods.
 * Si el período exacto no existe, busca el más cercano hacia atrás.
 *
 * @param {string[]} allPeriods - Lista de period keys (YYYY-MM-DD o YYYY-MM-DD para monthly)
 * @param {string} grain - 'daily' | 'weekly' | 'monthly'
 * @returns {number} - índice del período actual, o -1 si no se encuentra
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
 * Calcula la posición de scroll horizontal para centrar el período actual
 * en el viewport visible.
 *
 * @param {Object} params
 * @param {HTMLElement} params.container - El scroll container (scrollContainerRef.current)
 * @param {string[]} params.allPeriods - Lista de period keys
 * @param {string} params.grain - 'daily' | 'weekly' | 'monthly'
 * @param {number} params.fixedCol1W - Ancho de la columna fija 1 (COL1_W)
 * @param {number} params.fixedCol2W - Ancho de la columna fija 2 (COL2_W)
 * @param {number} params.colW - Ancho de cada columna de período
 * @returns {{ scrollLeft: number, currentIdx: number } | null}
 */
export function computeViewportCenterScroll({ container, allPeriods, grain, fixedCol1W, fixedCol2W, colW }) {
  if (!container || !allPeriods || !allPeriods.length) return null

  const idx = findCurrentPeriodIndex(allPeriods, grain)
  if (idx < 0) return null

  const fixedW = fixedCol1W + fixedCol2W
  const targetLeft = fixedW + (idx * colW)
  const viewportWidth = container.clientWidth

  if (viewportWidth <= 0) return null

  // Centrar: posición del centro del período actual en el centro del viewport
  const scrollTo = Math.max(0, targetLeft - Math.floor(viewportWidth / 2) + Math.floor(colW / 2))

  return { scrollLeft: scrollTo, currentIdx: idx }
}

/**
 * Ejecuta el scroll centrado operacionalmente.
 * Respeta el comportamiento smooth para navegación natural.
 *
 * @param {HTMLElement} container - El scroll container
 * @param {number} scrollLeft - Posición de scroll calculada
 * @param {string} behavior - 'smooth' | 'auto' | 'instant'
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
 * Función principal: centrar el viewport de proyección en el período actual.
 * Uso: llamar desde useEffect después de que los datos de proyección estén listos.
 *
 * @param {Object} params
 * @param {React.RefObject} params.scrollContainerRef - Ref al scroll container
 * @param {Object|null} params.projMatrix - Matriz de proyección (o displayProjMatrix)
 * @param {string} params.grain - Grano actual
 * @param {boolean} params.compact - Modo compacto
 * @param {boolean} params.isProjectionMode - Si está en modo proyección
 * @param {boolean} [params.force=false] - Forzar centrado incluso si ya se aplicó
 */
export function centerProjectionViewport({
  scrollContainerRef,
  projMatrix,
  grain,
  compact,
  isProjectionMode,
  force = false,
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
  })

  if (!result) return false

  executeViewportCenter(container, result.scrollLeft, 'auto')
  return true
}

/**
 * Verifica si el período actual ya es visible en el viewport sin necesidad de scroll.
 *
 * @param {HTMLElement} container
 * @param {string[]} allPeriods
 * @param {string} grain
 * @param {number} colW
 * @param {number} fixedCol1W
 * @param {number} fixedCol2W
 * @returns {boolean}
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
