import { useState, useCallback, useEffect, useMemo } from 'react';
import useOmniviewV2Shell from './hooks/useOmniviewV2Shell';
import useOmniviewV2Matrix from './hooks/useOmniviewV2Matrix';
import { useOmniviewV2PlanReal } from './hooks/useOmniviewV2PlanReal';
import { useOmniviewV2DrillCell } from './hooks/useOmniviewV2DrillCell';
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
import { exportOmniviewV2Csv } from './omniviewV2Export';
import { getMetricById } from './omniviewV2Metrics';
import { sortMatrixRows } from './omniviewV2Sort';
import { getPresetRange } from './omniviewV2PeriodPresets';
import './design/MatrixVisualSystem.css';

const today = new Date().toISOString().slice(0, 10);

function OmniviewV2ShadowPage() {
  const [sourceSystem, setSourceSystem] = useState('CT_TRIPS_2026');
  const [grain, setGrain] = useState('day');
  const [metricId, setMetricId] = useState('orders');
  const [viewMode, setViewMode] = useState('real');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [country, setCountry] = useState('peru');
  const [city, setCity] = useState('lima');
  const [businessSlice, setBusinessSlice] = useState('');
  const [parkId, setParkId] = useState('');
  const [selectedCell, setSelectedCell] = useState(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [operatingDate, setOperatingDate] = useState(null);
  const [statusBarOpen, setStatusBarOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [sortMode, setSortMode] = useState('default');
  const [activePreset, setActivePreset] = useState('');

  // Period preset handler (OV2-UI-P1E)
  const handlePresetSelect = useCallback((presetId) => {
    const range = getPresetRange(presetId);
    if (range) {
      setDateFrom(range.from);
      setDateTo(range.to);
      setActivePreset(presetId);
    }
  }, []);

  // Custom date change clears active preset
  const handleDateFromChange = useCallback((v) => { setDateFrom(v); setActivePreset(''); }, []);
  const handleDateToChange = useCallback((v) => { setDateTo(v); setActivePreset(''); }, []);

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
    sourceSystem, grain, dateFrom || null, dateTo || null, country, city, businessSlice || null, parkId || null
  );

  const { matrixData: realMatrixData, usingFallback, error: matrixError, refetch: matrixRefetch } = useOmniviewV2Matrix(
    sourceSystem, grain, metricId, dateFrom || null, dateTo || null, shellData, country, city
  );

  const { planData, loading: planLoading } = useOmniviewV2PlanReal(
    metricId, dateFrom || null, dateTo || null
  );

  // Drill data: fetched when a cell is selected
  const { drillData, loading: drillLoading } = useOmniviewV2DrillCell(
    inspectorOpen ? selectedCell : null, grain
  );

  // Sort rows client-side (OV2-UI-P1D)
  const sortedRealData = useMemo(() => {
    if (!realMatrixData || !realMatrixData.rows || !realMatrixData.cells) return realMatrixData;
    if (sortMode === 'default') return realMatrixData;
    const sortedRows = sortMatrixRows(realMatrixData.rows, realMatrixData.cells, sortMode, metricId);
    return { ...realMatrixData, rows: sortedRows };
  }, [realMatrixData, sortMode, metricId]);

  // Select active matrix data based on view mode
  const activeMatrixData = viewMode === 'plan_real' ? planData : sortedRealData;
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

  // CSV Export (OV2-UI-P1C)
  const handleExportCsv = useCallback(() => {
    try {
      exportOmniviewV2Csv({
        matrixData,
        metric: getMetricById(metricId),
        grain,
        filters: { country, city, businessSlice, parkId, dateFrom, dateTo },
        viewMode,
        canonicalReady: shellData?.canonical_ready ?? false,
        freshness,
        operatingDate,
        coverage: coverage.coverage_pct,
        activePreset,
      });
    } catch (e) {
      console.error('OV2 CSV export failed:', e);
    }
  }, [matrixData, metricId, grain, country, city, businessSlice, parkId, dateFrom, dateTo, viewMode, shellData, freshness, operatingDate, coverage]);


  // Keyboard: Escape exits fullscreen
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape' && isFullscreen) setIsFullscreen(false);
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [isFullscreen]);

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
    <div className="ov2-matrix-shell" style={{
      height: isFullscreen ? '100vh' : '100vh',
      width: isFullscreen ? '100vw' : undefined,
      position: isFullscreen ? 'fixed' : undefined,
      top: isFullscreen ? 0 : undefined,
      left: isFullscreen ? 0 : undefined,
      zIndex: isFullscreen ? 9999 : undefined,
      display: 'flex', flexDirection: 'column', background: '#f9fafb'
    }}>
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

      {/* Fallback Banner */}
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

      {/* MVP Banner */}
      <div style={{
        background: '#eff6ff',
        color: '#1d4ed8',
        fontSize: 11,
        textAlign: 'center',
        padding: '2px 16px',
        fontWeight: 500,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        gap: 8,
      }}>
        <span>OV2 MVP — Shadow Mode | V1 remains default</span>
        <button
          onClick={() => setIsFullscreen(!isFullscreen)}
          title={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
          style={{
            padding: '2px 8px',
            fontSize: 10,
            border: '1px solid #bfdbfe',
            borderRadius: 3,
            background: '#fff',
            cursor: 'pointer',
            color: '#1d4ed8',
          }}
        >
          {isFullscreen ? '[Esc] Exit Fullscreen' : '[F] Fullscreen'}
        </button>
      </div>

      {/* Command Header */}
      <OmniviewV2CommandHeader
        sourceSystem={sourceSystem}
        canonicalReady={shellData?.canonical_ready ?? false}
        grain={grain}
        metricId={metricId}
        dateFrom={dateFrom}
        dateTo={dateTo}
        country={country}
        city={city}
        businessSlice={businessSlice}
        parkId={parkId}
        coveragePct={coverage.coverage_pct}
        freshness={freshness}
        onSourceChange={handleSourceChange}
        onGrainChange={setGrain}
        onMetricChange={setMetricId}
        sortMode={sortMode}
        onSortChange={setSortMode}
        activePreset={activePreset}
        onPresetSelect={handlePresetSelect}
        onDateFromChange={handleDateFromChange}
        onDateToChange={handleDateToChange}
        onCountryChange={setCountry}
        onCityChange={setCity}
        onBusinessSliceChange={setBusinessSlice}
        onParkIdChange={setParkId}
        hasData={hasData}
        onExportCsv={handleExportCsv}
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

      {/* Operational Status Bar */}
      <div style={{ borderBottom: '1px solid var(--ov2-border-color)' }}>
        <button onClick={() => setStatusBarOpen(!statusBarOpen)} style={{
          width: '100%', padding: '6px 16px', background: statusBarOpen ? '#f3f4f6' : '#fafafa',
          border: 'none', cursor: 'pointer', fontSize: 11, fontWeight: 600, color: '#6b7280',
          display: 'flex', alignItems: 'center', gap: 8
        }}>
          <span style={{ transform: statusBarOpen ? 'rotate(90deg)' : 'rotate(0deg)', transition: 'transform .2s', display: 'inline-block' }}>{'>'}</span>
          Status{' '}
          <span style={{ color: operatingDate?.freshness_status === 'FRESH' ? '#16a34a' : '#dc2626', fontWeight: 400 }}>
            {operatingDate?.freshness_status || 'UNKNOWN'}
          </span>
          <span style={{ color: '#9ca3af' }}>|</span>
          <span style={{ fontWeight: 400, color: '#6b7280' }}>Date: {operatingDate?.latest_closed_date || '—'}</span>
          <span style={{ color: '#9ca3af' }}>|</span>
          <span style={{ fontWeight: 400, color: '#6b7280' }}>Coverage: {coverage?.coverage_pct != null ? `${coverage.coverage_pct}%` : '—'}</span>
          <span style={{ color: '#9ca3af' }}>|</span>
          <span style={{ fontWeight: 400, color: '#6b7280' }}>Source: {shellData?.canonical_ready ? 'CANONICAL' : 'SHADOW'}</span>
        </button>
        {statusBarOpen && (
          <div style={{ padding: '8px 16px', background: '#f9fafb', fontSize: 11, display: 'flex', flexWrap: 'wrap', gap: 16, borderTop: '1px solid var(--ov2-border-color)' }}>
            <div><strong>Operating:</strong> {operatingDate?.latest_closed_date || '—'}</div>
            <div><strong>Max Available:</strong> {operatingDate?.max_available_date || '—'}</div>
            <div><strong>Has Today:</strong> {operatingDate?.has_today_data ? 'Yes' : 'No'}</div>
            <div><strong>Freshness:</strong> <span style={{ color: operatingDate?.freshness_status === 'FRESH' ? '#16a34a' : '#dc2626' }}>{operatingDate?.freshness_status || '—'}</span></div>
            <div><strong>Coverage:</strong> {coverage?.coverage_pct != null ? `${coverage.coverage_pct}%` : '—'}</div>
            <div><strong>Canonical:</strong> {shellData?.canonical_ready ? 'Yes' : 'No'}</div>
            <div><strong>Fallback:</strong> {usingFallback ? 'ACTIVE' : 'None'}</div>
            <div><strong>Source:</strong> {sourceSystem}</div>
            <div><strong>Grain:</strong> {grain}</div>
          </div>
        )}
      </div>

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
            metricId={metricId}
            viewMode={viewMode}
            selectedCell={selectedCell ? { rowId: selectedCell.row_id, columnId: selectedCell.column_id } : null}
            onCellClick={handleCellClick}
          />
        )}
      </div>

      {/* Cell Inspector */}
      <CellInspector
        cell={selectedCell ? { ...selectedCell, _drill: drillData, _drillLoading: drillLoading } : null}
        isOpen={inspectorOpen}
        onClose={handleCloseInspector}
      />
    </div>
  );
}

export default OmniviewV2ShadowPage;
