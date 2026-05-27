/**
 * PilotWorkboard — FASE H2
 * Real Operations Pilot Preparation
 *
 * Proporciona:
 *  - Readiness status
 *  - Scope recomendado
 *  - Cohort preview/creation
 *  - Assignment to 5 owners
 *  - Workboard with progress
 *  - Operator daily flow guide
 *  - Learning log
 *
 * NO kanban complejo. NO CRM.
 * Tabla clara y operable.
 */
import { useState, useEffect, useCallback } from 'react'
import api from '../../services/api'

const PRIORITY_COLORS = {
  CRITICAL: 'bg-red-100 text-red-800 border-red-200',
  HIGH: 'bg-amber-100 text-amber-800 border-amber-200',
  MEDIUM: 'bg-blue-100 text-blue-800 border-blue-200',
  LOW: 'bg-gray-100 text-gray-600 border-gray-200',
}

const WF_STATUS_COLORS = {
  UNASSIGNED: 'bg-gray-100 text-gray-500',
  ASSIGNED: 'bg-blue-100 text-blue-700',
  IN_PROGRESS: 'bg-amber-100 text-amber-700',
  CONTACTED: 'bg-emerald-100 text-emerald-700',
  NO_RESPONSE: 'bg-orange-100 text-orange-700',
  RECOVERED: 'bg-green-100 text-green-700',
  CLOSED: 'bg-gray-200 text-gray-500',
  BLOCKED: 'bg-red-100 text-red-700',
}

const QUEUE_LABELS = {
  REGISTERED_NO_FIRST_TRIP: 'No First Trip',
  DECLINING_DRIVERS: 'Declining',
  AT_RISK_DRIVERS: 'At Risk',
  CHURNED_RECENT: 'Recent Churn',
  HIGH_POTENTIAL_UNDERUTILIZED: 'Underutilized',
}

const OBSERVATION_TYPES = [
  { value: 'bad_phone', label: 'Teléfono inválido' },
  { value: 'wrong_queue', label: 'Cola incorrecta' },
  { value: 'useful_queue', label: 'Cola útil' },
  { value: 'unclear_action', label: 'Acción poco clara' },
  { value: 'driver_feedback', label: 'Feedback del driver' },
  { value: 'system_issue', label: 'Problema del sistema' },
  { value: 'other', label: 'Otro' },
]

function formatPct (n) {
  if (n == null) return '—'
  return Number(n).toFixed(1) + '%'
}

