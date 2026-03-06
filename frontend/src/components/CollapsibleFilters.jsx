import { useState } from 'react'
import Filters from './Filters'

function CollapsibleFilters({ onFilterChange }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="mb-4">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-300 bg-white text-gray-700 hover:bg-gray-50 font-medium text-sm"
      >
        {open ? 'Ocultar filtros' : 'Mostrar filtros'}
        <span className="text-gray-500">{open ? '▲' : '▶'}</span>
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
