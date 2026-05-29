import { useState } from 'react'
import { getTabGuide } from '../../config/driverTabGuideRegistry'

export default function DriverTabGuide ({ tabKey, dataUnavailable }) {
  const [expanded, setExpanded] = useState(false)
  const guide = getTabGuide(tabKey)

  if (!guide) return null

  return (
    <div className='mb-3'>
      <button
        type='button'
        onClick={() => setExpanded(!expanded)}
        className='w-full flex items-center justify-between px-4 py-2.5 bg-gradient-to-r from-slate-50 to-blue-50/50 border border-slate-200 rounded-lg hover:border-blue-200 transition-colors group'
      >
        <div className='flex items-center gap-2 min-w-0'>
          <span className='text-blue-500 text-sm flex-shrink-0'>{expanded ? '▾' : '▸'}</span>
          <span className='text-xs text-slate-600 truncate'>
            <strong className='text-slate-700'>¿Para qué?</strong>{' '}
            {guide.oneLinePurpose}
          </span>
        </div>
        <span className='text-[10px] text-slate-400 flex-shrink-0 ml-2 group-hover:text-blue-500'>
          {expanded ? 'Ocultar guía' : 'Ver guía'}
        </span>
      </button>

      {expanded && (
        <div className='mt-1.5 border border-slate-200 rounded-lg bg-white px-4 py-3 space-y-2.5 text-xs'>
          <div>
            <div className='font-semibold text-slate-700 mb-0.5'>Qué lograrás</div>
            <div className='text-slate-600'>{guide.whatYouCanDo}</div>
          </div>
          <div>
            <div className='font-semibold text-slate-700 mb-0.5'>Cómo usarlo</div>
            <div className='text-slate-600'>{guide.howToUse}</div>
          </div>
          <div>
            <div className='font-semibold text-slate-700 mb-0.5'>Decisión que permite</div>
            <div className='text-slate-600 italic'>{guide.decisionItSupports}</div>
          </div>
          <div>
            <div className='font-semibold text-slate-700 mb-0.5'>Siguiente paso recomendado</div>
            <div className='text-slate-600'>{guide.nextStep}</div>
          </div>
          {guide.audience && (
            <div className='pt-1 border-t border-slate-100'>
              <span className='text-[10px] text-slate-400'>Audiencia: {guide.audience}</span>
            </div>
          )}
        </div>
      )}

      {dataUnavailable && (
        <div className='mt-1.5 px-4 py-2.5 bg-amber-50 border border-amber-200 rounded-lg text-[11px] text-amber-700'>
          <strong>Data no disponible:</strong>{' '}
          {guide.dataUnavailableMessage || 'No significa necesariamente que no exista data. Significa que esta vista no pudo leer su fuente operativa. Revisa Data Foundation u Operational Health.'}
        </div>
      )}
    </div>
  )
}
