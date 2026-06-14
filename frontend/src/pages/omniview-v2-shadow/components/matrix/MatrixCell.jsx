import { memo, useCallback, useMemo } from 'react';
import CellBadge from './CellBadge';
import CellDelta from './CellDelta';
import { formatValue } from '../base/MetricValue';
import { getCellToneClass } from '../../omniviewV2ColorSemantics';
import { getPlanRealDisplay } from '../../omniviewV2PlanReal';

function _badgeForSource(sourceSystem, canonicalReady) {
  if (!canonicalReady) return 'SHADOW';
  if (sourceSystem === 'CT_TRIPS_2026') return 'CT_BRIDGE';
  if (sourceSystem === 'YANGO_API_RAW') return 'YANGO_API';
  return null;
}

function _badgeForFallback(fallbackUsed) {
  if (fallbackUsed) return 'FALLBACK';
  return null;
}

const MatrixCell = memo(function MatrixCell({
  cell,
  rowId,
  columnId,
  grain = 'day',
  metricId = 'orders',
  viewMode = 'real',
  columnPeriodStatus,
  isSelected,
  onClick,
  density,
}) {
  const handleClick = useCallback(() => {
    if (cell && onClick) {
      onClick(cell);
    }
  }, [cell, onClick]);

  if (!cell) {
    return (
      <div className="ov2-cell ov2-cell--muted" style={{ minWidth: `var(--ov2-col-width-${grain})` }}>
        —
      </div>
    );
  }

  const cellStatus = cell.cell_status || 'OK';
  const isFuture = columnPeriodStatus === 'FUTURE';
  const canonicalReady = cell.canonical_ready ?? true;
  const fallbackUsed = cell.fallback_used || false;
  const valueNull = cell.value == null;

  const tone = getCellToneClass(cell, metricId, isFuture);
  let cellClass = `ov2-cell ov2-cell--${tone}`;

  if (isSelected) cellClass += ' ov2-cell--selected';

  const sourceBadge = _badgeForSource(cell.source_system, canonicalReady);
  const fallbackBadge = _badgeForFallback(fallbackUsed);
  const showEstimated = cell.is_estimated;
  const showDelta = cell.comparison_status != null || cell.delta_value != null || cell.delta_pct != null;
  const showPeriodBadge = columnPeriodStatus === 'PARTIAL';
  const showMissing = valueNull || cell.formatted_value === 'N/A';
  const isPlanRealMode = viewMode === 'plan_real';

  // Plan vs Real display (OV2-UI-P1F)
  const pvr = isPlanRealMode && !isFuture && !valueNull
    ? getPlanRealDisplay(cell, metricId)
    : null;

  return (
    <div
      className={cellClass}
      style={{ minWidth: `var(--ov2-col-width-${grain})`, position: 'relative' }}
      onClick={handleClick}
      title={`${cell.metric_id || ''} — ${cell.label || ''} | ${columnPeriodStatus || ''} | ${canonicalReady ? 'CANONICAL' : 'SHADOW'}`}
    >
      {sourceBadge && !isFuture && <CellBadge type={sourceBadge} />}
      {fallbackBadge && !isFuture && <CellBadge type={fallbackBadge} />}

      <span style={{ fontWeight: 600 }}>
        {showMissing ? <span style={{ color: 'var(--ov2-text-muted)' }}>N/A</span> : (cell.formatted_value || formatValue(cell.value, cell.unit))}
      </span>

      {/* Plan vs Real subtitle (OV2-UI-P1F) */}
      {pvr && pvr.attainmentPct != null && (
        <span style={{ fontSize: 9, color: 'var(--ov2-text-secondary)', display: 'block', lineHeight: 1.2 }}>
          {pvr.attainmentFormatted} · {pvr.tone === 'negative' ? 'Behind' : pvr.tone === 'positive' ? 'Ahead' : 'OK'}
        </span>
      )}
      {pvr && pvr.status === 'missing' && (
        <span style={{ fontSize: 9, color: 'var(--ov2-text-muted)', display: 'block' }}>NO DATA</span>
      )}

      {showEstimated && <CellBadge type="ESTIMATED" />}
      {showPeriodBadge && <CellBadge type="PARTIAL" />}

      {showDelta && !isFuture && !valueNull && (
        <CellDelta status={cell.comparison_status} value={cell.delta_value} pct={cell.delta_pct} />
      )}

      {showDelta && !isFuture && valueNull && (
        <span style={{ position: 'absolute', bottom: 1, left: 4, fontSize: 9, color: 'var(--ov2-text-muted)' }}>NO COMP</span>
      )}
    </div>
  );
});

export default MatrixCell;
