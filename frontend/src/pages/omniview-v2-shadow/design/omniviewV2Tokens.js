const tokens = {
  colors: {
    ok: '#22c55e',
    warning: '#f59e0b',
    blocked: '#ef4444',
    shadow: '#6366f1',
    notComparable: '#9ca3af',
    estimated: '#a855f7',
    selected: '#3b82f6',

    okBg: '#f0fdf4',
    warningBg: '#fffbeb',
    blockedBg: '#fef2f2',
    hoverBg: '#eff6ff',
    mutedBg: '#f3f4f6',
    disabledBg: '#e5e7eb',

    textPrimary: '#111827',
    textSecondary: '#6b7280',
    textMuted: '#9ca3af',

    borderOk: '#22c55e',
    borderWarning: '#f59e0b',
    borderBlocked: '#ef4444',
    borderSelected: '#3b82f6',
    borderDefault: '#e5e7eb',
  },

  typography: {
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
    fontFamilyMono: "'SF Mono', 'Fira Code', 'Fira Mono', 'Roboto Mono', monospace",
    fontSizeCell: '13px',
    fontSizeHeader: '12px',
    fontSizeKpi: '24px',
    fontSizeKpiLabel: '11px',
    fontSizeBadge: '10px',
    fontWeightCell: 400,
    fontWeightHeader: 600,
    fontWeightKpi: 700,
    fontWeightBadge: 500,
    lineHeightCell: '40px',
    lineHeightHeader: '40px',
  },

  spacing: {
    cellPaddingX: '8px',
    cellPaddingY: '0px',
    headerPaddingX: '8px',
    headerPaddingY: '0px',
    matrixGap: 0,
    badgeGap: '4px',
    sectionGap: '16px',
  },

  borderRadius: {
    cell: '0px',
    badge: '3px',
    inspector: '8px',
  },

  shadows: {
    inspector: '0 4px 24px rgba(0,0,0,0.12)',
    header: '0 1px 3px rgba(0,0,0,0.08)',
    selected: '0 0 0 2px #3b82f6 inset',
  },

  zIndex: {
    header: 100,
    stickyColumn: 50,
    inspector: 200,
    inspectorBackdrop: 190,
    badge: 10,
  },

  rowHeight: 40,
  headerHeight: 44,

  columnWidthByGrain: {
    hour: 70,
    day: 90,
    week: 100,
    month: 100,
  },

  badgeSizes: {
    height: '18px',
    fontSize: '10px',
    paddingX: '6px',
  },

  iconSizes: {
    small: '12px',
    medium: '16px',
    large: '20px',
  },

  transitionDurations: {
    fast: '100ms',
    normal: '150ms',
    slow: '300ms',
  },

  densityModes: {
    comfortable: {
      rowHeight: 40,
      cellFontSize: '13px',
      cellPaddingX: '8px',
    },
    compact: {
      rowHeight: 32,
      cellFontSize: '12px',
      cellPaddingX: '6px',
    },
  },
};

export default tokens;
