/**
 * Recoverability Intelligence Dashboard — Fase 2C.1
 * Shadow mode: diagnostico de recoverability sin automatizacion.
 * NO genera recomendaciones. NO acciona intervenciones.
 */
import { useState, useEffect, useCallback } from 'react'
import {
  getRecoverabilitySummary,
  getRecoverabilityDistribution,
  getRecoverabilityTop,
  getRecoverabilityShadowPriority,
  getDriverRecoverability,
} from '../../services/api'

function formatNum(n) {
  if (n == null || n === '') return '—'
  const num = Number(n)
  if (Number.isNaN(num)) return '—'
  return num.toLocaleString('es-ES', { maximumFractionDigits: 2 })
}

const STATE_COLORS = {
  HIGHLY_RECOVERABLE: '#22c55e',
  RECOVERABLE: '#3b82f6',
  LOW_RECOVERABLE: '#eab308',
  HARD_TO_RECOVER: '#f97316',
  NON_RECOVERABLE: '#ef4444',
}

const STATE_LABELS = {
  HIGHLY_RECOVERABLE: 'Highly Recoverable',
  RECOVERABLE: 'Recoverable',
  LOW_RECOVERABLE: 'Low Recoverable',
  HARD_TO_RECOVER: 'Hard to Recover',
  NON_RECOVERABLE: 'Non Recoverable',
}

const URGENCY_COLORS = { HIGH: '#ef4444', MEDIUM: '#f97316', LOW: '#3b82f6', NONE: '#6b7280' }

