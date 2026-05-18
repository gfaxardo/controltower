/**
 * RenameProjectionVersionModal — Modal compacto para renombrar versión.
 *
 * Permite editar display_name y description.
 * plan_version_key es visible pero NO editable.
 *
 * Motor: Control Foundation (ACTIVE)
 */
import { useState } from 'react'
import { patchPlanVersion } from '../../services/api.js'

export default function RenameProjectionVersionModal ({
  planVersionKey,
  currentDisplayName,
  currentDescription,
  onClose,
  onSaved,
}) {
  const [displayName, setDisplayName] = useState(currentDisplayName || '')
  const [description, setDescription] = useState(currentDescription || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const handleSave = async () => {
    const trimmed = displayName.trim()
    if (!trimmed) {
      setError('El nombre visible es obligatorio')
      return
    }
    setSaving(true)
    setError(null)
    try {
      const result = await patchPlanVersion(planVersionKey, trimmed, description.trim() || null)
      if (onSaved) onSaved(result)
    } catch (e) {
      const msg = e?.response?.data?.detail || e.message || 'Error al guardar'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  const inputCls = 'w-full border border-ct-border rounded-md px-2.5 py-1.5 text-sm text-ct-text bg-ct-card focus:ring-2 focus:ring-blue-400 focus:border-blue-400 outline-none'
  const disabledCls = 'w-full border border-ct-border rounded-md px-2.5 py-1.5 text-sm text-ct-text3 bg-ct-surface'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ct-nav/40 p-4" role="dialog" aria-modal="true" onClick={onClose}>
      <div className="bg-ct-card rounded-xl shadow-xl border border-ct-border w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="px-4 py-3 border-b border-ct-border flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-ct-text">Renombrar versión</h3>
            <p className="text-[10px] text-ct-text3 mt-0.5">Solo se edita el nombre visible</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="p-1 rounded text-ct-text3 hover:text-ct-text hover:bg-ct-border transition-colors disabled:opacity-30"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Body */}
        <div className="px-4 py-3 space-y-3">
          {/* plan_version_key — solo lectura */}
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-ct-text3">Llave técnica</label>
            <input
              type="text"
              value={planVersionKey}
              disabled
              className={disabledCls}
            />
            <p className="text-[9px] text-ct-text3 mt-0.5">La llave técnica no se puede modificar.</p>
          </div>

          {/* display_name — editable */}
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-ct-text3">Nombre visible</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => { setDisplayName(e.target.value); setError(null) }}
              placeholder="Ej. Proyección base R27 Q2"
              className={inputCls}
              autoFocus
              disabled={saving}
            />
          </div>

          {/* description — opcional */}
          <div>
            <label className="text-[10px] font-semibold uppercase tracking-wider text-ct-text3">Descripción (opcional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Nota sobre esta versión..."
              className={inputCls + ' resize-none'}
              rows={2}
              disabled={saving}
            />
          </div>

          {/* Error */}
          {error && (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-[11px] text-red-800">{error}</div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-ct-border flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={saving}
            className="px-3 py-1.5 rounded-md text-xs font-medium text-ct-text2 bg-ct-surface border border-ct-border hover:bg-ct-bg transition-colors disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !displayName.trim()}
            className="px-3 py-1.5 rounded-md text-xs font-semibold bg-blue-600 text-white hover:bg-blue-700 transition-colors shadow-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
          >
            {saving && (
              <span className="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
            )}
            {saving ? 'Guardando…' : 'Guardar'}
          </button>
        </div>
      </div>
    </div>
  )
}
