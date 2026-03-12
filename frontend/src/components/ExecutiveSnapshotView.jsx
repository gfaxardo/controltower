import KPICards from './KPICards'

/**
 * Snapshot estratégico compacto: Plan vs Real (KPIs + Revenue por país).
 * Sin upload visible; filtros se gestionan en App (panel colapsable).
 */
function ExecutiveSnapshotView({ filters = {}, refreshKey = 0 }) {
  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium text-gray-700">Plan vs Real — KPIs</h3>
      <KPICards key={`snapshot-kpis-${refreshKey}`} filters={filters} compact />
    </div>
  )
}

export default ExecutiveSnapshotView
