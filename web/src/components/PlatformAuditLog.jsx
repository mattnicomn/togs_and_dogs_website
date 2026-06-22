import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getPlatformAudit } from '../api/platform';
import './PlatformAdmin.css';

const PlatformAuditLog = () => {
  const [audits, setAudits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAuditLogs = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPlatformAudit();
      setAudits(data.audits || []);
    } catch (err) {
      console.error('Failed to load platform audit logs:', err);
      setError(err.message || 'Failed to fetch audit history.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditLogs();
  }, []);

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch (e) {
      return dateStr;
    }
  };

  // Mask sensitive actor email addresses to protect privacy (e.g. matt***@gmail.com)
  const formatActor = (actorStr) => {
    if (!actorStr) return 'Platform System';
    
    // Check if it looks like a Cognito UUID sub
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (uuidRegex.test(actorStr)) {
      return 'Platform Admin';
    }

    // Check if it's an email address
    if (actorStr.includes('@')) {
      const [local, domain] = actorStr.split('@');
      if (local.length <= 3) {
        return `${local.substring(0, 1)}***@${domain}`;
      }
      return `${local.substring(0, 3)}***@${domain}`;
    }

    return actorStr;
  };

  const formatActionName = (action) => {
    if (!action) return 'Unknown Action';
    return action.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  // Render the old/new values in a friendly diff format
  const renderChanges = (audit) => {
    const fields = audit.changed_fields || [];
    const oldVals = audit.old_values || {};
    const newVals = audit.new_values || {};

    if (fields.length === 0) {
      return <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>No fields changed</span>;
    }

    return (
      <div className="audit-changes-box">
        {fields.map((f, idx) => {
          const oldV = oldVals[f] === null || oldVals[f] === undefined ? 'None' : String(oldVals[f]);
          const newV = newVals[f] === null || newVals[f] === undefined ? 'Cleared' : String(newVals[f]);
          return (
            <div key={idx} style={{ marginBottom: idx < fields.length - 1 ? '6px' : 0 }}>
              <strong style={{ textTransform: 'uppercase', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{f.replace(/_/g, ' ')}</strong>:
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '2px', flexWrap: 'wrap' }}>
                <span style={{ color: 'var(--warning-color)', textDecoration: 'line-through' }}>{oldV}</span>
                <span>➔</span>
                <span style={{ color: 'var(--success-color)', fontWeight: 600 }}>{newV}</span>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="platform-admin-container">
      <Link to="/platform-admin" className="btn-back-platform">← Back to Dashboard</Link>

      <header className="platform-header-section" style={{ marginTop: '24px' }}>
        <div className="platform-title-group">
          <h1>Platform Audit Log</h1>
          <p>Global security and operational mutation events</p>
        </div>
        <div className="platform-nav-actions">
          <button onClick={fetchAuditLogs} className="button-secondary" disabled={loading}>
            🔄 Refresh Log
          </button>
        </div>
      </header>

      {error && (
        <div className="platform-card-section" style={{ borderLeft: '4px solid var(--warning-color)' }}>
          <h3 style={{ color: 'var(--warning-color)', border: 'none', padding: 0 }}>Log Retrieval Error</h3>
          <p>{error}</p>
          <button onClick={fetchAuditLogs} className="button-primary" style={{ marginTop: '16px' }}>🔄 Retry Fetching Logs</button>
        </div>
      )}

      {loading && !error && (
        <div className="platform-loading-container">
          <div className="platform-spinner"></div>
          <p>Fetching platform audit trails...</p>
        </div>
      )}

      {!loading && !error && (
        <>
          {audits.length === 0 ? (
            <div className="platform-empty-state">
              <span className="platform-empty-icon">📋</span>
              <h3>No Audit Entries Found</h3>
              <p>No operational changes have been logged in the system.</p>
            </div>
          ) : (
            <div className="audit-table-wrapper">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th>Timestamp (Local)</th>
                    <th>Action</th>
                    <th>Target Tenant</th>
                    <th>Changed Fields & Values</th>
                    <th>Actor</th>
                  </tr>
                </thead>
                <tbody>
                  {audits.map((audit, idx) => (
                    <tr key={audit.SK || idx}>
                      <td className="audit-timestamp">
                        {formatDate(audit.timestamp || audit.SK?.split('#')[1])}
                      </td>
                      <td style={{ fontWeight: 600 }}>
                        {formatActionName(audit.action)}
                      </td>
                      <td className="monospace" style={{ fontWeight: 600 }}>
                        {audit.target_company_id || '—'}
                      </td>
                      <td>
                        {renderChanges(audit)}
                      </td>
                      <td style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>
                        👤 {formatActor(audit.actor)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '20px', textAlign: 'center' }}>
            Showing the latest {audits.length} operational logs (retrieved from DynamoDB secure audit PK).
          </p>
        </>
      )}
    </div>
  );
};

export default PlatformAuditLog;
