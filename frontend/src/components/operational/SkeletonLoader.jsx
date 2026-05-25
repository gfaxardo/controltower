/**
 * SkeletonLoader — FASE 1H.3
 * Carga esqueletal ligera para evitar flashing y layout jumps.
 * Usa el mismo layout que el contenido real para evitar CLS.
 */

export function SkeletonBar ({ className = '' }) {
  return (
    <div className={`rounded animate-pulse bg-gray-200 ${className}`} />
  )
}

export function SkeletonText ({ lines = 1, className = '' }) {
  return (
    <div className={`space-y-1.5 ${className}`}>
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonBar
          key={i}
          className={`h-3 ${i === lines - 1 && lines > 1 ? 'w-3/4' : 'w-full'}`}
        />
      ))}
    </div>
  )
}

export function SkeletonCard ({ className = '' }) {
  return (
    <div className={`rounded-lg border border-gray-200 bg-white p-4 space-y-3 ${className}`}>
      <SkeletonBar className="h-4 w-1/3" />
      <SkeletonBar className="h-8 w-1/2" />
      <SkeletonText lines={2} />
    </div>
  )
}

/** Skeleton específico para la matriz Omniview. Mantiene el layout de la tabla real. */
export function OmniviewMatrixSkeleton ({ rows = 8, cols = 6 }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="px-4 py-3 bg-slate-800 flex gap-3">
        <SkeletonBar className="h-3 w-16 bg-slate-600" />
        <SkeletonBar className="h-3 w-20 bg-slate-600" />
        {Array.from({ length: Math.min(cols, 8) }).map((_, i) => (
          <SkeletonBar key={i} className={`h-3 bg-slate-600 ${i === 0 ? 'w-14 ml-auto' : 'w-12'}`} />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-2 px-4 py-2 border-b border-gray-100">
          <SkeletonBar className={`h-3 rounded bg-gray-200 ${i === 0 ? 'w-24' : 'w-20'}`} />
          <SkeletonBar className="h-3 w-12 rounded bg-gray-100 ml-auto" />
          {Array.from({ length: Math.min(cols, 6) }).map((_, j) => (
            <SkeletonBar key={j} className="h-3 w-10 rounded bg-gray-100" />
          ))}
        </div>
      ))}
      <div className="flex items-center gap-2 px-4 py-2 text-xs text-gray-400">
        <span className="inline-block w-3 h-3 border-[1.5px] border-gray-300 border-t-blue-500 rounded-full animate-spin" />
        Cargando datos...
      </div>
    </div>
  )
}

export default SkeletonBar
