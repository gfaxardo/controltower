/**
 * OperationalOpportunitiesView — subtab "Oportunidades Operativas"
 *
 * Muestra sugerencias operativas, contextuales y prioridades detectadas por el motor
 * de proyección. Lenguaje de oportunidad, no de decisión automática.
 *
 * Motor: Diagnostic Engine (READY NEXT) — lectura de oportunidades detectadas.
 * NO es Action Engine ni Decision Engine.
 */
import { useEffect, useState } from 'react'
import { getOmniviewProjection, getControlLoopPlanVersions, getPlanVersions } from '../../services/api.js'

const GRAINS = [
  { id: 'monthly', label: 'Mensual' },
  { id: 'weekly', label: 'Semanal' },
  { id: 'daily', label: 'Diario' },
]

const CONFIDENCE_LABEL = { high: 'Alta', medium: 'Media', low: 'Baja' }
const CONFIDENCE_COLOR = { high: 'text-emerald-700', medium: 'text-amber-700', low: 'text-ct-text2' }

const PRIORITY_BAND_COLORS = {
  CRITICAL: 'bg-red-100 text-red-800 border-red-200',
  HIGH: 'bg-amber-100 text-amber-800 border-amber-200',
  MEDIUM: 'bg-blue-100 text-blue-800 border-blue-200',
  LOW: 'bg-ct-surface text-ct-text border-ct-border',
}

