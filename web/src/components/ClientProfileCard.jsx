import React from 'react';
import { accountStatusLabel, accountStatusClass, profileStatusLabel, profileStatusClass } from '../utils/clientManagement';

const ClientProfileCard = ({
  client: c,
  isSelected,
  openClientDetail,
  isProtectedProfile
}) => {
  return (
    <div
      className={`client-profile-card ${isSelected ? 'selected' : ''}`}
      style={{
        position: 'relative',
        display: 'flex',
        flexDirection: 'column',
        border: isSelected ? '2px solid var(--accent-color)' : c.is_virtual ? '1px dashed var(--accent-orange)' : '1px solid var(--border)',
        opacity: c.is_active === false ? 0.6 : 1,
        backgroundColor: isSelected ? 'var(--bg-muted)' : 'var(--card-bg)',
        borderRadius: '12px',
        boxSizing: 'border-box'
      }}
    >
      {isSelected && <div className="selected-indicator">Selected</div>}

      <button
        type="button"
        className="card-summary-button-link"
        onClick={(e) => openClientDetail(c, e.currentTarget)}
        aria-label={`Client profile for ${c.display_name}. Click or press Enter or Space to view details.`}
        aria-pressed={isSelected}
        style={{
          padding: '20px 20px 10px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '12px',
          width: '100%',
          boxSizing: 'border-box'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', width: '100%' }}>
          <div>
            <h4 style={{ margin: 0, display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '4px', color: 'inherit' }}>
              {c.display_name}
              {isProtectedProfile(c) && (
                <span style={{ color: 'var(--accent-teal)', fontSize: '11px', backgroundColor: 'rgba(0, 188, 212, 0.1)', padding: '2px 8px', borderRadius: '12px', border: '1px solid var(--accent-teal)' }}>
                  Protected Platform Admin
                </span>
              )}
              {c.auto_created && (
                <span style={{ fontSize: '10px', backgroundColor: 'rgba(76, 175, 80, 0.1)', color: 'var(--success, #4caf50)', padding: '2px 8px', borderRadius: '12px', border: '1px solid rgba(76, 175, 80, 0.3)' }}>
                  Auto-created
                </span>
              )}
              {c.request_count > 0 && (
                <span style={{ fontSize: '10px', backgroundColor: 'var(--bg-muted)', padding: '2px 8px', borderRadius: '12px' }}>
                  {c.request_count} request{c.request_count > 1 ? 's' : ''}
                </span>
              )}
            </h4>
            <p style={{ margin: '4px 0', fontSize: '13px', color: 'var(--text-muted)' }}>
              {c.email || <span style={{ fontStyle: 'italic', opacity: 0.6 }}>No email on file</span>}
            </p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-end', flexShrink: 0 }}>
            <span className={`access-badge ${profileStatusClass(c)}`} style={{ fontSize: '10px' }}>{profileStatusLabel(c)}</span>
            <span className={`access-badge ${accountStatusClass(c)}`} style={{ fontSize: '10px' }}>{accountStatusLabel(c)}</span>
          </div>
        </div>

        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', textAlign: 'left', width: '100%' }}>
          {c.pet_names_summary && (
            <p style={{ margin: '4px 0', fontSize: '12px' }}>
              🐾 {c.pet_names_summary}
              {c.pet_breeds_summary && (
                <span style={{ color: 'var(--text-muted)', marginLeft: '4px' }}>({c.pet_breeds_summary})</span>
              )}
            </p>
          )}
          {!c.pet_names_summary && !c.intake_request_ids && (
            <p style={{ margin: '4px 0', fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>No pets linked</p>
          )}
        </div>
      </button>

      <div
        className="btn-group"
        style={{
          display: 'flex',
          gap: '8px',
          flexWrap: 'wrap',
          marginTop: 'auto',
          padding: '10px 20px 20px 20px',
          borderTop: '1px solid var(--border)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <button
          type="button"
          className="btn-small"
          onClick={(e) => openClientDetail(c, e.currentTarget)}
        >
          View Details
        </button>
      </div>
    </div>
  );
};

export default ClientProfileCard;
