import { useState } from 'react'
import useLimaGrowthData from './lima-growth-v2/hooks/useLimaGrowthData.js'
import CommandCenterSection from './lima-growth-v2/sections/CommandCenterSection.jsx'
import ProgramsSection from './lima-growth-v2/sections/ProgramsSection.jsx'
import ExecutionQueueSection from './lima-growth-v2/sections/ExecutionQueueSection.jsx'
import ControlConfigSection from './lima-growth-v2/sections/ControlConfigSection.jsx'
import { formatNum, StatusBadge, HealthDot } from './lima-growth-v2/components/SharedComponents.jsx'

const NAV_ITEMS = [
  { id: 'command', label: 'Command Center', icon: '▸' },
  { id: 'programs', label: 'Programas y Estado', icon: '▸' },
  { id: 'queue', label: 'Execution Queue', icon: '▸' },
  { id: 'config', label: 'Configuracion', icon: '▸' },
]

export default function LimaGrowthDashboardV2() {
  const today = new Date().toISOString().slice(0, 10)
  const [activeSection, setActiveSection] = useState('command')
  const { data, loading, errors, refreshQueue, buildQueue, exportQueue, saveCapacity, fetchSection } = useLimaGrowthData(today)

  const handleRetryAll = () => {
    fetchSection('summary', () => import('../services/api.js').then(m => m.getLimaGrowthOperationalSummary(today)))
    fetchSection('driverState', () => import('../services/api.js').then(m => m.getLimaGrowthDriverStateSummary(today)))
    fetchSection('programs', () => import('../services/api.js').then(m => m.getLimaGrowthProgramsSummary(today)))
  }

  const summary = data.summary
  const config = data.config

  return (
    <div className="flex h-full min-h-screen bg-[#f6f8fb]">
      {/* Sidebar */}
      <aside className="w-52 flex-shrink-0 flex flex-col" style={{ backgroundColor: '#06244a' }}>
        <div className="px-4 py-5 border-b border-white/10">
          <div className="flex items-center gap-2">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
            <span className="text-white font-semibold text-sm">Lima Growth</span>
          </div>
          <p className="text-xs text-white/50 mt-1">Engine v2.0</p>
        </div>
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveSection(item.id)}
              className={`w-full text-left px-3 py-2 rounded-lg text-sm transition-all flex items-center gap-2 ${
                activeSection === item.id ? 'bg-white/15 text-white font-medium' : 'text-white/60 hover:text-white hover:bg-white/5'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="px-3 py-3 border-t border-white/10">
          <div className="flex items-center gap-2 text-xs text-white/40">
            <span className={`w-2 h-2 rounded-full ${config?.enabled ? 'bg-green-400' : 'bg-gray-400'}`} />
            LC: {config?.mode || '...'}
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <header className="bg-white border-b border-gray-100 px-6 py-3 flex items-center justify-between sticky top-0 z-10">
          <div>
            <h1 className="text-lg font-bold text-gray-800">YEGO Lima Growth Engine</h1>
            <p className="text-xs text-gray-400">Pipeline operacional: Universo → Priorizacion → Capacidad → Queue → Export</p>
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span>Fecha: {today}</span>
            <span>Universo: {formatNum(summary?.universe_total) || '...'}</span>
            <span>Accionables: {formatNum(summary?.actionable_today) || '...'}</span>
          </div>
        </header>

        <div className="p-6">
          {activeSection === 'command' && (
            <CommandCenterSection data={data} loading={loading} errors={errors} onRetry={handleRetryAll} />
          )}
          {activeSection === 'programs' && (
            <ProgramsSection data={data} loading={loading} errors={errors} onRetry={handleRetryAll} />
          )}
          {activeSection === 'queue' && (
            <ExecutionQueueSection
              data={data}
              loading={loading}
              errors={errors}
              onBuildQueue={buildQueue}
              onExport={exportQueue}
              onRefresh={(filters) => refreshQueue(filters)}
            />
          )}
          {activeSection === 'config' && (
            <ControlConfigSection data={data} loading={loading} errors={errors} onSaveCapacity={saveCapacity} />
          )}
        </div>
      </main>
    </div>
  )
}
