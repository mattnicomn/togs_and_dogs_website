import React from 'react';

const StaffProfileCard = ({
  staff: s,
  isSelected,
  openStaffDetail,
  isProtectedProfile,
  isSelf,
  getAccessStatus
}) => {
  return (
    <div
      className={`staff-profile-card ${isSelected ? 'selected' : ''}`}
      style={{
        border: isSelected ? '2px solid var(--accent-color)' : s.is_virtual ? '1px dashed var(--accent-orange)' : '1px solid var(--border-color)',
        borderRadius: '12px',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: isSelected ? 'var(--bg-muted)' : 'var(--card-bg)',
        boxSizing: 'border-box'
      }}
    >
      {isSelected && <div className="selected-indicator">Selected</div>}

      <button
        type="button"
        className="card-summary-button-link"
        onClick={(e) => openStaffDetail(s, e.currentTarget)}
        aria-label={`Staff profile for ${s.display_name}. Click or press Enter or Space to view details.`}
        aria-pressed={isSelected}
        style={{
          padding: '16px 16px 8px 16px',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px',
          width: '100%',
          boxSizing: 'border-box'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', width: '100%', color: 'inherit' }}>
          <span className="dot" style={{ backgroundColor: s.assignment_color || 'var(--staff-unassigned)', width: '16px', height: '16px', borderRadius: '50%', flexShrink: 0 }}></span>
          <strong style={{ fontSize: '18px', display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '4px' }}>
            {s.display_name}
            {s.is_virtual && <span style={{ color: 'var(--accent-orange)', fontSize: '12px', backgroundColor: 'rgba(255, 152, 0, 0.15)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--accent-orange)' }}>Login Only</span>}
            {s.is_orphaned_identity && <span style={{ color: 'var(--danger, #f44336)', fontSize: '12px' }} title="Login references a deleted user">⚠️ Orphaned</span>}
          </strong>
          {isProtectedProfile(s) && <span style={{ color: 'var(--accent-teal)', fontSize: '11px', backgroundColor: 'rgba(0, 188, 212, 0.1)', padding: '2px 8px', borderRadius: '12px', border: '1px solid var(--accent-teal)' }}>Protected Platform Admin</span>}
          {isSelf(s) && <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>(You)</span>}
        </div>
        <div style={{ fontSize: '14px', color: 'var(--text-secondary)', textAlign: 'left', width: '100%' }}>
          <p style={{ margin: '2px 0' }}><strong>Access Level:</strong> {s.role}</p>

          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', margin: '6px 0' }}>
            <strong>Access:</strong>
            {(() => {
              const status = getAccessStatus(s);
              return <span className={`access-badge ${status.class}`}>{status.label}</span>
            })()}
          </div>
        </div>
      </button>

      <div
        style={{
          padding: '8px 16px 16px 16px',
          borderTop: '1px solid var(--border-color, #333)',
          marginTop: 'auto'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          className="button-secondary"
          style={{ width: '100%', padding: '8px 12px' }}
          onClick={(e) => openStaffDetail(s, e.currentTarget)}
        >
          View Details
        </button>
      </div>
    </div>
  );
};

export default StaffProfileCard;
