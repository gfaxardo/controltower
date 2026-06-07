import { useState, useMemo } from 'react';
import MatrixShell from './components/matrix/MatrixShell';
import CellInspector from './components/matrix/CellInspector';
import SourceBadge from './components/base/SourceBadge';
import CoverageBadge from './components/base/CoverageBadge';
import StatusBadge from './components/base/StatusBadge';
import {
  mockCTDay,
  mockCTWeek,
  mockCTMonth,
  mockYangoDay,
  mockWarnings,
  mockCompareMode,
} from './mocks/mockMatrixResponse';
import './design/MatrixVisualSystem.css';

const SCENARIOS = {
  ct_day: { label: 'CT Day', fn: mockCTDay, source: 'CT_TRIPS_2026', grain: 'day' },
  ct_week: { label: 'CT Week', fn: mockCTWeek, source: 'CT_TRIPS_2026', grain: 'week' },
  ct_month: { label: 'CT Month', fn: mockCTMonth, source: 'CT_TRIPS_2026', grain: 'month' },
  yango_day: { label: 'Yango Day', fn: mockYangoDay, source: 'YANGO_API_RAW', grain: 'day' },
  warnings: { label: 'Warnings', fn: mockWarnings, source: 'CT_TRIPS_2026', grain: 'day' },
  compare: { label: 'Compare Mode', fn: mockCompareMode, source: 'CT_TRIPS_2026', grain: 'day' },
};

const METRICS = ['orders', 'revenue', 'active_drivers', 'tpd'];

function OmniviewV2MatrixSandbox() {
  const [scenario, setScenario] = useState('ct_day');
  const [selectedCell, setSelectedCell] = useState(null);
  const [inspectorOpen, setInspectorOpen] = useState(false);

  const scenarioDef = SCENARIOS[scenario];
  const matrixData = useMemo(() => scenarioDef.fn(), [scenario]);

  const handleCellClick = (cell) => {
    setSelectedCell(cell);
    setInspectorOpen(true);
  };

  const handleCloseInspector = () => {
    setInspectorOpen(false);
    setSelectedCell(null);
  };

  const metadata = matrixData.metadata || {};
  const canonicalReady = matrixData.canonical_ready;

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', fontFamily: 'var(--ov2-font-family)', background: '#f9fafb' }}>
      {/* Command Header */}
      <div className="ov2-command-header">
        <span style={{ fontWeight: 700, fontSize: 14, marginRight: 16 }}>OV2 Matrix Sandbox</span>

        <select
          value={scenario}
          onChange={(e) => { setScenario(e.target.value); handleCloseInspector(); }}
          style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid var(--ov2-border-color)', fontSize: 13 }}
        >
          {Object.entries(SCENARIOS).map(([key, def]) => (
            <option key={key} value={key}>{def.label}</option>
          ))}
        </select>

        <span style={{ color: 'var(--ov2-border-color)', margin: '0 4px' }}>|</span>

        <SourceBadge canonicalReady={canonicalReady} />
        <CoverageBadge pct={metadata.coverage_pct} />

        {scenarioDef.source === 'YANGO_API_RAW' && (
          <StatusBadge status="shadow" label="NOT CANONICAL" />
        )}

        <span style={{ marginLeft: 'auto', fontSize: 12, color: 'var(--ov2-text-secondary)' }}>
          {scenarioDef.source} · {scenarioDef.grain} · {metadata.row_count} rows × {metadata.column_count} cols
        </span>
      </div>

      {/* Matrix Zone */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <MatrixShell
          matrixData={matrixData}
          selectedCell={selectedCell ? { rowId: selectedCell.row_id, columnId: selectedCell.column_id } : null}
          onCellClick={handleCellClick}
        />
      </div>

      {/* Inspector */}
      <CellInspector
        cell={selectedCell}
        isOpen={inspectorOpen}
        onClose={handleCloseInspector}
      />
    </div>
  );
}

export default OmniviewV2MatrixSandbox;
