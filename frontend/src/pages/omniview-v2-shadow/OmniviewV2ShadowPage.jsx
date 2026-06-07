import { useState, useCallback, useEffect } from 'react';
import useOmniviewV2Shell from './hooks/useOmniviewV2Shell';
import useOmniviewV2Matrix from './hooks/useOmniviewV2Matrix';
import { useOmniviewV2PlanReal } from './hooks/useOmniviewV2PlanReal';
import { getOmniviewV2OperatingDate } from '../../services/api';
import OmniviewV2CommandHeader from './components/layout/OmniviewV2CommandHeader';
import OmniviewV2ContextBar from './components/layout/OmniviewV2ContextBar';
import OmniviewV2ExecutiveState from './components/layout/OmniviewV2ExecutiveState';
import OmniviewV2AlertStrip from './components/layout/OmniviewV2AlertStrip';
import OmniviewV2SectionShell from './components/layout/OmniviewV2SectionShell';
import MatrixShell from './components/matrix/MatrixShell';
import CellInspector from './components/matrix/CellInspector';
import MatrixSkeleton from './components/matrix/MatrixSkeleton';
import OmniviewV2GlobalEmptyState from './components/OmniviewV2GlobalEmptyState';
import './design/MatrixVisualSystem.css';

const today = new Date().toISOString().slice(0, 10);

