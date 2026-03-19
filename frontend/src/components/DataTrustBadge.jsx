/**
 * DataTrustBadge — Capa mínima de confianza de data.
 * OK = verde, WARNING = amarillo, BLOCKED = rojo.
 * Texto corto + tooltip opcional. <10% del header.
 */
const CONFIG = {
  ok: {
    label: 'Data validada',
    className: 'bg-green-100 text-green-800 border-green-300',
    title: 'Datos frescos y fuente canónica activa'
  },
  warning: {
    label: 'Data parcial',
    className: 'bg-amber-100 text-amber-800 border-amber-300',
    title: 'Data parcialmente fresca o en transición'
  },
  blocked: {
    label: 'Data no confiable',
    className: 'bg-red-100 text-red-800 border-red-300',
    title: 'Errores de carga o paridad no validada'
  }
}

function DataTrustBadge ({
  status = 'warning',
  message,
  last_update,
  className: extra = '',
  source_of_truth,
  confidence_score,
  freshness_status,
  completeness_status,
  consistency_status
}) {
  const config = CONFIG[status] || CONFIG.warning
  const label = message || config.label
  const titleParts = [config.title]
  if (last_update) titleParts.push(`Última actualización: ${last_update}`)
  if (source_of_truth) titleParts.push(`Fuente: ${source_of_truth}`)
  if (confidence_score != null) titleParts.push(`Score: ${confidence_score}`)
  if (freshness_status) titleParts.push(`Freshness: ${freshness_status}`)
  if (completeness_status) titleParts.push(`Completeness: ${completeness_status}`)
  if (consistency_status) titleParts.push(`Consistency: ${consistency_status}`)
  const title = titleParts.filter(Boolean).join('. ')

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${config.className} ${extra}`}
      title={title}
    >
      {label}
    </span>
  )
}

export default DataTrustBadge
export { CONFIG as DATA_TRUST_CONFIG }