function OperationalOpportunitiesView () {
  const [grain, setGrain] = useState('monthly')
  const [planVersion, setPlanVersion] = useState('')
  const [planVersions, setPlanVersions] = useState([])
  const [projectionMeta, setProjectionMeta] = useState(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState(null)
  const [activeTab, setActiveTab] = useState('operacionales')

  useEffect(() => {
    let cancelled = false
    async function loadVersions () {
      try {
        const [cpv, pv] = await Promise.all([
          getControlLoopPlanVersions(),
          getPlanVersions(),
        ])
        if (cancelled) return
        const normalize = (item) => {
          if (typeof item === 'string') return { key: item, label: item }
          return { key: item.plan_version_key || item.plan_version || item.key, label: item.display_name || item.label || item.plan_version_key || item.plan_version || item.key }
        }
        const rawList = [
          ...(cpv?.versions || cpv?.plan_versions || []),
          ...(Array.isArray(pv) ? pv : (pv?.versions || []))
        ]
        const unique = [...new Map(rawList.map(v => {
          const n = normalize(v)
          return [n.key, n]
        })).values()]
        setPlanVersions(unique)
        if (unique.length > 0) setPlanVersion(unique[0].key)
      } catch (e) {
        if (!cancelled) console.warn('No se pudieron cargar versiones de plan:', e.message)
      }
    }
    loadVersions()
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!planVersion) return
    let cancelled = false
    setLoading(true)
    setErr(null)
    async function load () {
      try {
        const params = { plan_version: planVersion, grain }
        const meta = await getOmniviewProjection(params)
        if (cancelled) return
        setProjectionMeta(meta)
      } catch (e) {
        if (!cancelled) setErr(e.message || 'Error al cargar datos')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [planVersion, grain])

  const opsSuggestions = Array.isArray(projectionMeta?.operational_suggestions) ? projectionMeta.operational_suggestions : []
  const ctxSuggestions = Array.isArray(projectionMeta?.contextual_suggestions) ? projectionMeta.contextual_suggestions : []

  const totalOps = opsSuggestions.length
  const totalCtx = ctxSuggestions.length

  const renderSuggestionRow = (s, idx) => {
    if (!s) return null
    const name = s.recommended_action_name || s.opportunity?.headline || `Oportunidad ${idx + 1}`
    const city = s.city || s.country || ''
    const slice = s.business_slice_name || s.lob || ''
    const impact = s.expected_impact != null ? `${Number(s.expected_impact).toFixed(1)}%` : '—'
    const confidence = s.confidence || s.opportunity?.confidence || 'medium'
    const priority = s.priority_band || s.severity || 'MEDIUM'
    const why = s.why || s.rationale || s.opportunity?.explanation || ''
    const owner = s.owner_suggested || s.target_team || ''
    const channel = s.channel_suggested || ''

    return (
      <div key={idx} className="rounded-lg border border-ct-border bg-ct-card px-4 py-3 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-ct-text truncate">{name}</p>
            <p className="text-[11px] text-ct-text2 mt-0.5">
              {[city, slice].filter(Boolean).join(' · ') || 'Sin ubicación'}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${PRIORITY_BAND_COLORS[priority] || PRIORITY_BAND_COLORS.MEDIUM}`}>
              {priority}
            </span>
            <span className={`text-[10px] font-medium ${CONFIDENCE_COLOR[confidence] || 'text-ct-text2'}`}>
              Confianza: {CONFIDENCE_LABEL[confidence] || confidence}
            </span>
          </div>
        </div>

        {why && (
          <p className="text-[11px] text-ct-text mb-2 line-clamp-3">{why}</p>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-ct-text2">
          <span>Impacto estimado: <strong className="text-ct-text">{impact}</strong></span>
          {owner && <span>Owner sugerido: <strong className="text-ct-text">{owner}</strong></span>}
          {channel && <span>Canal: <strong className="text-ct-text">{channel}</strong></span>}
        </div>

        <div className="mt-2 pt-2 border-t border-ct-border flex items-center gap-3 text-[10px]">
          <span className="text-ct-text3">
            Requiere validación manual
          </span>
          <span className="text-ct-text3">|</span>
          <span className="text-blue-600">
            Oportunidad operativa
          </span>
          <span className="text-ct-text3 flex-1 text-right">
            Ejecución no habilitada
          </span>
        </div>
      </div>
    )
  }

  const renderCtxRow = (c, idx) => {
    if (!c) return null
    const headline = c.opportunity?.headline || `Oportunidad contextual ${idx + 1}`
    const city = c.opportunity?.city || c.country || ''
    const slice = c.opportunity?.business_slice_name || c.opportunity?.lob || ''
    const driversAffected = c.estimated_supply_gap_drivers || c.estimated_recoverable_drivers || ''
    const confidence = c.opportunity?.confidence || 'medium'
    const explanation = c.opportunity?.explanation || ''

    return (
      <div key={idx} className="rounded-lg border border-violet-200 bg-violet-50/40 px-4 py-3 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-2 mb-2">
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-violet-900 truncate">{headline}</p>
            <p className="text-[11px] text-violet-600/80 mt-0.5">
              {[city, slice].filter(Boolean).join(' · ') || 'Sin ubicación'}
            </p>
          </div>
          <span className={`text-[10px] font-medium ${CONFIDENCE_COLOR[confidence] || 'text-ct-text2'} flex-shrink-0`}>
            Confianza: {CONFIDENCE_LABEL[confidence] || confidence}
          </span>
        </div>

        {explanation && (
          <p className="text-[11px] text-violet-800/80 mb-2 line-clamp-3">{explanation}</p>
        )}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] text-violet-600/80">
          {driversAffected && <span>Conductores afectados: <strong>{Number(driversAffected).toLocaleString()}</strong></span>}
        </div>

        <div className="mt-2 pt-2 border-t border-violet-150 flex items-center gap-3 text-[10px]">
          <span className="text-violet-400">
            Oportunidad contextual
          </span>
          <span className="text-violet-400">|</span>
          <span className="text-violet-400">
            Ver trazabilidad en Omniview Matrix
          </span>
        </div>
      </div>
    )
  }

  const renderEmpty = (type) => (
    <div className="rounded-lg border border-ct-border bg-ct-surface px-4 py-8 text-center">
      <p className="text-sm text-ct-text2">No se detectaron oportunidades {type} para esta versión del plan.</p>
      <p className="text-[11px] text-ct-text3 mt-1">Esto puede indicar que el sistema no encontró gaps significativos o que los datos de proyección no están completos.</p>
    </div>
  )

  return (
    <div className="space-y-4">
      {/* Header + Controls */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-ct-text">Oportunidades Operativas</h3>
          <p className="text-[11px] text-ct-text2 mt-0.5">
            Sugerencias detectadas por el motor de proyección. Requieren validación manual. La ejecución automática no está habilitada.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={planVersion}
            onChange={(e) => setPlanVersion(e.target.value)}
            className="text-xs border border-slate-300 rounded-md px-2 py-1.5 bg-ct-card text-ct-text"
          >
            <option value="">— Versión del plan —</option>
            {planVersions.map((v) => (
              <option key={v.key} value={v.key}>
                {v.label || v.key}
              </option>
            ))}
          </select>
          <div className="flex rounded-md border border-slate-300 overflow-hidden">
            {GRAINS.map((g) => (
              <button
                key={g.id}
                type="button"
                onClick={() => setGrain(g.id)}
                className={`px-2.5 py-1.5 text-[11px] font-medium transition-colors ${
                  grain === g.id ? 'bg-slate-800 text-white' : 'bg-ct-card text-ct-text hover:bg-ct-surface'
                }`}
              >
                {g.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2.5 text-[11px] text-amber-900">
        <strong>Información operativa preliminar.</strong> Las oportunidades que se muestran aquí son detectadas automáticamente por el sistema. No constituyen decisiones automáticas ni campañas activas. Toda ejecución requiere validación manual del equipo operativo.
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-ct-border pb-2">
        <button
          type="button"
          onClick={() => setActiveTab('operacionales')}
          className={`px-3 py-1.5 rounded-t text-xs font-medium transition-colors ${
            activeTab === 'operacionales'
              ? 'bg-ct-card border border-b-white border-ct-border text-ct-text -mb-[1px] relative z-10'
              : 'text-ct-text2 hover:text-ct-text'
          }`}
        >
          Operacionales ({totalOps})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('contextuales')}
          className={`px-3 py-1.5 rounded-t text-xs font-medium transition-colors ${
            activeTab === 'contextuales'
              ? 'bg-ct-card border border-b-white border-ct-border text-ct-text -mb-[1px] relative z-10'
              : 'text-ct-text2 hover:text-ct-text'
          }`}
        >
          Contextuales ({totalCtx})
        </button>
      </div>

      {/* Loading / Error */}
      {loading && (
        <div className="flex items-center gap-2 text-xs text-ct-text2 py-12 justify-center">
          <span className="inline-block w-3.5 h-3.5 border-2 border-slate-300 border-t-blue-500 rounded-full animate-spin" />
          Cargando oportunidades…
        </div>
      )}
      {err && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-xs text-red-800">{err}</div>
      )}

      {/* Content */}
      {!loading && !err && activeTab === 'operacionales' && (
        <div className="space-y-3">
          {opsSuggestions.length > 0
            ? opsSuggestions.map((s, i) => renderSuggestionRow(s, i))
            : renderEmpty('operacionales')}
          {opsSuggestions.length > 0 && (
            <p className="text-[10px] text-ct-text3 text-center pt-1">
              {opsSuggestions.length} oportunidad{opsSuggestions.length !== 1 ? 'es' : ''} operacional{opsSuggestions.length !== 1 ? 'es' : ''} detectada{opsSuggestions.length !== 1 ? 's' : ''}
            </p>
          )}
        </div>
      )}

      {!loading && !err && activeTab === 'contextuales' && (
        <div className="space-y-3">
          {ctxSuggestions.length > 0
            ? ctxSuggestions.map((c, i) => renderCtxRow(c, i))
            : renderEmpty('contextuales')}
          {ctxSuggestions.length > 0 && (
            <p className="text-[10px] text-ct-text3 text-center pt-1">
              {ctxSuggestions.length} oportunidad{ctxSuggestions.length !== 1 ? 'es' : ''} contextual{ctxSuggestions.length !== 1 ? 'es' : ''} detectada{ctxSuggestions.length !== 1 ? 's' : ''}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

export default OperationalOpportunitiesView