function OmniviewV2ShadowPage() {
  const [sourceSystem, setSourceSystem] = useState('CT_TRIPS_2026');
  const [grain, setGrain] = useState('day');
  const [metricId, setMetricId] = useState('orders');
  const [viewMode, setViewMode] = useState('real');
  const [dateFrom, setDateFrom] = useState('');  // Will be set by operating-date
  const [dateTo, setDateTo] = useState('');
  const [selectedCell, setSelectedCell] = useState(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [operatingDate, setOperatingDate] = useState(null);

  // On mount: fetch operating date and set defaults
  useEffect(() => {
    let cancelled = false;
    getOmniviewV2OperatingDate({ source_system: sourceSystem }).then((data) => {
      if (!cancelled && data?.default_date) {
        setOperatingDate(data);
        const latest = data.default_date;
        setDateFrom(latest);
        setDateTo(latest);
      }
    }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  // When grain changes, reset date range to smart defaults
  useEffect(() => {
    if (!operatingDate?.latest_closed_date) return;
    const latest = operatingDate.latest_closed_date;
    const d = new Date(latest);
    if (grain === 'day') {
      d.setDate(d.getDate() - 6);
      setDateFrom(d.toISOString().slice(0, 10));
      setDateTo(latest);
    } else if (grain === 'week') {
      d.setDate(d.getDate() - 56);
      setDateFrom(d.toISOString().slice(0, 10));
      setDateTo(latest);
    } else if (grain === 'month') {
      d.setMonth(d.getMonth() - 5);
      setDateFrom(d.toISOString().slice(0, 10).slice(0, 7) + '-01');
      setDateTo(latest.slice(0, 7) + '-01');
    }
  }, [grain, operatingDate]);

  const { data: shellData, loading: shellLoading, error: shellError, refetch: shellRefetch } = useOmniviewV2Shell(
    sourceSystem, grain, dateFrom || null, dateTo || null
  );

  const { matrixData: realMatrixData, usingFallback, error: matrixError, refetch: matrixRefetch } = useOmniviewV2Matrix(
    sourceSystem, grain, metricId, dateFrom || null, dateTo || null, shellData
  );

  const { planData, loading: planLoading } = useOmniviewV2PlanReal(
    metricId, dateFrom || null, dateTo || null
  );

  // Select active matrix data based on view mode
  const activeMatrixData = viewMode === 'plan_real' ? planData : realMatrixData;
  const matrixData = activeMatrixData;
  const loading = shellLoading;
  const matrixLoading = !matrixData && !matrixError && !shellLoading;

  const kpiStrip = shellData?.sections?.find((s) => s.section_id === 'kpi_strip');
  const executive = shellData?.sections?.find((s) => s.section_id === 'executive_state');
  const alertsSection = shellData?.sections?.find((s) => s.section_id === 'alerts_warnings');
  const coverage = shellData?.coverage || {};

  const allSections = shellData?.sections || [];
  const allWarnings = shellData?.sections?.flatMap((s) => s.warnings || []) || [];

  // View status: only EMPTY if matrix loaded and has 0 cells
  const matrixMeta = matrixData?.metadata || {};
  const cellsArr = matrixData?.cells || [];
  const hasData = cellsArr.length > 0;
  const hasNoDataWarning = (matrixData?.warnings || []).some(
    (w) => w.code === 'NO_DATA'
  );
  const viewStatus = hasData ? 'READY' : (matrixData && !hasData) ? 'EMPTY' : 'LOADING';
  const latestAvailableDate = operatingDate?.latest_closed_date || matrixMeta.data_date || '';
  const isTodayEmpty = !hasData && dateFrom === today && dateTo === today;

  const handleCellClick = useCallback((cell) => {
    setSelectedCell(cell);
    setInspectorOpen(true);
  }, []);

  const handleCloseInspector = useCallback(() => {
    setInspectorOpen(false);
    setSelectedCell(null);
  }, []);

  const handleGoToLatestDate = useCallback(() => {
    if (latestAvailableDate) {
      setDateFrom(latestAvailableDate);
      setDateTo(latestAvailableDate);
      handleCloseInspector();
    }
  }, [latestAvailableDate, handleCloseInspector]);

  const handleViewSourceHealth = useCallback(() => {
    const el = document.getElementById('shell-section-source_health');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.style.boxShadow = '0 0 0 3px #f59e0b';
      setTimeout(() => { el.style.boxShadow = ''; }, 2000);
    }
  }, []);

  const handleChangeDateRange = useCallback(() => {
    const el = document.querySelector('.ov2-command-header input[type="date"]');
    if (el) {
      el.focus();
      el.style.boxShadow = '0 0 0 3px #3b82f6';
      setTimeout(() => { el.style.boxShadow = ''; }, 2000);
    }
  }, []);

  // Collapse sections when empty
  const filteredSections = viewStatus === 'EMPTY'
    ? allSections.filter((s) =>
        ['source_health', 'executive_state', 'alerts_warnings', 'lineage_audit'].includes(s.section_id)
      )
    : allSections;

  const handleSourceChange = useCallback((newSource) => {
    setSourceSystem(newSource);
    handleCloseInspector();
  }, [handleCloseInspector]);

  const handleAlertClick = useCallback((warning) => {
    const targetSection = allSections.find(
      (s) => s.warnings && s.warnings.some((w) => w.code === warning.code)
    );
    if (targetSection) {
      const el = document.getElementById(`section-${targetSection.section_id}`);
      el?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [allSections]);

  const freshness = shellData?.freshness?.last_refreshed_at || '';

  // Don't render until operating date is loaded and dates are set
  if (!dateFrom || !operatingDate) {
    return (
      <div className="ov2-matrix-shell" style={{ height: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f9fafb' }}>
        <MatrixSkeleton />
      </div>
    );
  }

  // Only show full error page if BOTH shell and matrix fail
  if (shellError && matrixError) {
    return (
      <div className="ov2-matrix-shell" style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#f9fafb' }}>
        <div className="ov2-command-header">
          <span style={{ fontWeight: 700, fontSize: 14 }}>OV2 Shadow</span>
          <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--ov2-text-muted)' }}>Error</span>
        </div>
        <div className="ov2-empty" style={{ flex: 1 }}>
          <div style={{ fontSize: 40, marginBottom: 8, opacity: 0.3 }}>!</div>
          <div>{shellError?.message || shellError}</div>
          <button
            onClick={shellRefetch}
            style={{ marginTop: 12, padding: '8px 16px', border: '1px solid var(--ov2-border-color)', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="ov2-matrix-shell" style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: '#f9fafb' }}>
      {/* Safety Banner */}
      {sourceSystem === 'YANGO_API_RAW' && (
        <div style={{
          background: 'var(--ov2-bg-warning)',
          color: '#92400e',
          fontSize: 12,
          textAlign: 'center',
          padding: '4px 16px',
          fontWeight: 500,
        }}>
          SHADOW MODE — Yango API is NOT canonical. Read-only. No operational decisions.
        </div>
      )}

      {/* Fallback Banner — temporary adapter active */}
      {usingFallback && (
        <div style={{
          background: '#fef3c7',
          color: '#92400e',
          fontSize: 11,
          textAlign: 'center',
          padding: '3px 16px',
          fontWeight: 500,
        }}>
          MATRIX_FALLBACK_ACTIVE — Using shell adapter. Real /matrix endpoint unavailable.
        </div>
      )}

      {/* Command Header */}
      <OmniviewV2CommandHeader
        sourceSystem={sourceSystem}
        canonicalReady={shellData?.canonical_ready ?? false}
        grain={grain}
        dateFrom={dateFrom}
        dateTo={dateTo}
        coveragePct={coverage.coverage_pct}
        freshness={freshness}
        onSourceChange={handleSourceChange}
        onGrainChange={setGrain}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
      />

      {/* Context Bar */}
      <OmniviewV2ContextBar
        sourceSystem={sourceSystem}
        grain={grain}
        dateFrom={dateFrom}
        dateTo={dateTo}
        selectedSection={null}
      />

      {/* Mode + KPI Selector */}
      <div style={{ display: 'flex', gap: 8, padding: '6px 16px', background: '#fafafa', borderBottom: '1px solid var(--ov2-border-color)', fontSize: 12, alignItems: 'center' }}>
        <span style={{ fontWeight: 600, color: '#6b7280', marginRight: 4 }}>Mode:</span>
        <button onClick={() => setViewMode('real')} style={{
          padding: '4px 12px', borderRadius: 4, border: viewMode === 'real' ? '2px solid #22c55e' : '1px solid #e5e7eb',
          background: viewMode === 'real' ? '#f0fdf4' : '#fff', cursor: 'pointer', fontSize: 12, fontWeight: viewMode === 'real' ? 600 : 400,
          color: viewMode === 'real' ? '#166534' : '#6b7280',
        }}>Real Matrix</button>
        <button onClick={() => { setViewMode('plan_real'); setGrain('month'); }} style={{
          padding: '4px 12px', borderRadius: 4, border: viewMode === 'plan_real' ? '2px solid #6366f1' : '1px solid #e5e7eb',
          background: viewMode === 'plan_real' ? '#eef2ff' : '#fff', cursor: 'pointer', fontSize: 12, fontWeight: viewMode === 'plan_real' ? 600 : 400,
          color: viewMode === 'plan_real' ? '#3730a3' : '#6b7280',
        }}>Plan vs Real (Monthly)</button>
        <span style={{ color: '#d1d5db', margin: '0 4px' }}>|</span>
        <span style={{ fontWeight: 600, color: '#6b7280', marginRight: 4 }}>KPI:</span>
        {['orders','revenue','active_drivers','avg_ticket','trips_per_driver'].map((m) => (
          <button key={m} onClick={() => setMetricId(m)} style={{
            padding: '4px 10px', borderRadius: 4, border: metricId === m ? '2px solid #3b82f6' : '1px solid #e5e7eb',
            background: metricId === m ? '#eff6ff' : '#fff', cursor: 'pointer', fontSize: 11, fontWeight: metricId === m ? 600 : 400,
            color: metricId === m ? '#1d4ed8' : '#6b7280',
          }}>
            {m === 'orders' ? 'Trips' : m === 'revenue' ? 'Revenue' : m === 'active_drivers' ? 'Drivers' : m === 'avg_ticket' ? 'Ticket' : 'TPD'}
          </button>
        ))}
      </div>
      )}
      <OmniviewV2ContextBar
        sourceSystem={sourceSystem}
        grain={grain}
        dateFrom={dateFrom}
        dateTo={dateTo}
        selectedSection={null}
      />

      {/* KPI Selector Bar */}
      <div style={{ display: 'flex', gap: 4, padding: '6px 16px', background: '#fafafa', borderBottom: '1px solid var(--ov2-border-color)', fontSize: 12 }}>
        {['orders','revenue','active_drivers','avg_ticket','trips_per_driver'].map((m) => (
          <button key={m} onClick={() => setMetricId(m)} style={{
            padding: '4px 12px', borderRadius: 4, border: metricId === m ? '2px solid #3b82f6' : '1px solid #e5e7eb',
            background: metricId === m ? '#eff6ff' : '#fff', cursor: 'pointer', fontSize: 12, fontWeight: metricId === m ? 600 : 400,
            color: metricId === m ? '#1d4ed8' : '#6b7280',
          }}>
            {m === 'orders' ? 'Trips' : m === 'revenue' ? 'Revenue' : m === 'active_drivers' ? 'Drivers' : m === 'avg_ticket' ? 'Avg Ticket' : 'TPD'}
          </button>
        ))}
      </div>

      {/* Alert Strip */}
      <OmniviewV2AlertStrip warnings={allWarnings} onAlertClick={handleAlertClick} />

      {/* Global Empty State */}
      {viewStatus === 'EMPTY' && (
        <OmniviewV2GlobalEmptyState
          sourceSystem={sourceSystem}
          grain={grain}
          dateFrom={dateFrom}
          dateTo={dateTo}
          latestAvailableDate={latestAvailableDate}
          isToday={isTodayEmpty}
          onGoToLatestDate={handleGoToLatestDate}
          onViewSourceHealth={handleViewSourceHealth}
          onChangeDateRange={handleChangeDateRange}
        />
      )}

      {/* Executive State */}
      {kpiStrip && viewStatus !== 'EMPTY' && (
        <OmniviewV2ExecutiveState
          kpis={kpiStrip.kpis || []}
          onMetricClick={(kpi) => {
            const el = document.getElementById('ov2-matrix-zone');
            el?.scrollIntoView({ behavior: 'smooth' });
          }}
        />
      )}

      {/* Section Shell */}
      <OmniviewV2SectionShell sections={filteredSections} />

      {/* Matrix Zone */}
      <div id="ov2-matrix-zone" style={{ flex: 1, overflow: 'hidden', margin: '0 16px 0', borderTop: '1px solid var(--ov2-border-color)' }}>
        {loading ? (
          <MatrixSkeleton />
        ) : matrixError && !matrixData ? (
          <div className="ov2-empty">
            <div style={{ fontSize: 32, marginBottom: 8, opacity: 0.3 }}>!</div>
            <div style={{ fontWeight: 600, marginBottom: 4 }}>Matrix Unavailable</div>
            <div style={{ fontSize: 12, color: 'var(--ov2-text-muted)', marginBottom: 4 }}>
              {matrixError}
            </div>
            <div style={{ fontSize: 11, color: 'var(--ov2-text-muted)' }}>
              {sourceSystem} · {grain} · {dateFrom} – {dateTo}
            </div>
            <button
              onClick={matrixRefetch}
              style={{ marginTop: 12, padding: '6px 16px', border: '1px solid var(--ov2-border-color)', borderRadius: 4, cursor: 'pointer', fontSize: 12 }}
            >
              Retry
            </button>
          </div>
        ) : (
          <MatrixShell
            matrixData={matrixData}
            selectedCell={selectedCell ? { rowId: selectedCell.row_id, columnId: selectedCell.column_id } : null}
            onCellClick={handleCellClick}
          />
        )}
      </div>

      {/* Cell Inspector */}
      <CellInspector
        cell={selectedCell}
        isOpen={inspectorOpen}
        onClose={handleCloseInspector}
      />
    </div>
  );
}

export default OmniviewV2ShadowPage;
