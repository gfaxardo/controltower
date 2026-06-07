function MatrixEmptyState({ message = 'No data available for the selected period.' }) {
  return (
    <div className="ov2-empty">
      <div style={{ fontSize: 40, marginBottom: 8, opacity: 0.3 }}>⊡</div>
      <div>{message}</div>
      <div style={{ fontSize: 12, color: 'var(--ov2-text-muted)' }}>
        Try adjusting the period or grain selector.
      </div>
    </div>
  );
}

export default MatrixEmptyState;
