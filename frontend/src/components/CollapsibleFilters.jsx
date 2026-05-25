import { useState } from 'react'
import Filters from './Filters'

function CollapsibleFilters({ onFilterChange }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mb-2">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md border border-ct-border bg-ct-card text-ct-text2 hover:text-ct-text hover:bg-ct-surface hover:border-ct-border-hi font-medium text-xs transition-all"
      >
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2a1 1 0 01-.293.707L13 13.414V19a1 1 0 01-.553.894l-4 2A1 1 0 017 21v-7.586L3.293 6.707A1 1 0 013 6V4z" />
        </svg>
        {open ? 'Ocultar filtros' : 'Filtros globales'}
        <svg className={`w-2.5 h-2.5 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {open && (
        <div className="mt-2">
          <Filters onFilterChange={onFilterChange} />
        </div>
      )}
    </div>
  )
}

export default CollapsibleFilters
