/**
 * ProjectionVersionSelector — Selector reutilizable de versiones de proyección.
 *
 * Muestra display_name como texto principal y metadata secundaria.
 * Incluye botón compacto para abrir modal de rename.
 *
 * Motor: Control Foundation (ACTIVE)
 */
import { useState } from 'react'
import RenameProjectionVersionModal from './RenameProjectionVersionModal.jsx'

const miniSelectCls =
  'uppercase border border-ct-border rounded-md text-xs px-2 py-1 bg-ct-card outline-none text-ct-text focus:ring-1 focus:ring-blue-400 tracking-wide'

export default function ProjectionVersionSelector ({
  versions = [],
  selectedVersionKey = '',
  onChange,
  onRenameSuccess,
  disabled = false,
  label = 'Plan',
}) {
  const [renameOpen, setRenameOpen] = useState(false)

  const selected = Array.isArray(versions)
    ? versions.find(v => v.key === selectedVersionKey)
    : null

  const display = selected?.display_name || selected?.label || selectedVersionKey || '—'

  const meta = []
  if (selected?.source_filename) meta.push(selected.source_filename)
  if (selected?.row_count != null) meta.push(`${selected.row_count} filas`)
  if (selected?.uploaded_at) meta.push(String(selected.uploaded_at).slice(0, 10))
  if (selected?.status && selected.status !== 'active') meta.push(selected.status)

  const handleRenameSaved = (result) => {
    setRenameOpen(false)
    if (onRenameSuccess) onRenameSuccess(result)
  }

  return (
    <>
      <div className="flex items-center gap-1.5">
        <span className="text-[11px] font-medium text-ct-text3">{label}</span>
        {versions.length > 0 ? (
          <>
            <select
              className={miniSelectCls}
              value={selectedVersionKey}
              onChange={(e) => onChange(e.target.value)}
              disabled={disabled}
            >
              {versions.map((v) => (
                <option key={v.key} value={v.key}>
                  {v.display_name || v.label || v.key}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => setRenameOpen(true)}
              disabled={disabled || !selectedVersionKey}
              className="p-1 rounded text-ct-text3 hover:text-ct-text hover:bg-ct-border transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
              title="Renombrar versión"
            >
              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
              </svg>
            </button>
          </>
        ) : (
          <span className="text-[10px] text-amber-600 font-medium">Sin versiones</span>
        )}
        {meta.length > 0 && (
          <span className="text-[9px] text-ct-text3 hidden sm:inline truncate max-w-[12rem]" title={meta.join(' · ')}>
            {meta.join(' · ')}
          </span>
        )}
      </div>

      {renameOpen && selected && (
        <RenameProjectionVersionModal
          planVersionKey={selected.key}
          currentDisplayName={selected.display_name || selected.label || selected.key}
          currentDescription={selected.description || ''}
          onClose={() => setRenameOpen(false)}
          onSaved={handleRenameSaved}
        />
      )}
    </>
  )
}