export default function RecoverabilityIntelligenceDashboard() {
  const [summary, setSummary] = useState(null)
  const [distribution, setDistribution] = useState(null)
  const [topDrivers, setTopDrivers] = useState([])
  const [shadowPriority, setShadowPriority] = useState([])
  const [selectedDriver, setSelectedDriver] = useState(null)
  const [driverDetail, setDriverDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [params, setParams] = useState({ period_days: 28 })

  const fetchAll = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [s, d, t, p] = await Promise.all([
        getRecoverabilitySummary(params).catch(() => null),
        getRecoverabilityDistribution(params).catch(() => null),
        getRecoverabilityTop({ ...params, limit: 20 }).catch(() => null),
        getRecoverabilityShadowPriority({ ...params, limit: 30 }).catch(() => null),
      ])
      setSummary(s)
      setDistribution(d)
      setTopDrivers(t?.drivers || [])
      setShadowPriority(p?.priority || [])
    } catch (e) {
      setError(e.message || 'Error loading data')
    } finally {
      setLoading(false)
    }
  }, [params])

  useEffect(() => { fetchAll() }, [fetchAll])

  const handleDriverClick = async (driverId) => {
    setSelectedDriver(driverId)
    setDriverDetail(null)
    try {
      const d = await getDriverRecoverability(driverId, params)
      setDriverDetail(d)
    } catch (e) {
      setDriverDetail({ error: e.message })
    }
  }

  if (loading) return <div style={{ padding: 24, color: '#94a3b8' }}>Loading recoverability data...</div>

  return (
    <div style={{ padding: 24, color: '#e2e8f0' }}>
      {/* Shadow mode banner */}
      <div style={{
        background: 'linear-gradient(135deg, #1e293b, #0f172a)',
        border: '1px solid #f97316',
        borderRadius: 8,
        padding: '12px 20px',
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <span style={{ fontSize: 20 }}>⚠️</span>
        <div>
          <strong style={{ color: '#f97316' }}>SHADOW MODE</strong>
          <span style={{ color: '#94a3b8', marginLeft: 10 }}>
            Recoverability scores are diagnostic only. No automated interventions. No SAC queue routing. No recommendations generated.
          </span>
        </div>
      </div>

      {error && (
        <div style={{ background: '#450a0a', border: '1px solid #ef4444', borderRadius: 8, padding: 12, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* KPI Cards */}
      {summary?.summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 16, marginBottom: 24 }}>
          <KpiCard label="Total Drivers" value={formatNum(summary.summary.total_drivers)} color="#94a3b8" />
          <KpiCard label="Avg Recoverability" value={formatNum(summary.summary.avg_recoverability_score)} color="#3b82f6" />
          <KpiCard label="Highly Recoverable" value={formatNum(summary.summary.highly_recoverable_count)} color={STATE_COLORS.HIGHLY_RECOVERABLE} />
          <KpiCard label="Recoverable" value={formatNum(summary.summary.recoverable_count)} color={STATE_COLORS.RECOVERABLE} />
          <KpiCard label="Hard to Recover" value={formatNum(summary.summary.hard_to_recover_count)} color={STATE_COLORS.HARD_TO_RECOVER} />
          <KpiCard label="Non Recoverable" value={formatNum(summary.summary.non_recoverable_count)} color={STATE_COLORS.NON_RECOVERABLE} />
        </div>
      )}

      {/* Distribution chart + Top recoverable */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 24 }}>
        {/* Distribution */}
        {distribution?.distribution && (
          <div style={panelStyle}>
            <h3 style={sectionTitle}>Recoverability Distribution</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {distribution.distribution.map((d) => (
                <div key={d.state} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: `${Math.max(d.pct, 2)}%`,
                    height: 28,
                    background: d.color,
                    borderRadius: 4,
                    minWidth: 4,
                    transition: 'width 0.3s',
                    display: 'flex',
                    alignItems: 'center',
                    paddingLeft: 8,
                    fontSize: 12,
                    fontWeight: 600,
                    overflow: 'hidden',
                    whiteSpace: 'nowrap',
                  }}>
                    {d.pct > 5 ? `${d.label} (${d.pct}%)` : ''}
                  </div>
                  {d.pct <= 5 && <span style={{ fontSize: 12, color: '#94a3b8' }}>{d.label}: {d.count} ({d.pct}%)</span>}
                </div>
              ))}
            </div>
            <div style={{ marginTop: 12, fontSize: 11, color: '#64748b' }}>
              Total: {distribution.total_drivers} drivers in scope
            </div>
          </div>
        )}

        {/* Top recoverable */}
        <div style={panelStyle}>
          <h3 style={sectionTitle}>Top Recoverable Drivers</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ color: '#94a3b8', textAlign: 'left' }}>
                <th style={{ padding: '4px 8px' }}>#</th>
                <th style={{ padding: '4px 8px' }}>Driver</th>
                <th style={{ padding: '4px 8px' }}>Score</th>
                <th style={{ padding: '4px 8px' }}>State</th>
              </tr>
            </thead>
            <tbody>
              {topDrivers.slice(0, 10).map((d) => (
                <tr
                  key={d.driver_id}
                  onClick={() => handleDriverClick(d.driver_id)}
                  style={{
                    cursor: 'pointer',
                    borderBottom: '1px solid #1e293b',
                    background: selectedDriver === d.driver_id ? '#1e293b' : 'transparent',
                  }}
                >
                  <td style={{ padding: '4px 8px', color: '#64748b' }}>{d.rank}</td>
                  <td style={{ padding: '4px 8px', fontFamily: 'monospace', fontSize: 11 }}>
                    {d.driver_id?.substring(0, 12)}...
                  </td>
                  <td style={{ padding: '4px 8px', fontWeight: 600, color: STATE_COLORS[d.recoverability_state] }}>
                    {d.recoverability_score}
                  </td>
                  <td style={{ padding: '4px 8px' }}>
                    <span style={{
                      background: STATE_COLORS[d.recoverability_state] + '22',
                      color: STATE_COLORS[d.recoverability_state],
                      padding: '2px 6px',
                      borderRadius: 4,
                      fontSize: 10,
                      fontWeight: 600,
                    }}>
                      {STATE_LABELS[d.recoverability_state]}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Shadow Priority */}
      {shadowPriority.length > 0 && (
        <div style={panelStyle}>
          <h3 style={sectionTitle}>Shadow Priority Ranking (Visual Only)</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ color: '#94a3b8', textAlign: 'left' }}>
                  <th style={thStyle}>Rank</th>
                  <th style={thStyle}>Tier</th>
                  <th style={thStyle}>Driver</th>
                  <th style={thStyle}>Score</th>
                  <th style={thStyle}>State</th>
                  <th style={thStyle}>Urgency</th>
                  <th style={thStyle}>Percentile</th>
                </tr>
              </thead>
              <tbody>
                {shadowPriority.slice(0, 20).map((d) => (
                  <tr key={d.driver_id} style={trStyle} onClick={() => handleDriverClick(d.driver_id)}>
                    <td style={tdStyle}>{d.rank}</td>
                    <td style={tdStyle}>
                      <span style={{
                        background: d.priority_tier_shadow === 'TIER_1' ? '#22c55e22' : d.priority_tier_shadow === 'TIER_2' ? '#3b82f622' : '#64748b22',
                        color: d.priority_tier_shadow === 'TIER_1' ? '#22c55e' : d.priority_tier_shadow === 'TIER_2' ? '#3b82f6' : '#64748b',
                        padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                      }}>{d.priority_tier_shadow}</span>
                    </td>
                    <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: 11 }}>{d.driver_id?.substring(0, 12)}...</td>
                    <td style={{ ...tdStyle, fontWeight: 600, color: STATE_COLORS[d.recoverability_state] }}>{d.recoverability_score}</td>
                    <td style={tdStyle}>
                      <span style={{ background: STATE_COLORS[d.recoverability_state] + '22', color: STATE_COLORS[d.recoverability_state], padding: '1px 6px', borderRadius: 4, fontSize: 10, fontWeight: 600 }}>
                        {STATE_LABELS[d.recoverability_state]}
                      </span>
                    </td>
                    <td style={{ ...tdStyle, color: URGENCY_COLORS[d.intervention_urgency] }}>{d.intervention_urgency}</td>
                    <td style={tdStyle}>{d.percentile}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div style={{ marginTop: 8, fontSize: 10, color: '#64748b' }}>
            Shadow priority ranking — no SAC queue routing. Visual diagnostic only.
          </div>
        </div>
      )}

      {/* Driver Detail Panel */}
      {selectedDriver && driverDetail && !driverDetail.error && (
        <div style={panelStyle}>
          <h3 style={sectionTitle}>
            Driver Detail: <span style={{ fontFamily: 'monospace', fontSize: 13 }}>{selectedDriver}</span>
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: 16 }}>
            {/* Score overview */}
            <div>
              <div style={{ fontSize: 32, fontWeight: 700, color: STATE_COLORS[driverDetail.recoverability_state] }}>
                {driverDetail.recoverability_score}
              </div>
              <div style={{ color: '#94a3b8', fontSize: 13 }}>
                State: {STATE_LABELS[driverDetail.recoverability_state] || driverDetail.recoverability_state}
              </div>
              <div style={{ color: '#64748b', fontSize: 11, marginTop: 4 }}>
                Urgency: {driverDetail.intervention_urgency}
              </div>
            </div>

            {/* Explainability */}
            <div>
              <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 8 }}>Explainability</div>
              <div style={{
                background: '#0f172a',
                border: '1px solid #1e293b',
                borderRadius: 6,
                padding: 12,
                fontSize: 12,
                color: '#cbd5e1',
                lineHeight: 1.6,
              }}>
                {driverDetail.explainability_text}
              </div>
            </div>
          </div>

          {/* Score breakdown */}
          {driverDetail.score_breakdown && (
            <div style={{ marginTop: 16 }}>
              <div style={{ color: '#94a3b8', fontSize: 12, marginBottom: 8 }}>Score Breakdown</div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
                <thead>
                  <tr style={{ color: '#64748b', textAlign: 'left' }}>
                    <th style={thStyle}>Component</th>
                    <th style={thStyle}>Score</th>
                    <th style={thStyle}>Weight</th>
                    <th style={thStyle}>Contribution</th>
                    <th style={thStyle}>Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(driverDetail.score_breakdown).filter(([k]) => k !== 'modifiers').map(([key, val]) => (
                    <tr key={key} style={trStyle}>
                      <td style={{ ...tdStyle, color: '#e2e8f0' }}>{key}</td>
                      <td style={tdStyle}>{val.score}</td>
                      <td style={tdStyle}>{(val.weight * 100).toFixed(0)}%</td>
                      <td style={tdStyle}>{val.contribution}</td>
                      <td style={{ ...tdStyle, fontSize: 10, color: '#94a3b8' }}>{val.evidence}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {/* Modifiers */}
              {driverDetail.score_breakdown.modifiers?.length > 0 && (
                <div style={{ marginTop: 8 }}>
                  <span style={{ color: '#64748b', fontSize: 11 }}>Modifiers: </span>
                  {driverDetail.score_breakdown.modifiers.map((m, i) => (
                    <span key={i} style={{
                      background: m.points > 0 ? '#22c55e22' : '#ef444422',
                      color: m.points > 0 ? '#22c55e' : '#ef4444',
                      padding: '2px 6px', borderRadius: 4, fontSize: 10, marginRight: 6,
                    }}>
                      {m.modifier} ({m.points > 0 ? '+' : ''}{m.points})
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

const panelStyle = {
  background: '#0f172a',
  border: '1px solid #1e293b',
  borderRadius: 8,
  padding: 16,
}

const sectionTitle = {
  fontSize: 14,
  fontWeight: 600,
  color: '#94a3b8',
  marginBottom: 12,
  borderBottom: '1px solid #1e293b',
  paddingBottom: 8,
}

const thStyle = { padding: '4px 8px', borderBottom: '1px solid #1e293b' }
const tdStyle = { padding: '4px 8px', borderBottom: '1px solid #1e293b', color: '#94a3b8' }
const trStyle = { cursor: 'pointer', borderBottom: '1px solid #1e293b' }

function KpiCard({ label, value, color }) {
  return (
    <div style={{
      background: '#0f172a',
      border: '1px solid #1e293b',
      borderRadius: 8,
      padding: 16,
      textAlign: 'center',
    }}>
      <div style={{ fontSize: 24, fontWeight: 700, color }}>{value}</div>
      <div style={{ fontSize: 11, color: '#64748b', marginTop: 4 }}>{label}</div>
    </div>
  )
}
