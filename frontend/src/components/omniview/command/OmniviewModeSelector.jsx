/**
 * OmniviewModeSelector — Selector de modo operacional compacto.
 * 
 * Segmentado en línea — NO tabs, NO dropdowns, NO banners.
 * 4 modos: EXECUTIVE | OPERATIONAL | DIAGNOSTIC | COMPARATIVE
 * 
 * Integrado en el command header.
 * 
 * Motor: Control Foundation + Diagnostic Engine
 */

export const OMNIVIEW_MODES = Object.freeze({
  EXECUTIVE:    'executive',
  OPERATIONAL:  'operational',
  DIAGNOSTIC:   'diagnostic',
  COMPARATIVE:  'comparative',
})

const MODE_ITEMS = [
  { id: OMNIVIEW_MODES.EXECUTIVE,   label: 'Executive' },
  { id: OMNIVIEW_MODES.OPERATIONAL, label: 'Operational' },
  { id: OMNIVIEW_MODES.DIAGNOSTIC,  label: 'Diagnostic' },
  { id: OMNIVIEW_MODES.COMPARATIVE, label: 'Comparative' },
]

const MODE_DESCRIPTIONS = {
  [OMNIVIEW_MODES.EXECUTIVE]:   'Quick status overview',
  [OMNIVIEW_MODES.OPERATIONAL]: 'Daily operational monitoring',
  [OMNIVIEW_MODES.DIAGNOSTIC]:  'Degradation & root cause',
  [OMNIVIEW_MODES.COMPARATIVE]: 'Plan vs Real comparisons',
}

/**
 * @param {object} props
 * @param {string} props.mode — Current mode
 * @param {function} props.onChange — (mode: string) => void
 * @param {boolean} [props.compact] — Even smaller (label-only, no descriptions)
 * @param {string} [props.className]
 */
export default function OmniviewModeSelector({
  mode = OMNIVIEW_MODES.OPERATIONAL,
  onChange,
  compact = false,
  className = '',
}) {
  return (
    <div className={`inline-flex items-center rounded-md border border-ct-border bg-ct-surface p-0.5 ${className}`} role="radiogroup" aria-label="Operational mode">
      {MODE_ITEMS.map((item) => {
        const isActive = mode === item.id
        return (
          <button
            key={item.id}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => onChange(item.id)}
            title={MODE_DESCRIPTIONS[item.id]}
            className={`px-2 py-0.5 rounded text-xs font-medium transition-all whitespace-nowrap ${
              isActive
                ? 'bg-ct-accent text-white shadow-sm'
                : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border/50'
            }`}
          >
            {item.label}
          </button>
        )
      })}
    </div>
  )
}

export { MODE_DESCRIPTIONS }
