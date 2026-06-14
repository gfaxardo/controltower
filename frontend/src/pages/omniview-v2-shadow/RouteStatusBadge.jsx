/**
 * Omniview V2 — Route Status Badge
 * OV2-UI-V1A: Visual status indicator per navigation taxonomy.
 */
export const STATUS_TAXONOMY = {
  DEFAULT_CERTIFIED: { label: 'Default', color: '#16a34a', bg: '#f0fdf4' },
  ACTIVE_BUILD: { label: 'Active', color: '#d97706', bg: '#fffbeb' },
  LEGACY_FALLBACK: { label: 'Legacy', color: '#6b7280', bg: '#f3f4f6' },
  BLOCKED_DO_NOT_USE: { label: 'Blocked', color: '#dc2626', bg: '#fef2f2' },
  DEV_SANDBOX: { label: 'Dev', color: '#7c3aed', bg: '#f5f3ff' },
};

export function RouteStatusBadge({ status, style }) {
  const t = STATUS_TAXONOMY[status];
  if (!t) return <span style={{ fontSize: 10, color: '#9ca3af', ...style }}>—</span>;
  return (
    <span style={{
      fontSize: 10, fontWeight: 500, padding: '1px 6px', borderRadius: 3,
      color: t.color, background: t.bg, border: `1px solid ${t.color}20`,
      ...style,
    }}>
      {t.label}
    </span>
  );
}

export default RouteStatusBadge;
