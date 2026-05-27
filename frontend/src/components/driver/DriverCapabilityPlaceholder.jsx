/**
 * DriverCapabilityPlaceholder — FASE H3.1
 *
 * Governance placeholder for capabilities not yet built.
 * Shows status, layer, phase, dependencies, and what's missing.
 * NO simulation, NO fake data, NO operational execution here.
 */
import { useMemo } from 'react'
import { getCapabilityMeta } from '../../config/operationalMaturityRegistry.js'
import { DriverCapabilityBanner } from '../operational/MaturityIndicators.jsx'

function DepBadge ({ dep }) {
  return (
    <span className='px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-600 border border-gray-200'>
      {dep}
    </span>
  )
}

export default function DriverCapabilityPlaceholder ({ moduleKey }) {
  const meta = useMemo(() => getCapabilityMeta(moduleKey), [moduleKey])

  const layerName = meta?.layer || 'Unknown'
  const description = meta?.description || 'Capability not yet operational.'
  const governanceReason = meta?.governanceReason || 'Under construction.'
  const dependencies = meta?.dependencies || []
  const endpoints = meta?.endpoints || []
  const phase = meta?.phase || 'TBD'
  const statusLabel = meta?.statusLabel || 'Not Ready'
  const engineLabel = meta?.engine || 'TBD'

  return (
    <div className='space-y-4'>
      <DriverCapabilityBanner moduleKey={moduleKey} />

      <div className='bg-ct-card border border-ct-border rounded-xl p-6'>
        <div className='flex items-baseline gap-3 flex-wrap mb-4'>
          <h2 className='text-lg font-semibold text-ct-text'>{meta?.label || moduleKey}</h2>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${
            meta?.productionReady
              ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
              : 'bg-amber-50 text-amber-700 border-amber-200'
          }`}>
            {statusLabel}
          </span>
        </div>

        <div className='grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm'>
          <div className='space-y-3'>
            <div>
              <div className='text-xs text-ct-text3 uppercase tracking-wide mb-1'>Layer</div>
              <div className='text-ct-text font-medium'>{layerName}</div>
            </div>
            <div>
              <div className='text-xs text-ct-text3 uppercase tracking-wide mb-1'>Engine</div>
              <div className='text-ct-text'>{engineLabel}</div>
            </div>
            <div>
              <div className='text-xs text-ct-text3 uppercase tracking-wide mb-1'>Phase</div>
              <div className='text-ct-text font-medium'>{phase}</div>
            </div>
          </div>
          <div className='space-y-3'>
            <div>
              <div className='text-xs text-ct-text3 uppercase tracking-wide mb-1'>Description</div>
              <div className='text-ct-text2'>{description}</div>
            </div>
            <div>
              <div className='text-xs text-ct-text3 uppercase tracking-wide mb-1'>Status</div>
              <div className='text-ct-text2'>{governanceReason}</div>
            </div>
          </div>
        </div>
      </div>

      <div className='bg-amber-50 border border-amber-200 rounded-lg p-4'>
        <h3 className='text-sm font-semibold text-amber-900 mb-2'>No operational execution here yet</h3>
        <p className='text-xs text-amber-800'>
          This capability is visible as a roadmap preview. It is not ready for operational use.
        </p>
      </div>

      {dependencies.length > 0 && (
        <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
          <h3 className='text-sm font-semibold text-ct-text mb-2'>Dependencies</h3>
          <div className='flex flex-wrap gap-1.5'>
            {dependencies.map((d, i) => <DepBadge key={i} dep={d} />)}
          </div>
        </div>
      )}

      {endpoints.length > 0 && (
        <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
          <h3 className='text-sm font-semibold text-ct-text mb-2'>Required Endpoints / Data Sources</h3>
          <ul className='text-xs text-ct-text2 list-disc list-inside space-y-0.5'>
            {endpoints.map((ep, i) => <li key={i}>{ep}</li>)}
          </ul>
        </div>
      )}

      <div className='bg-blue-50 border border-blue-200 rounded-lg p-4'>
        <h3 className='text-sm font-semibold text-blue-900 mb-1'>¿Qué falta?</h3>
        <p className='text-xs text-blue-800'>
          {governanceReason}
        </p>
        <p className='text-xs text-blue-700 mt-2'>
          This capability will be activated when its dependencies are met and its engine phase is ACTIVE.
        </p>
      </div>
    </div>
  )
}
