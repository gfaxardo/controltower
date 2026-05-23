/**
 * Performance Timer — FASE 1G.3C
 * Instrumenta tiempos de render, API wait, parse y state update.
 *
 * Uso:
 *   const timer = usePerformanceTimer('OmniviewMatrix')
 *   // ...después de API...
 *   timer.mark('api_wait', ms)
 *   timer.mark('parse', ms)
 *   timer.mark('render')
 *
 * Emite resumen a console.groupCollapsed cuando el ciclo completa.
 */

let _uid = 0

export class PerformanceTimer {
  constructor(label = 'Perf') {
    this.label = label
    this.uid = ++_uid
    this.marks = []
    this.start = performance.now()
    this._renderStart = 0
    this._renderEnd = 0
  }

  mark(name, elapsed = null) {
    const t = elapsed != null ? elapsed : performance.now() - this.start
    this.marks.push({ name, time: t, ts: performance.now() })
    if (name === 'render_start') this._renderStart = performance.now()
    if (name === 'render_end') this._renderEnd = performance.now()
  }

  /** Mide el tiempo que tarda el siguiente paint (RAF + doble RAF). */
  measureRender(name) {
    return new Promise((resolve) => {
      this.mark(`${name}_start`)
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          const elapsed = performance.now() - this._renderStart || performance.now() - this.start
          this.mark(name, elapsed)
          resolve(elapsed)
        })
      })
    })
  }

  report() {
    if (this.marks.length === 0) return null
    const total = performance.now() - this.start
    const rows = this.marks.map(({ name, time }) => ({
      phase: name,
      ms: Math.round(time * 10) / 10,
      pct: Math.round((time / Math.max(total, 1)) * 100),
    }))
    rows.push({ phase: 'TOTAL', ms: Math.round(total * 10) / 10, pct: 100 })
    return { label: this.label, rows, total }
  }

  log() {
    const r = this.report()
    if (!r) return r
    if (typeof console !== 'undefined' && console.groupCollapsed) {
      const emoji = r.total < 1500 ? '✅' : r.total < 4000 ? '⚠️' : '🔴'
      console.groupCollapsed(`${emoji} [Perf #${this.uid}] ${r.label} · ${r.total.toFixed(1)}ms`)
      console.table(r.rows)
      console.groupEnd()
    }
    return r
  }
}

/**
 * Hook-like factory: devuelve un timer que comienza al instanciarse.
 * En React, usarlo con useRef.
 *
 * Ejemplo:
 *   const timerRef = useRef(null)
 *   if (!timerRef.current) timerRef.current = new PerformanceTimer('Carga')
 *   timerRef.current.mark('api_wait', responseTime)
 */
export function createTimer(label) {
  return new PerformanceTimer(label)
}

/**
 * Marca render start/end para medir duración del commit render en React.
 * Usar con useLayoutEffect o useEffect:
 *
 *   useLayoutEffect(() => { timerRef.current?.mark('render_end') })
 */
export function useRenderMark(timerRef, phase = 'render') {
  // Se usa en useEffect / useLayoutEffect — solo el marking
  return {
    start: () => timerRef.current?.mark(`${phase}_start`),
    end: () => timerRef.current?.mark(`${phase}_end`),
  }
}

export default PerformanceTimer
