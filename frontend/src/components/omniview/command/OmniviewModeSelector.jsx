/**
 * OmniviewModeSelector — Selector de modo operacional compacto.
 * 
 * FASE 1H.4 — Viewport Dominance:
 * Operational = modo dominante visible.
 * Executive / Diagnostic / Comparative = colapsados en dropdown secundario.
 * 
 * Motor: Control Foundation + Diagnostic Engine
 */

import { useState, useRef, useEffect } from 'react'

export const OMNIVIEW_MODES = Object.freeze({
  EXECUTIVE:    'executive',
  OPERATIONAL:  'operational',
  DIAGNOSTIC:   'diagnostic',
  COMPARATIVE:  'comparative',
})

const MODE_DESCRIPTIONS = {
  [OMNIVIEW_MODES.EXECUTIVE]:   'Quick status overview',
  [OMNIVIEW_MODES.OPERATIONAL]: 'Daily operational monitoring',
  [OMNIVIEW_MODES.DIAGNOSTIC]:  'Degradation & root cause',
  [OMNIVIEW_MODES.COMPARATIVE]: 'Plan vs Real comparisons',
}

const SECONDARY_MODES = [
  { id: OMNIVIEW_MODES.EXECUTIVE,   label: 'Executive' },
  { id: OMNIVIEW_MODES.DIAGNOSTIC,  label: 'Diagnostic' },
  { id: OMNIVIEW_MODES.COMPARATIVE, label: 'Comparative' },
]

export default function OmniviewModeSelector({
  mode = OMNIVIEW_MODES.OPERATIONAL,
  onChange,
  compact = false,
  className = '',
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return
    const close = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false)
      }
    }
    window.addEventListener('mousedown', close)
    return () => window.removeEventListener('mousedown', close)
  }, [menuOpen])

  const secondaryLabel = SECONDARY_MODES.map(m => m.label).join(' · ')
  const isSecondaryActive = SECONDARY_MODES.some(m => m.id === mode)

  return (
    <div ref={menuRef} className={`inline-flex items-center rounded-md border border-ct-border bg-ct-surface p-0.5 gap-0.5 ${className}`} aria-label="Operational mode">
      {/* Primary: Operational — dominante */}
      <button
        type="button"
        onClick={() => onChange(OMNIVIEW_MODES.OPERATIONAL)}
        title={MODE_DESCRIPTIONS[OMNIVIEW_MODES.OPERATIONAL]}
        className={`px-2.5 py-0.5 rounded text-xs font-semibold transition-all whitespace-nowrap ${
          mode === OMNIVIEW_MODES.OPERATIONAL
            ? 'bg-ct-accent text-white shadow-sm'
            : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border/50'
        }`}
      >
        Operational
      </button>

      {/* Secondary modes — collapsed dropdown */}
      <div className="relative">
        <button
          type="button"
          onClick={() => setMenuOpen(o => !o)}
          title={`Más modos: ${secondaryLabel}`}
          className={`px-1.5 py-0.5 rounded text-[10px] font-medium transition-all ${
            isSecondaryActive
              ? 'text-ct-accent bg-ct-accent/10'
              : 'text-ct-text3 hover:text-ct-text hover:bg-ct-border/50'
          }`}
        >
          ···
        </button>
        {menuOpen && (
          <div className="absolute left-0 top-full mt-1 z-50 bg-white border border-gray-200 rounded-lg shadow-lg py-0.5 min-w-[120px]">
            {SECONDARY_MODES.map(item => (
              <button
                key={item.id}
                type="button"
                onClick={() => { onChange(item.id); setMenuOpen(false) }}
                title={MODE_DESCRIPTIONS[item.id]}
                className={`w-full text-left px-3 py-1 text-[11px] font-medium transition-colors whitespace-nowrap ${
                  mode === item.id
                    ? 'bg-ct-accent/10 text-ct-accent'
                    : 'text-ct-text2 hover:bg-gray-50'
                }`}
              >
                {item.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export { MODE_DESCRIPTIONS }
