import os

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
    'frontend', 'src', 'pages', 'lima-growth-v2', 'sections', 'ExecutionQueueSection.jsx')

with open(path, 'r') as f:
    content = f.read()

# Find the last closing of the main component and add ResultSyncPanel before it
old = '      </SectionCard>\n    </div>\n  )\n}\n'
new = '''      </SectionCard>
      <ResultSyncPanel exports={data.exports} />
    </div>
  )
}

function ResultSyncPanel({ exports }) {
  const [selectedCampaign, setSelectedCampaign] = useState(null)
  const [summary, setSummary] = useState(null)
  const [records, setRecords] = useState(null)
  const [loading, setLoading] = useState(false)

  const campaigns = (exports || []).filter(e => e.campaign_id_external).slice(0, 10)

  const loadResults = async (cid) => {
    setSelectedCampaign(cid)
    setLoading(true)
    try {
      const { default: api } = await import('../../../services/api.js')
      const [s, r] = await Promise.all([
        api.get('/yego-lima-growth/loopcontrol/results/summary?campaign_id_external=' + cid),
        api.get('/yego-lima-growth/loopcontrol/results?campaign_id_external=' + cid)
      ])
      setSummary(s.data)
      setRecords(r.data)
    } catch { setSummary(null); setRecords(null) }
    finally { setLoading(false) }
  }

  return (
    <SectionCard title="Resultados LoopControl" color="#7c3aed">
      {!campaigns.length ? <p className="text-xs text-gray-400 py-4 text-center">No hay campanas exportadas con resultados.</p> :
        <div className="mb-3">
          <select value={selectedCampaign || ''} onChange={e => loadResults(e.target.value)} className="text-xs border border-gray-200 rounded-lg px-2 py-1.5">
            <option value="">Seleccionar campana...</option>
            {campaigns.map(c => <option key={c.campaign_id_external} value={c.campaign_id_external}>{c.campaign_name || c.campaign_id_external} ({new Date(c.exported_at).toLocaleDateString('es-PE')})</option>)}
          </select>
        </div>}
      {loading && <LoadingState text="Cargando resultados..." />}
      {summary && (
        <div className="grid grid-cols-4 gap-2 mb-3 text-center text-xs">
          <div className="bg-gray-50 rounded-lg p-2"><p className="font-bold">{formatNum(summary.total_results)}</p><p className="text-gray-400">Total</p></div>
          <div className="bg-emerald-50 rounded-lg p-2"><p className="font-bold text-emerald-700">{formatNum(summary.matched_queue_count)}</p><p className="text-gray-400">Matched</p></div>
          <div className="bg-amber-50 rounded-lg p-2"><p className="font-bold text-amber-700">{formatNum(summary.unmatched_count)}</p><p className="text-gray-400">Unmatched</p></div>
          <div className="bg-purple-50 rounded-lg p-2"><p className="font-bold text-purple-700">{formatNum(summary.contacted_count)}</p><p className="text-gray-400">Contacted</p></div>
        </div>)}
      {records?.records?.length > 0 && (
        <div className="overflow-x-auto"><table className="w-full text-xs"><thead><tr className="border-b border-gray-100 text-gray-400"><th className="text-left py-1">Driver</th><th className="text-left py-1">Status</th><th className="text-left py-1">Disposition</th><th className="text-left py-1">Agent</th></tr></thead><tbody>{records.records.map((r,i) => (<tr key={i} className="border-b border-gray-50"><td className="py-1">{r.driver_name || r.phone || '—'}</td><td className="py-1"><span className={'px-1.5 py-0.5 rounded text-xs font-medium ' + (r.status==='CONTACTED'?'bg-emerald-100 text-emerald-700':'bg-gray-100 text-gray-600')}>{r.status||'UNKNOWN'}</span></td><td className="py-1">{r.disposition||'—'}</td><td className="py-1 text-gray-500">{r.agent||'—'}</td></tr>))}</tbody></table></div>)}
    </SectionCard>
  )
}

'''

content = content.replace(old, new)

with open(path, 'w') as f:
    f.write(content)

print("ResultSyncPanel added successfully")
