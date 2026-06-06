export default function FreshnessBadge({ freshness, compact = false }) {
  if (!freshness) return null

  const { status, age_minutes, threshold_minutes, source, reason, remediation } = freshness

  const config = {
    FRESH:    { bg: 'bg-green-50', text: 'text-green-700', dot: 'bg-green-400', label: 'Fresh' },
    WARNING:  { bg: 'bg-yellow-50', text: 'text-yellow-700', dot: 'bg-yellow-400', label: 'Warning' },
    STALE:    { bg: 'bg-red-50', text: 'text-red-700', dot: 'bg-red-400', label: 'Stale' },
    UNKNOWN:  { bg: 'bg-gray-50', text: 'text-gray-500', dot: 'bg-gray-300', label: 'Unknown' },
  }

  const c = config[status] || config.UNKNOWN

  const tooltip = [
    reason,
    source ? `Source: ${source}` : null,
    age_minutes != null ? `Age: ${Math.round(age_minutes)}min (threshold: ${threshold_minutes}min)` : null,
    remediation || null,
  ].filter(Boolean).join('\n')

  if (compact) {
    return (
      <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${c.bg} ${c.text}`} title={tooltip}>
        <span className={`w-1.5 h-1.5 rounded-full ${c.dot}`} />
        {c.label}
      </span>
    )
  }

  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-xs font-medium ${c.bg} ${c.text}`} title={tooltip}>
      <span className={`w-2 h-2 rounded-full ${c.dot}`} />
      {c.label}
      {age_minutes != null && <span className="opacity-70">{Math.round(age_minutes)}m</span>}
    </span>
  )
}

export function SectionFreshnessBadge({ data, domain }) {
  const freshness = data?.freshness?.[domain]
  if (!freshness) return null
  return <FreshnessBadge freshness={freshness} compact />
}
