import KPICards from './KPICards'

/**
 * Snapshot estratégico compacto: Plan vs Real (KPIs + Revenue por país).
 * Sin upload visible; filtros se gestionan en App (panel colapsable).
 */
function ExecutiveSnapshotView({ filters = {}, refreshKey = 0 }) {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-gray-800">Snapshot (Plan vs Real)</h2>
      <KPICards key={`snapshot-kpis-${refreshKey}`} filters={filters} compact />
    </div>
  )
}

export default ExecutiveSnapshotView
