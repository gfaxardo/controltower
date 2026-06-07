import StatusBadge from '../base/StatusBadge';
import SourceBadge from '../base/SourceBadge';

function OmniviewV2SectionShell({ sections = [], onSectionClick }) {
  if (!sections || sections.length === 0) return null;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 'var(--ov2-section-gap)', padding: '0 16px 12px' }}>
      {sections.map((section) => {
        const statusCode = section.status?.code || section.status || 'OK';
        return (
          <div key={section.section_id} className={`ov2-section-card ov2-section-card--${statusCode.toLowerCase()}`} onClick={() => onSectionClick?.(section)} style={{ cursor: 'pointer' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontWeight: 600, fontSize: 13 }}>{section.title || section.section_id}</span>
              <div style={{ display: 'flex', gap: 4 }}>
                <SourceBadge canonicalReady={section.canonical_ready} />
                <StatusBadge status={statusCode.toLowerCase()} label={statusCode} />
              </div>
            </div>
            <div style={{ fontSize: 12, color: 'var(--ov2-text-secondary)', marginBottom: 4 }}>
              {section.summary || section.description || ''}
            </div>
            {section.allowed_actions && section.allowed_actions.length > 0 && (
              <div style={{ display: 'flex', gap: 4, marginTop: 8 }}>
                {section.allowed_actions.map((action, i) => (
                  <span key={i} className="ov2-badge ov2-badge--shadow" style={{ fontSize: 9 }}>
                    {action.label || action.action_id}
                  </span>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default OmniviewV2SectionShell;
