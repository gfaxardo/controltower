import { useState } from 'react'
import Filters from './components/Filters'
import KPICards from './components/KPICards'
import MonthlySplitView from './components/MonthlySplitView'
import UploadPlan from './components/UploadPlan'
import PlanTabs from './components/PlanTabs'

function App() {
  const [filters, setFilters] = useState({
    country: '',
    city: '',
    line_of_business: '',
    year_real: 2025,
    year_plan: 2026
  })
  const [refreshKey, setRefreshKey] = useState(0)
  const [activeTab, setActiveTab] = useState('valid')

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters)
  }

  const handleUploadSuccess = () => {
    setRefreshKey(prev => prev + 1)
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">
            YEGO Control Tower — Fase 2A
          </h1>
          <p className="text-gray-600 mb-4">
            Sistema de comparación Plan vs Real. En esta fase, el sistema muestra Real histórico (2025) y Plan futuro (2026).
            La comparación activa se activará cuando exista Real 2026.
          </p>
          <div className="bg-blue-50 border-l-4 border-blue-500 p-4 rounded-md">
            <p className="text-blue-800 font-medium">
              Plan vs Real se activa cuando exista Real 2026. Hoy mostramos histórico real + plan validado contra universo 2025.
            </p>
          </div>
        </header>

        <UploadPlan onUploadSuccess={handleUploadSuccess} />

        <Filters onFilterChange={handleFilterChange} />

        <KPICards key={`kpis-${refreshKey}`} filters={filters} />

        <div className="mb-4 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('valid')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'valid'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Plan Válido
            </button>
            <button
              onClick={() => setActiveTab('out_of_universe')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'out_of_universe'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Expansión / Fuera de universo
            </button>
            <button
              onClick={() => setActiveTab('missing')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'missing'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Huecos del Plan
            </button>
          </nav>
        </div>

        {activeTab === 'valid' ? (
          <MonthlySplitView key={`monthly-${refreshKey}`} filters={filters} />
        ) : (
          <PlanTabs 
            key={`tabs-${refreshKey}`} 
            filters={filters} 
            activeTab={activeTab}
            onTabChange={setActiveTab}
          />
        )}
      </div>
    </div>
  )
}

export default App
