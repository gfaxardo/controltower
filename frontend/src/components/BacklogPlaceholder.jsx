import { useLocation } from 'react-router-dom'

function BacklogPlaceholder () {
  const location = useLocation()

  return (
    <div className="min-h-[50vh] flex items-center justify-center">
      <div className="max-w-md mx-auto text-center px-4">
        <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-ct-border flex items-center justify-center">
          <svg className="w-7 h-7 text-ct-text3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
        </div>
        <h2 className="text-base font-semibold text-ct-text mb-1.5">Vista no disponible</h2>
        <p className="text-xs text-ct-text2 mb-1">
          Esta vista está en backlog o requiere validación antes de estar disponible en producción.
        </p>
        <p className="text-2xs text-ct-text3 font-mono bg-ct-surface rounded px-2 py-1 inline-block">
          {location.pathname}
        </p>
      </div>
    </div>
  )
}

export default BacklogPlaceholder
