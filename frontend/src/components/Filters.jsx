import { useState } from 'react'

function Filters({ onFilterChange }) {
  const [filters, setFilters] = useState({
    country: '',
    city: '',
    line_of_business: '',
    year_real: 2025,
    year_plan: 2026
  })

  const handleChange = (field, value) => {
    const newFilters = { ...filters, [field]: value }
    setFilters(newFilters)
    onFilterChange(newFilters)
  }

  return (
    <div className="bg-white p-4 rounded-lg shadow-md mb-6">
      <h3 className="text-lg font-semibold mb-4">Filtros</h3>
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            País
          </label>
          <input
            type="text"
            value={filters.country}
            onChange={(e) => handleChange('country', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Ej: Peru, Colombia"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Ciudad
          </label>
          <input
            type="text"
            value={filters.city}
            onChange={(e) => handleChange('city', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Todas"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Línea de Negocio
          </label>
          <input
            type="text"
            value={filters.line_of_business}
            onChange={(e) => handleChange('line_of_business', e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Todas"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Año Real
          </label>
          <input
            type="number"
            value={filters.year_real}
            onChange={(e) => handleChange('year_real', parseInt(e.target.value) || 2025)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            min="2020"
            max="2100"
          />
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Año Plan
          </label>
          <input
            type="number"
            value={filters.year_plan}
            onChange={(e) => handleChange('year_plan', parseInt(e.target.value) || 2026)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            min="2020"
            max="2100"
          />
        </div>
      </div>
    </div>
  )
}

export default Filters
