/**
 * Calibración ligera del Insight Engine (solo cliente + localStorage).
 */
import { useEffect, useState } from 'react'
import { INSIGHT_CONFIG } from './omniview/insightConfig.js'
import { clearInsightUserPatch, saveInsightUserPatch } from './omniview/insightUserSettings.js'

export default function BusinessSliceInsightSettings ({ open, onClose, userPatch, onSaved }) {
  const defaults = INSIGHT_CONFIG.impactWeights
  const [wRev, setWRev] = useState(defaults.revenue_yego_net)
  const [wTrip, setWTrip] = useState(defaults.trips_completed)
  const [wDrv, setWDrv] = useState(defaults.active_drivers)
  const [sens, setSens] = useState(1)

  useEffect(() => {
    if (!open) return
    setWRev(userPatch?.impactWeights?.revenue_yego_net ?? defaults.revenue_yego_net)
    setWTrip(userPatch?.impactWeights?.trips_completed ?? defaults.trips_completed)
    setWDrv(userPatch?.impactWeights?.active_drivers ?? defaults.active_drivers)
    setSens(userPatch?.sensitivityMultiplier ?? 1)
  }, [open, userPatch, defaults.revenue_yego_net, defaults.trips_completed, defaults.active_drivers])

  if (!open) return null

  const normalizeWeights = () => {
    const s = (Number(wRev) || 0) + (Number(wTrip) || 0) + (Number(wDrv) || 0) || 1
    return {
      revenue_yego_net: (Number(wRev) || 0) / s,
      trips_completed: (Number(wTrip) || 0) / s,
      active_drivers: (Number(wDrv) || 0) / s,
    }
  }

  const handleSave = () => {
    saveInsightUserPatch({
      impactWeights: normalizeWeights(),
      sensitivityMultiplier: Math.min(2, Math.max(0.5, Number(sens) || 1)),
    })
    onSaved?.()
    onClose()
  }

  const handleReset = () => {
    clearInsightUserPatch()
    onSaved?.()
    onClose()
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/30" role="dialog" aria-modal="true" aria-labelledby="insight-settings-title">
      <div className="bg-white rounded-lg border border-gray-200 shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto">
        <div className="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
          <h2 id="insight-settings-title" className="text-sm font-bold text-gray-800">Insight settings</h2>
          <button type="button" className="text-gray-400 hover:text-gray-700 text-lg leading-none" onClick={onClose} aria-label="Cerrar">×</button>
        </div>
        <div className="px-4 py-3 space-y-3 text-xs text-gray-600">
          <p className="text-[11px] text-gray-500 leading-relaxed">
            Ajustes guardados en este navegador (localStorage). Umbrales principales del motor siguen en código; aquí solo pesos de impacto y multiplicador de sensibilidad.
          </p>

          <div>
            <p className="font-semibold text-gray-700 mb-1">Pesos de impacto (se normalizan al guardar)</p>
            <div className="grid grid-cols-3 gap-2">
              <label className="flex flex-col gap-0.5">
                <span className="text-[10px] text-gray-400">Revenue</span>
                <input type="number" step="0.05" min="0" max="1" className="border rounded px-2 py-1" value={wRev} onChange={(e) => setWRev(e.target.value)} />
              </label>
              <label className="flex flex-col gap-0.5">
                <span className="text-[10px] text-gray-400">Viajes</span>
                <input type="number" step="0.05" min="0" max="1" className="border rounded px-2 py-1" value={wTrip} onChange={(e) => setWTrip(e.target.value)} />
              </label>
              <label className="flex flex-col gap-0.5">
                <span className="text-[10px] text-gray-400">Conductores</span>
                <input type="number" step="0.05" min="0" max="1" className="border rounded px-2 py-1" value={wDrv} onChange={(e) => setWDrv(e.target.value)} />
              </label>
            </div>
          </div>

          <div>
            <label className="flex flex-col gap-1">
              <span className="font-semibold text-gray-700">Sensibilidad de umbrales</span>
              <span className="text-[10px] text-gray-400">Mayor = más estricto (menos alertas). Rango 0.5–2.</span>
              <input type="range" min="0.5" max="2" step="0.05" value={sens} onChange={(e) => setSens(Number(e.target.value))} className="w-full" />
              <span className="text-[11px] font-mono text-gray-700">{Number(sens).toFixed(2)}×</span>
            </label>
          </div>
        </div>
        <div className="px-4 py-3 border-t border-gray-100 flex flex-wrap gap-2 justify-end">
          <button type="button" className="px-3 py-1.5 rounded text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200" onClick={handleReset}>
            Restaurar defaults
          </button>
          <button type="button" className="px-3 py-1.5 rounded text-xs font-medium text-white bg-slate-800 hover:bg-slate-900" onClick={handleSave}>
            Guardar
          </button>
        </div>
      </div>
    </div>
  )
}
