import { useState } from 'react'
import CollapsibleFilters from './components/CollapsibleFilters'
import ExecutiveSnapshotView from './components/ExecutiveSnapshotView'
import MonthlySplitView from './components/MonthlySplitView'
import WeeklyPlanVsRealView from './components/WeeklyPlanVsRealView'
import Phase2BActionsTrackingView from './components/Phase2BActionsTrackingView'
import Phase2CAccountabilityView from './components/Phase2CAccountabilityView'
import LobUniverseView from './components/LobUniverseView'
import RealLOBDrillView from './components/RealLOBDrillView'
import DriverLifecycleView from './components/DriverLifecycleView'
import SupplyView from './components/SupplyView'
import UploadPlan from './components/UploadPlan'
import PlanTabs from './components/PlanTabs'

const LEGACY_ENABLED = (import.meta.env.VITE_CT_LEGACY_ENABLED || '').toLowerCase() === 'true'

function App() {
  const [filters, setFilters] = useState({
    country: '',
    city: '',
    line_of_business: '',
    year_real: 2025,
    year_plan: 2026
  })
  const [refreshKey, setRefreshKey] = useState(0)
  const [activeTab, setActiveTab] = useState('real_lob')
  const [legacySubTab, setLegacySubTab] = useState('valid')
  const [showAdminModal, setShowAdminModal] = useState(false)

  const handleFilterChange = (newFilters) => {
    setFilters(newFilters)
  }

  const handleUploadSuccess = () => {
    setRefreshKey(prev => prev + 1)
    setShowAdminModal(false)
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="container mx-auto px-4 py-8">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-2xl font-bold text-gray-800">
            YEGO Control Tower
          </h1>
          <button
            type="button"
            onClick={() => setShowAdminModal(true)}
            className="px-4 py-2 rounded-md border border-gray-400 bg-gray-100 text-gray-700 hover:bg-gray-200 font-medium text-sm"
          >
            ADMIN
          </button>
        </header>

        {showAdminModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-modal="true">
            <div className="bg-white rounded-lg shadow-xl max-w-lg w-full max-h-[90vh] overflow-y-auto p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-semibold text-gray-800">Subir Plan</h2>
                <button
                  type="button"
                  onClick={() => setShowAdminModal(false)}
                  className="text-gray-500 hover:text-gray-700 text-2xl leading-none"
                >
                  ×
                </button>
              </div>
              <UploadPlan onUploadSuccess={handleUploadSuccess} />
            </div>
          </div>
        )}

        <CollapsibleFilters onFilterChange={handleFilterChange} />

        <div className="mb-4 border-b border-gray-200">
          <nav className="-mb-px flex flex-wrap gap-1 sm:space-x-8">
            <button
              onClick={() => setActiveTab('real_lob')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'real_lob'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Real LOB
            </button>
            <button
              onClick={() => setActiveTab('driver_lifecycle')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'driver_lifecycle'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Driver Lifecycle
            </button>
            <button
              onClick={() => setActiveTab('supply')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'supply'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Supply (Real)
            </button>
            <button
              onClick={() => setActiveTab('snapshot')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'snapshot'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Snapshot
            </button>
            <button
              onClick={() => setActiveTab('legacy')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'legacy'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Legacy
            </button>
            {LEGACY_ENABLED && (
              <>
                <button onClick={() => { setActiveTab('valid'); setLegacySubTab('valid'); }} className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'valid' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}>Plan Válido</button>
                <button onClick={() => { setActiveTab('out_of_universe'); setLegacySubTab('out_of_universe'); }} className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'out_of_universe' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500'}`}>Expansión</button>
                <button onClick={() => { setActiveTab('missing'); setLegacySubTab('missing'); }} className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'missing' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500'}`}>Huecos</button>
                <button onClick={() => { setActiveTab('actions'); setLegacySubTab('actions'); }} className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'actions' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500'}`}>Fase 2B</button>
                <button onClick={() => { setActiveTab('accountability'); setLegacySubTab('accountability'); }} className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'accountability' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500'}`}>Fase 2C</button>
                <button onClick={() => { setActiveTab('lob_universe'); setLegacySubTab('lob_universe'); }} className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'lob_universe' ? 'border-blue-500 text-blue-600' : 'border-transparent text-gray-500'}`}>Universo & LOB</button>
              </>
            )}
          </nav>
        </div>

        {activeTab === 'real_lob' && (
          <RealLOBDrillView key={`real-lob-drill-${refreshKey}`} />
        )}
        {activeTab === 'driver_lifecycle' && (
          <DriverLifecycleView key={`driver-lifecycle-${refreshKey}`} />
        )}
        {activeTab === 'supply' && (
          <SupplyView key={`supply-${refreshKey}`} />
        )}
        {activeTab === 'snapshot' && (
          <ExecutiveSnapshotView key={`snapshot-${refreshKey}`} filters={filters} refreshKey={refreshKey} />
        )}
        {activeTab === 'legacy' && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 border-b border-gray-200 pb-2">
              {['valid', 'out_of_universe', 'missing', 'actions', 'accountability', 'lob_universe'].map((t) => (
                <button
                  key={t}
                  onClick={() => setLegacySubTab(t)}
                  className={`px-3 py-1.5 rounded text-sm ${legacySubTab === t ? 'bg-blue-500 text-white' : 'bg-gray-200 text-gray-700'}`}
                >
                  {t === 'valid' && 'Plan Válido'}
                  {t === 'out_of_universe' && 'Expansión'}
                  {t === 'missing' && 'Huecos'}
                  {t === 'actions' && 'Fase 2B'}
                  {t === 'accountability' && 'Fase 2C'}
                  {t === 'lob_universe' && 'Universo & LOB'}
                </button>
              ))}
            </div>
            {legacySubTab === 'valid' && (
              <>
                <MonthlySplitView key={`monthly-${refreshKey}`} filters={filters} />
                <WeeklyPlanVsRealView key={`weekly-${refreshKey}`} filters={filters} />
              </>
            )}
            {legacySubTab === 'actions' && <Phase2BActionsTrackingView />}
            {legacySubTab === 'accountability' && <Phase2CAccountabilityView />}
            {legacySubTab === 'lob_universe' && <LobUniverseView key={`lob-universe-${refreshKey}`} filters={filters} />}
            {['out_of_universe', 'missing'].includes(legacySubTab) && (
              <PlanTabs key={`tabs-${refreshKey}`} filters={filters} activeTab={legacySubTab} onTabChange={setLegacySubTab} />
            )}
          </div>
        )}
        {LEGACY_ENABLED && activeTab !== 'real_lob' && activeTab !== 'legacy' && (
          <>
            {activeTab === 'valid' && (
              <>
                <MonthlySplitView key={`monthly-${refreshKey}`} filters={filters} />
                <WeeklyPlanVsRealView key={`weekly-${refreshKey}`} filters={filters} />
              </>
            )}
            {activeTab === 'actions' && <Phase2BActionsTrackingView />}
            {activeTab === 'accountability' && <Phase2CAccountabilityView />}
            {activeTab === 'lob_universe' && <LobUniverseView key={`lob-universe-${refreshKey}`} filters={filters} />}
            {['out_of_universe', 'missing'].includes(activeTab) && (
              <PlanTabs key={`tabs-${refreshKey}`} filters={filters} activeTab={activeTab} onTabChange={setActiveTab} />
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default App
