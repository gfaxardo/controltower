import { Component } from 'react'

/**
 * Error Boundary para el módulo Omniview Matrix.
 * Captura cualquier error de React en los componentes hijos y
 * muestra un mensaje de diagnóstico en lugar de una pantalla en blanco.
 */
export default class OmniviewErrorBoundary extends Component {
  constructor (props) {
    super(props)
    this.state = { hasError: false, error: null, info: null }
  }

  static getDerivedStateFromError (error) {
    return { hasError: true, error }
  }

  componentDidCatch (error, info) {
    this.setState({ info })
    console.error('[OmniviewErrorBoundary] Caught error:', error, info)
  }

  render () {
    if (!this.state.hasError) return this.props.children

    const { error, info } = this.state
    const msg = error?.message || String(error)
    const stack = error?.stack || ''
    const componentStack = info?.componentStack || ''

    return (
      <div className="rounded-xl border border-red-200 bg-red-50 p-6 space-y-4">
        <div className="flex items-start gap-3">
          <svg className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126z" />
          </svg>
          <div>
            <p className="text-sm font-bold text-red-800">Error en Omniview Matrix</p>
            <p className="text-xs text-red-700 mt-1">{msg}</p>
          </div>
        </div>

        <div className="text-xs space-y-2">
          <p className="text-gray-500 font-semibold">Stack trace:</p>
          <pre className="bg-white border border-red-100 rounded p-3 text-[10px] text-red-700 overflow-auto max-h-40 whitespace-pre-wrap">
            {stack}
          </pre>

          {componentStack && (
            <>
              <p className="text-gray-500 font-semibold">Component stack:</p>
              <pre className="bg-white border border-red-100 rounded p-3 text-[10px] text-gray-600 overflow-auto max-h-40 whitespace-pre-wrap">
                {componentStack}
              </pre>
            </>
          )}
        </div>

        <button
          type="button"
          onClick={() => this.setState({ hasError: false, error: null, info: null })}
          className="px-3 py-1.5 rounded text-xs font-semibold bg-red-600 text-white hover:bg-red-700 transition-colors"
        >
          Reintentar
        </button>
      </div>
    )
  }
}