export default function PilotWorkboard () {
  const [readiness, setReadiness] = useState(null)
  const [cohortPreview, setCohortPreview] = useState(null)
  const [cohortResult, setCohortResult] = useState(null)
  const [assignResult, setAssignResult] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [learningLog, setLearningLog] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('overview')

  const [scope, setScope] = useState({ queue_types: ['AT_RISK_DRIVERS', 'REGISTERED_NO_FIRST_TRIP'], max_drivers: 100, has_phone_only: true })
  const [creating, setCreating] = useState(false)
  const [assigning, setAssigning] = useState(false)

  const [logForm, setLogForm] = useState({ observation_type: 'bad_phone', observation_note: '' })

  const OWNERS = ['operador1', 'operador2', 'operador3', 'operador4', 'operador5']

  const loadReadiness = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get('/drivers/pilot-readiness', { timeout: 30000 })
      setReadiness(res.data)
      if (res.data?.recommended_scope) {
        setScope({
          queue_types: res.data.recommended_scope.queue_types || ['AT_RISK_DRIVERS', 'REGISTERED_NO_FIRST_TRIP'],
          max_drivers: res.data.recommended_scope.max_drivers || 100,
          has_phone_only: res.data.recommended_scope.has_phone_only !== false,
        })
      }
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Failed to load readiness')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { loadReadiness() }, [loadReadiness])

  const handlePreview = useCallback(async () => {
    setCreating(true)
    setError(null)
    try {
      const res = await api.post('/drivers/pilot/cohort-preview', scope, { timeout: 30000 })
      setCohortPreview(res.data)
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Preview failed')
    } finally { setCreating(false) }
  }, [scope])

  const handleCreate = useCallback(async () => {
    setCreating(true)
    setError(null)
    try {
      const res = await api.post('/drivers/pilot/cohort', scope, { timeout: 30000 })
      setCohortResult(res.data)
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Cohort creation failed')
    } finally { setCreating(false) }
  }, [scope])

  const handleAssign = useCallback(async () => {
    if (!cohortResult?.cohort_id) return
    setAssigning(true)
    setError(null)
    try {
      const res = await api.post('/drivers/pilot/assign', {
        cohort_id: cohortResult.cohort_id,
        owners: OWNERS,
        strategy: 'balanced_by_priority',
      }, { timeout: 30000 })
      setAssignResult(res.data)
    } catch (err) {
      setError(err?.response?.data?.detail || err?.message || 'Assignment failed')
    } finally { setAssigning(false) }
  }, [cohortResult])

  const loadMetrics = useCallback(async () => {
    try {
      const cid = cohortResult?.cohort_id || ''
      const res = await api.get('/drivers/pilot/metrics', { params: cid ? { cohort_id: cid } : {}, timeout: 15000 })
      setMetrics(res.data)
    } catch { /* ignore */ }
  }, [cohortResult])

  useEffect(() => {
    if (cohortResult?.cohort_id) {
      loadMetrics()
      const interval = setInterval(loadMetrics, 30000)
      return () => clearInterval(interval)
    }
  }, [cohortResult?.cohort_id, loadMetrics])

  const loadLog = useCallback(async () => {
    try {
      const cid = cohortResult?.cohort_id || ''
      const res = await api.get('/drivers/pilot/learning-log', { params: cid ? { cohort_id: cid } : {}, timeout: 15000 })
      setLearningLog(res.data?.entries || [])
    } catch { /* ignore */ }
  }, [cohortResult])

  useEffect(() => { loadLog() }, [loadLog])

  const handleLogSubmit = async () => {
    try {
      const cid = cohortResult?.cohort_id || ''
      await api.post('/drivers/pilot/learning-log', {
        cohort_id: cid,
        observation_type: logForm.observation_type,
        observation_note: logForm.observation_note,
      }, { timeout: 15000 })
      setLogForm({ observation_type: 'bad_phone', observation_note: '' })
      loadLog()
    } catch { /* ignore */ }
  }

  return (
    <div className='space-y-4'>
      {/* Header */}
      <div className='bg-ct-card border border-ct-border rounded-xl px-5 py-4'>
        <h2 className='text-lg font-bold text-ct-text'>Operational Pilot</h2>
        <p className='text-xs text-ct-text3 mt-1'>
          Preparación y ejecución de piloto operativo real con 5 operadores. Validar si Drivers sirve para mejorar supply.
        </p>
      </div>

      {/* Tabs internas */}
      <div className='flex gap-1.5 flex-wrap'>
        {[
          { key: 'overview', label: 'Pilot Overview' },
          { key: 'readiness', label: 'Readiness' },
          { key: 'cohort', label: 'Cohort Builder' },
          { key: 'workboard', label: 'Workboard' },
          { key: 'learning', label: 'Learning Log' },
        ].map(t => (
          <button key={t.key} type='button' onClick={() => setActiveTab(t.key)}
            className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${activeTab === t.key ? 'bg-ct-accent text-white shadow-sm' : 'text-ct-text2 hover:text-ct-text hover:bg-ct-border'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {error && (
        <div className='bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-xs text-red-700'>
          {error}
          <button type='button' onClick={() => setError(null)} className='ml-2 text-gray-400 hover:text-gray-600'>&times;</button>
        </div>
      )}

      {/* ── Overview ── */}
      {activeTab === 'overview' && (
        <div className='space-y-4'>
          <div className='bg-blue-50 border border-blue-200 rounded-lg p-4'>
            <h3 className='text-sm font-semibold text-blue-900 mb-2'>Operational Pilot — Objetivo</h3>
            <p className='text-xs text-blue-800 mb-3'>
              Validar si el Driver Operating System permite a operadores humanos gestionar supply de forma efectiva. 5 personas usarán Drivers durante varios días para contactar, recuperar y activar conductores.
            </p>
            <div className='grid grid-cols-2 gap-2 text-[11px] text-blue-800'>
              <div><strong>Duración sugerida:</strong> 5-10 días hábiles</div>
              <div><strong>Operadores:</strong> 5 personas de operaciones</div>
              <div><strong>Casos por operador:</strong> 10-20 (balanceado por prioridad)</div>
              <div><strong>Canales:</strong> Llamada telefónica / WhatsApp</div>
              <div><strong>Qué registrar:</strong> Contacto, resultado, estado siguiente, observaciones</div>
              <div><strong>Métricas observadas:</strong> Contact rate, recovery rate, invalid phone rate, feedback</div>
            </div>
          </div>

          <div className='bg-amber-50 border border-amber-200 rounded-lg p-4'>
            <h3 className='text-sm font-semibold text-amber-900 mb-2'>Qué NO evaluar todavía</h3>
            <ul className='text-xs text-amber-800 list-disc list-inside space-y-1'>
              <li>No atribuir causalidad (¿el sistema causó la recuperación?)</li>
              <li>No medir ROI financiero</li>
              <li>No comparar con grupo de control (sin datos suficientes)</li>
              <li>No automatizar contactos</li>
              <li>No scoring probabilístico de recuperabilidad</li>
            </ul>
          </div>
        </div>
      )}

      {/* ── Readiness ── */}
      {activeTab === 'readiness' && (
        <div className='space-y-4'>
          {loading ? (
            <div className='animate-pulse space-y-2'><div className='h-4 bg-gray-100 rounded w-48' /><div className='h-3 bg-gray-50 rounded w-3/4' /></div>
          ) : readiness ? (
            <>
              <div className='flex items-center gap-3'>
                <span className={`text-sm font-semibold px-3 py-1 rounded-full border ${
                  readiness.status === 'ready' ? 'bg-emerald-50 text-emerald-700 border-emerald-200' :
                  readiness.status === 'warning' ? 'bg-amber-50 text-amber-700 border-amber-200' :
                  'bg-red-50 text-red-700 border-red-200'
                }`}>
                  {readiness.status === 'ready' ? 'Ready' : readiness.status === 'warning' ? 'Warning' : 'Blocked'}
                </span>
                <span className='text-sm font-bold text-ct-text'>Score: {readiness.readiness_score}%</span>
              </div>

              <div className='overflow-x-auto'>
                <table className='w-full text-xs'>
                  <thead>
                    <tr className='text-left text-gray-400 border-b border-gray-100'>
                      <th className='py-1.5 pr-2 font-medium'>Check</th>
                      <th className='py-1.5 pr-2 font-medium'>Status</th>
                      <th className='py-1.5 font-medium'>Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(readiness.checks || []).map((c, i) => (
                      <tr key={i} className='border-b border-gray-50'>
                        <td className='py-1.5 pr-2 text-ct-text font-medium'>{c.name}</td>
                        <td className='py-1.5 pr-2'>
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                            c.status === 'ok' ? 'bg-emerald-100 text-emerald-700' :
                            c.status === 'warning' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'
                          }`}>{c.status}</span>
                        </td>
                        <td className='py-1.5 text-ct-text2'>
                          {c.message}
                          {c.remediation && <span className='text-amber-600 ml-2'>({c.remediation})</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {readiness.blocking_gaps?.length > 0 && (
                <div className='bg-red-50 border border-red-200 rounded-lg p-3'>
                  <div className='text-xs font-semibold text-red-700 mb-1'>Blocking Gaps</div>
                  {readiness.blocking_gaps.map((g, i) => (
                    <div key={i} className='text-[11px] text-red-600'>{g.name}: {g.message}</div>
                  ))}
                </div>
              )}
            </>
          ) : null}
        </div>
      )}

      {/* ── Cohort Builder ── */}
      {activeTab === 'cohort' && (
        <div className='space-y-4'>
          <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
            <h3 className='text-sm font-semibold text-ct-text mb-3'>Scope Configuration</h3>
            <div className='grid grid-cols-2 gap-3 text-xs'>
              <div>
                <label className='block text-ct-text3 mb-1'>Queue Types</label>
                <div className='flex flex-wrap gap-1.5'>
                  {Object.entries(QUEUE_LABELS).map(([k, v]) => (
                    <label key={k} className='inline-flex items-center gap-1 cursor-pointer'>
                      <input type='checkbox' checked={scope.queue_types.includes(k)} onChange={e => {
                        setScope(s => ({
                          ...s,
                          queue_types: e.target.checked ? [...s.queue_types, k] : s.queue_types.filter(q => q !== k),
                        }))
                      }} className='rounded' />
                      <span className='text-[11px]'>{v}</span>
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className='block text-ct-text3 mb-1'>Max Drivers</label>
                <input type='number' min={5} max={500} value={scope.max_drivers} onChange={e => setScope(s => ({ ...s, max_drivers: Number(e.target.value) }))}
                  className='px-2 py-1 border border-ct-border rounded text-xs w-24' />
              </div>
              <div>
                <label className='inline-flex items-center gap-2 cursor-pointer'>
                  <input type='checkbox' checked={scope.has_phone_only} onChange={e => setScope(s => ({ ...s, has_phone_only: e.target.checked }))} className='rounded' />
                  <span className='text-xs'>Only drivers with phone</span>
                </label>
              </div>
            </div>
            <div className='flex gap-2 mt-4'>
              <button type='button' onClick={handlePreview} disabled={creating || scope.queue_types.length === 0}
                className='px-3 py-1.5 rounded bg-blue-500 text-white text-xs font-medium hover:bg-blue-600 disabled:opacity-50'>
                {creating ? 'Loading...' : 'Preview Cohort'}
              </button>
              <button type='button' onClick={handleCreate} disabled={creating || !cohortPreview || scope.queue_types.length === 0}
                className='px-3 py-1.5 rounded bg-green-600 text-white text-xs font-medium hover:bg-green-700 disabled:opacity-50'>
                {creating ? 'Creating...' : 'Create Frozen Cohort'}
              </button>
            </div>
          </div>

          {cohortPreview && (
            <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
              <h3 className='text-sm font-semibold text-ct-text mb-2'>Preview ({cohortPreview.total} drivers)</h3>
              <div className='flex flex-wrap gap-2 text-[11px] text-ct-text2 mb-3'>
                <span>With phone: <strong className='text-emerald-600'>{cohortPreview.with_phone}</strong></span>
                <span>Without phone: <strong className='text-amber-600'>{cohortPreview.without_phone}</strong></span>
                {Object.entries(cohortPreview.by_queue || {}).map(([k, v]) => (
                  <span key={k} className='px-1.5 py-0.5 rounded bg-gray-100 text-gray-600'>{QUEUE_LABELS[k] || k}: {v}</span>
                ))}
              </div>
              <div className='overflow-x-auto max-h-80 overflow-y-auto'>
                <table className='w-full text-[11px]'>
                  <thead>
                    <tr className='text-left text-gray-400 border-b border-gray-100 sticky top-0 bg-white'>
                      <th className='py-1 pr-2'>Driver</th>
                      <th className='py-1 pr-2'>Phone</th>
                      <th className='py-1 pr-2'>Queue</th>
                      <th className='py-1 pr-2'>Priority</th>
                      <th className='py-1 pr-2'>Lifecycle</th>
                      <th className='py-1 pr-2 text-right'>7d</th>
                      <th className='py-1 pr-2 text-right'>30d</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(cohortPreview.drivers || []).slice(0, 50).map((d, i) => (
                      <tr key={i} className='border-b border-gray-50 hover:bg-gray-50/50'>
                        <td className='py-1 pr-2 font-medium text-ct-text truncate max-w-[120px]'>{d.driver_name || d.driver_id?.slice(0, 12)}</td>
                        <td className='py-1 pr-2'>{d.has_phone ? <span className='text-emerald-500'>&#x2713;</span> : <span className='text-amber-500'>&#x2717;</span>}</td>
                        <td className='py-1 pr-2 text-ct-text2'>{QUEUE_LABELS[d.queue_type] || d.queue_type}</td>
                        <td className='py-1 pr-2'><span className={`px-1 py-0.5 rounded text-[9px] font-medium border ${PRIORITY_COLORS[d.queue_priority] || PRIORITY_COLORS.LOW}`}>{d.queue_priority}</span></td>
                        <td className='py-1 pr-2 text-ct-text2'>{d.lifecycle_stage}</td>
                        <td className='py-1 pr-2 text-right'>{d.trips_7d}</td>
                        <td className='py-1 pr-2 text-right'>{d.trips_30d}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(cohortPreview.drivers || []).length > 50 && (
                  <p className='text-[10px] text-gray-400 text-center py-2'>+{(cohortPreview.drivers.length - 50)} more drivers</p>
                )}
              </div>
            </div>
          )}

          {cohortResult && (
            <div className='bg-emerald-50 border border-emerald-200 rounded-lg p-4'>
              <h3 className='text-sm font-semibold text-emerald-800 mb-2'>Cohort Created</h3>
              <div className='text-xs text-emerald-700 space-y-1'>
                <div>ID: <code className='text-emerald-900'>{cohortResult.cohort_id}</code></div>
                <div>Inserted: {cohortResult.inserted} drivers</div>
                {cohortResult.errors?.length > 0 && (
                  <div className='text-amber-600'>Errors: {cohortResult.errors.join(', ')}</div>
                )}
              </div>
              <button type='button' onClick={handleAssign} disabled={assigning}
                className='mt-3 px-3 py-1.5 rounded bg-orange-500 text-white text-xs font-medium hover:bg-orange-600 disabled:opacity-50'>
                {assigning ? 'Assigning...' : `Assign to 5 Operators`}
              </button>
              {assignResult && (
                <div className='mt-3 text-xs text-emerald-700 bg-white/50 rounded p-2'>
                  <div>Assigned: {assignResult.assigned} drivers</div>
                  {assignResult.by_owner && Object.entries(assignResult.by_owner).map(([o, c]) => (
                    <div key={o}>{o}: {c} casos</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Workboard ── */}
      {activeTab === 'workboard' && (
        <div className='space-y-4'>
          {!cohortResult ? (
            <div className='bg-gray-50 border border-gray-200 rounded-lg p-6 text-center text-sm text-gray-500'>
              Crea un cohort en la pestaña &quot;Cohort Builder&quot; para ver el workboard.
            </div>
          ) : (
            <>
              {/* KPI strip */}
              {metrics && (
                <div className='grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-2'>
                  {[
                    { label: 'Assigned', value: metrics.assigned_total, color: 'text-blue-700' },
                    { label: 'Pending', value: metrics.pending_total, color: 'text-gray-600' },
                    { label: 'Contacted', value: metrics.contacted_total, color: 'text-emerald-700' },
                    { label: 'No Response', value: metrics.no_response_total, color: 'text-orange-700' },
                    { label: 'Recovered', value: metrics.recovered_total, color: 'text-green-700' },
                    { label: 'Contact Rate', value: formatPct(metrics.contact_rate), color: 'text-blue-700' },
                    { label: 'Recovery Rate', value: formatPct(metrics.recovery_rate), color: 'text-green-700' },
                  ].map(kpi => (
                    <div key={kpi.label} className='bg-ct-card border border-ct-border rounded-lg px-3 py-2'>
                      <div className='text-[10px] text-ct-text3 uppercase'>{kpi.label}</div>
                      <div className={`text-sm font-bold ${kpi.color}`}>{kpi.value}</div>
                    </div>
                  ))}
                </div>
              )}

              {/* By Owner */}
              {metrics?.outcomes_by_owner && Object.keys(metrics.outcomes_by_owner).length > 0 && (
                <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
                  <h3 className='text-sm font-semibold text-ct-text mb-2'>Outcomes by Owner</h3>
                  <div className='overflow-x-auto'>
                    <table className='w-full text-[11px]'>
                      <thead>
                        <tr className='text-left text-gray-400 border-b border-gray-100'>
                          <th className='py-1 pr-2'>Owner</th>
                          <th className='py-1 pr-2 text-right'>Total</th>
                          <th className='py-1 pr-2 text-right'>Pending</th>
                          <th className='py-1 pr-2 text-right'>Contacted</th>
                          <th className='py-1 pr-2 text-right'>No Resp</th>
                          <th className='py-1 pr-2 text-right'>Recovered</th>
                          <th className='py-1 pr-2 text-right'>Closed</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(metrics.outcomes_by_owner).map(([owner, statuses]) => {
                          const total = Object.values(statuses).reduce((a, b) => a + b, 0)
                          return (
                            <tr key={owner} className='border-b border-gray-50'>
                              <td className='py-1 pr-2 font-medium text-ct-text'>{owner}</td>
                              <td className='py-1 pr-2 text-right font-mono'>{total}</td>
                              <td className='py-1 pr-2 text-right'>{(statuses.UNASSIGNED || 0) + (statuses.ASSIGNED || 0) + (statuses.IN_PROGRESS || 0)}</td>
                              <td className='py-1 pr-2 text-right text-emerald-600'>{statuses.CONTACTED || 0}</td>
                              <td className='py-1 pr-2 text-right text-orange-600'>{statuses.NO_RESPONSE || 0}</td>
                              <td className='py-1 pr-2 text-right text-green-600'>{statuses.RECOVERED || 0}</td>
                              <td className='py-1 pr-2 text-right text-gray-400'>{statuses.CLOSED || 0}</td>
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Daily Flow Guide */}
              <div className='bg-blue-50 border border-blue-200 rounded-lg p-4'>
                <h3 className='text-sm font-semibold text-blue-900 mb-2'>Operator Daily Flow</h3>
                <ol className='text-xs text-blue-800 list-decimal list-inside space-y-1.5'>
                  <li><strong>Abrir tus casos asignados</strong> — Filtrar por tu owner en Action Queues.</li>
                  <li><strong>Revisar siguiente caso</strong> — Priorizar CRITICAL y HIGH.</li>
                  <li><strong>Contactar driver</strong> — Llamada o WhatsApp. Usar el teléfono visible.</li>
                  <li><strong>Registrar resultado</strong> — Usar quick actions: Contacted, No Response, Recover, Close.</li>
                  <li><strong>Si teléfono inválido:</strong> Marcar como invalid phone y registrar en Learning Log.</li>
                  <li><strong>Si driver responde:</strong> Registrar recover o seguimiento según resultado.</li>
                  <li><strong>Cerrar o dejar follow-up</strong> — Si requiere segunda llamada, dejar en IN_PROGRESS.</li>
                  <li><strong>Repetir al día siguiente</strong> — Revisar pendientes y continuar.</li>
                </ol>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── Learning Log ── */}
      {activeTab === 'learning' && (
        <div className='space-y-4'>
          <div className='bg-ct-card border border-ct-border rounded-lg p-4'>
            <h3 className='text-sm font-semibold text-ct-text mb-3'>Registrar Observación</h3>
            <div className='flex flex-wrap gap-2 items-end'>
              <div>
                <label className='block text-[10px] text-ct-text3 mb-1'>Tipo</label>
                <select value={logForm.observation_type} onChange={e => setLogForm(f => ({ ...f, observation_type: e.target.value }))}
                  className='px-2 py-1 border border-ct-border rounded text-xs'>
                  {OBSERVATION_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                </select>
              </div>
              <div>
                <label className='block text-[10px] text-ct-text3 mb-1'>Nota</label>
                <input type='text' value={logForm.observation_note} onChange={e => setLogForm(f => ({ ...f, observation_note: e.target.value }))}
                  placeholder='Describe la observación...'
                  className='px-2 py-1 border border-ct-border rounded text-xs w-64' />
              </div>
              <button type='button' onClick={handleLogSubmit} disabled={!logForm.observation_note.trim()}
                className='px-3 py-1.5 rounded bg-ct-accent text-white text-xs font-medium hover:opacity-90 disabled:opacity-50'>
                Registrar
              </button>
            </div>
          </div>

          <div className='bg-ct-card border border-ct-border rounded-lg overflow-hidden'>
            <div className='px-4 py-2 border-b border-ct-border'>
              <h3 className='text-sm font-semibold text-ct-text'>Learning Log ({learningLog.length})</h3>
            </div>
            {learningLog.length === 0 ? (
              <div className='px-4 py-6 text-center text-xs text-ct-text3'>No hay observaciones registradas.</div>
            ) : (
              <div className='overflow-x-auto'>
                <table className='w-full text-xs'>
                  <thead>
                    <tr className='text-left text-gray-400 border-b border-gray-100'>
                      <th className='py-1.5 px-2'>Type</th>
                      <th className='py-1.5 px-2'>Note</th>
                      <th className='py-1.5 px-2'>Owner</th>
                      <th className='py-1.5 px-2'>Driver</th>
                      <th className='py-1.5 px-2'>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {learningLog.map((l, i) => (
                      <tr key={i} className='border-b border-gray-50'>
                        <td className='py-1 px-2'>
                          <span className='px-1.5 py-0.5 rounded text-[10px] bg-gray-100 text-gray-600'>{l.observation_type}</span>
                        </td>
                        <td className='py-1 px-2 text-ct-text'>{l.observation_note}</td>
                        <td className='py-1 px-2 text-ct-text2'>{l.owner || '—'}</td>
                        <td className='py-1 px-2 text-ct-text2 font-mono'>{l.driver_id?.slice(0, 12) || '—'}</td>
                        <td className='py-1 px-2 text-ct-text3'>{l.created_at?.slice(0, 16) || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
