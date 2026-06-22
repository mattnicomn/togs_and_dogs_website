import React, { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { getPlatformTenants } from '../api/platform';
import './PlatformAdmin.css';

const PlatformAdmin = () => {
  const [tenants, setTenants] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  
  const navigate = useNavigate();

  const fetchTenants = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPlatformTenants();
      setTenants(data.tenants || []);
    } catch (err) {
      console.error('Failed to load tenants:', err);
      setError(err.message || 'Failed to fetch platform tenants. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch (e) {
      return dateStr;
    }
  };

  const getTierClass = (tier) => {
    const t = String(tier || '').toLowerCase();
    if (t.includes('starter')) return 'tier-starter';
    if (t.includes('professional')) return 'tier-professional';
    if (t.includes('premium')) return 'tier-premium';
    if (t.includes('enterprise')) return 'tier-enterprise';
    return 'tier-starter';
  };

  const getStatusClass = (status) => {
    const s = String(status || '').toLowerCase();
    if (s === 'active') return 'status-active';
    if (s === 'trialing') return 'status-trialing';
    if (s === 'past_due') return 'status-past_due';
    if (s === 'canceled') return 'status-canceled';
    if (s === 'disabled') return 'status-disabled';
    if (s === 'paused') return 'status-paused';
    return 'status-paused';
  };

  const formatLabel = (str) => {
    if (!str) return '—';
    return str.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  // Filter tenants based on search query (by company ID or display name)
  const filteredTenants = tenants.filter(t => {
    const query = searchQuery.toLowerCase().trim();
    if (!query) return true;
    
    const companyId = (t.company_id || '').toLowerCase();
    const displayName = (t.display_name || '').toLowerCase();
    
    return companyId.includes(query) || displayName.includes(query);
  });

  return (
    <div className="platform-admin-container">
      <header className="platform-header-section">
        <div className="platform-title-group">
          <h1>Platform Admin Console</h1>
          <p>Global multi-tenant platform operational controls</p>
        </div>
        <div className="platform-nav-actions">
          <Link to="/platform-admin/audit" className="button-secondary">
            📋 View Platform Audit Log
          </Link>
          <Link to="/admin" className="button-secondary">
            🏢 Tenant Staff Dashboard
          </Link>
        </div>
      </header>

      {error && (
        <div className="platform-card-section" style={{ borderLeft: '4px solid var(--warning-color)' }}>
          <h3 style={{ color: 'var(--warning-color)', border: 'none', padding: 0, margin: '0 0 12px 0' }}>
            System Error
          </h3>
          <p style={{ margin: '0 0 20px 0', color: 'var(--text-secondary)' }}>{error}</p>
          <button onClick={fetchTenants} className="button-primary">
            🔄 Retry Fetching Data
          </button>
        </div>
      )}

      {loading && !error && (
        <div className="platform-loading-container">
          <div className="platform-spinner"></div>
          <p>Retrieving platform tenant registry...</p>
        </div>
      )}

      {!loading && !error && (
        <>
          <div className="platform-list-controls">
            <h3 style={{ margin: 0, fontFamily: 'var(--serif)' }}>
              Registered Businesses ({filteredTenants.length})
            </h3>
            <div className="search-input-wrapper">
              <span className="search-icon-placeholder">🔍</span>
              <input
                type="text"
                placeholder="Search by company ID or name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search tenants"
              />
            </div>
          </div>

          {filteredTenants.length === 0 ? (
            <div className="platform-empty-state">
              <span className="platform-empty-icon">🏢</span>
              <h3>No Tenants Found</h3>
              <p>No active records matched your search query. Try clearing filters.</p>
            </div>
          ) : (
            <div className="tenant-grid">
              {filteredTenants.map((tenant) => (
                <div
                  key={tenant.company_id}
                  className="tenant-card"
                  onClick={() => navigate(`/platform-admin/tenants/${tenant.company_id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      navigate(`/platform-admin/tenants/${tenant.company_id}`);
                    }
                  }}
                >
                  <div className="tenant-card-header">
                    <div>
                      <div className="tenant-name">{tenant.display_name || 'Unnamed Tenant'}</div>
                      <div className="tenant-id">{tenant.company_id}</div>
                    </div>
                  </div>
                  
                  <div className="tenant-card-badges">
                    <span className={`platform-badge ${getTierClass(tenant.subscription_tier)}`}>
                      👑 {formatLabel(tenant.subscription_tier)}
                    </span>
                    <span className={`platform-badge ${getStatusClass(tenant.subscription_status)}`}>
                      {formatLabel(tenant.subscription_status)}
                    </span>
                  </div>

                  <div className="tenant-card-footer">
                    <span>Registered: {formatDate(tenant.created_at)}</span>
                    <span style={{ color: 'var(--primary)', fontWeight: 600 }}>Manage →</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default PlatformAdmin;
