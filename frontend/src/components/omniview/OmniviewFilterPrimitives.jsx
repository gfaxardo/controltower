/**
 * Controles de filtro compartidos entre Omniview Matrix y Reportes.
 * Valores enviados al API sin cambiar; la UI usa mayúsculas vía CSS.
 */
import { AVAILABLE_YEARS, normalizeOmniviewYear } from './constants.js'

const MONTH_OPTS = [
  { value: '', label: 'TODOS' },
  { value: 1, label: 'ENE' },
  { value: 2, label: 'FEB' },
  { value: 3, label: 'MAR' },
  { value: 4, label: 'ABR' },
  { value: 5, label: 'MAY' },
  { value: 6, label: 'JUN' },
  { value: 7, label: 'JUL' },
  { value: 8, label: 'AGO' },
  { value: 9, label: 'SEP' },
  { value: 10, label: 'OCT' },
  { value: 11, label: 'NOV' },
  { value: 12, label: 'DIC' },
]

const selectUpperCls =
  'uppercase border border-gray-200 rounded-md text-sm px-2.5 py-1.5 bg-white focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none min-w-[130px] text-gray-700 tracking-wide'

export function FilterSelect ({ label, value, onChange, options, placeholder, required }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
      </span>
      <select
        className={`${selectUpperCls} ${
          required && !value ? 'border-amber-400 bg-amber-50 text-amber-900' : 'hover:border-gray-300'
        }`}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">{placeholder}</option>
        {options.map((o) => (
          <option key={o} value={o}>{String(o).toUpperCase()}</option>
        ))}
      </select>
    </div>
  )
}

export function YearSelect ({ value, onChange, className = '' }) {
  const y = normalizeOmniviewYear(value)
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Año</span>
      <select
        className={`${selectUpperCls} w-24 ${className}`}
        value={y}
        onChange={(e) => onChange(Number(e.target.value))}
      >
        {AVAILABLE_YEARS.map((yy) => (
          <option key={yy} value={yy}>{yy}</option>
        ))}
      </select>
    </div>
  )
}

export function MonthSelect ({ value, onChange, className = '' }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Mes</span>
      <select
        className={`${selectUpperCls} w-28 ${className}`}
        value={value === '' || value == null ? '' : String(value)}
        onChange={(e) => {
          const v = e.target.value
          onChange(v === '' ? '' : Number(v))
        }}
      >
        {MONTH_OPTS.map((m) => (
          <option key={m.label} value={m.value === '' ? '' : String(m.value)}>{m.label}</option>
        ))}
      </select>
    </div>
  )
}

export { AVAILABLE_YEARS, normalizeOmniviewYear }
