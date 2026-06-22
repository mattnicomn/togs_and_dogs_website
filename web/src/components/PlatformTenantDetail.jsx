import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getPlatformTenant, updatePlatformTenant } from '../api/platform';
import './PlatformAdmin.css';

// Entitlement limits constant dictionary for frontend reference/fallback
const TIER_LIMITS = {
  starter: {
    max_active_clients: 20,
    max_staff: 1,
    max_monthly_notifications: 100,
    max_monthly_bookings: 50,
    google_calendar_enabled: false,
    export_enabled: false,
    custom_branding_enabled: false,
    video_evidence_enabled: false,
  },
  professional: {
    max_active_clients: 100,
    max_staff: 5,
    max_monthly_notifications: 500,
    max_monthly_bookings: 250,
    google_calendar_enabled: true,
    export_enabled: true,
    custom_branding_enabled: false,
    video_evidence_enabled: false,
  },
  premium: {
    max_active_clients: 500,
    max_staff: 15,
    max_monthly_notifications: 2000,
    max_monthly_bookings: 1000,
    google_calendar_enabled: true,
    export_enabled: true,
    custom_branding_enabled: true,
    video_evidence_enabled: true,
  },
  enterprise: {
    max_active_clients: 999999,
    max_staff: 999999,
    max_monthly_notifications: 999999,
    max_monthly_bookings: 999999,
    google_calendar_enabled: true,
    export_enabled: true,
    custom_branding_enabled: true,
    video_evidence_enabled: true,
  },
};

const tierPriority = { starter: 1, professional: 2, premium: 3, enterprise: 4 };

const PlatformTenantDetail = () => {
  const { companyId } = useParams();
  const navigate = useNavigate();

  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Edit Modal State
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [modalStep, setModalStep] = useState('edit'); // 'edit' or 'review'
  const [formFields, setFormFields] = useState({
    display_name: '',
    subscription_tier: 'starter',
    subscription_status: 'active',
    admin_override_until: '',
    notes: '',
  });

  const [saving, setSaving] = useState(false);
  const [modalError, setModalError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  const fetchTenantDetail = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await getPlatformTenant(companyId);
      setTenant(data);
      
      // Initialize form fields
      setFormFields({
        display_name: data.profile?.display_name || '',
        subscription_tier: data.subscription?.tier || 'starter',
        subscription_status: data.subscription?.status || 'active',
        admin_override_until: data.profile?.admin_override_until ? data.profile.admin_override_until.substring(0, 16) : '',
        notes: data.profile?.notes || '',
      });
    } catch (err) {
      console.error('Failed to load tenant details:', err);
      setError(err.message || 'Failed to fetch tenant metadata.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTenantDetail();
  }, [companyId]);

  if (loading) {
    return (
      <div className="platform-admin-container">
        <div className="platform-loading-container">
          <div className="platform-spinner"></div>
          <p>Retrieving tenant metadata and usage records...</p>
        </div>
      </div>
    );
  }

  if (error || !tenant) {
    return (
      <div className="platform-admin-container">
        <Link to="/platform-admin" className="btn-back-platform">← Back to Tenants</Link>
        <div className="platform-card-section" style={{ marginTop: '24px', borderLeft: '4px solid var(--warning-color)' }}>
          <h3 style={{ color: 'var(--warning-color)', border: 'none', padding: 0 }}>Load Failure</h3>
          <p>{error || 'Tenant metadata could not be fetched.'}</p>
          <button onClick={fetchTenantDetail} className="button-primary">🔄 Retry Fetching Details</button>
        </div>
      </div>
    );
  }

  // Format Helpers
  const formatLabel = (str) => {
    if (!str) return '—';
    return str.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '—';
    try {
      return new Date(dateStr).toLocaleString(undefined, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return dateStr;
    }
  };

  // Derive entitlements (prioritize backend limits, fallback to standard tier limits dictionary)
  const activeTier = tenant.subscription?.tier || 'starter';
  const limits = tenant.entitlement_summary?.limits || TIER_LIMITS[activeTier] || TIER_LIMITS.starter;

  // Determine if override is active
  const isOverrideActive = () => {
    const override = tenant.profile?.admin_override_until;
    if (!override) return false;
    try {
      return new Date() < new Date(override);
    } catch (e) {
      return false;
    }
  };

  // Prepare changes list for confirmation modal
  const getChanges = () => {
    const changes = [];
    const origProfile = tenant.profile || {};
    const origSub = tenant.subscription || {};

    if (formFields.display_name.trim() !== (origProfile.display_name || '').trim()) {
      changes.push({
        field: 'Display Name',
        oldVal: origProfile.display_name || '—',
        newVal: formFields.display_name,
      });
    }

    if (formFields.subscription_tier !== (origSub.tier || 'starter')) {
      changes.push({
        field: 'Subscription Tier',
        oldVal: origSub.tier || 'starter',
        newVal: formFields.subscription_tier,
      });
    }

    if (formFields.subscription_status !== (origSub.status || 'active')) {
      changes.push({
        field: 'Subscription Status',
        oldVal: origSub.status || 'active',
        newVal: formFields.subscription_status,
      });
    }

    const origOverride = origProfile.admin_override_until ? origProfile.admin_override_until.substring(0, 16) : '';
    if (formFields.admin_override_until !== origOverride) {
      changes.push({
        field: 'Admin Override Until',
        oldVal: origProfile.admin_override_until ? formatDate(origProfile.admin_override_until) : 'None',
        newVal: formFields.admin_override_until ? formatDate(formFields.admin_override_until + ':00Z') : 'Cleared',
      });
    }

    if (formFields.notes.trim() !== (origProfile.notes || '').trim()) {
      changes.push({
        field: 'Platform Notes',
        oldVal: origProfile.notes || '—',
        newVal: formFields.notes || 'Cleared',
      });
    }

    return changes;
  };

  const changesList = getChanges();
  const isTierDowngrade = () => {
    const oldTier = tenant.subscription?.tier || 'starter';
    const newTier = formFields.subscription_tier;
    return tierPriority[newTier] < tierPriority[oldTier];
  };

  const isSuspension = ['canceled', 'disabled'].includes(formFields.subscription_status) && 
                       !['canceled', 'disabled'].includes(tenant.subscription?.status || 'active');

  const isPastDue = formFields.subscription_status === 'past_due' && 
                    tenant.subscription?.status !== 'past_due';

  const handleOpenEdit = () => {
    setIsEditOpen(true);
    setModalStep('edit');
    setModalError(null);
  };

  const handleCloseEdit = () => {
    setIsEditOpen(false);
    setModalStep('edit');
    setModalError(null);
  };

  const handleSaveAttempt = (e) => {
    e.preventDefault();
    if (!formFields.display_name.trim()) {
      alert('Display Name is required.');
      return;
    }
    const currentChanges = getChanges();
    if (currentChanges.length === 0) {
      return;
    }
    setModalError(null);
    setModalStep('review');
  };

  const handleConfirmSave = async () => {
    try {
      setSaving(true);
      setModalError(null);

      // Construct PATCH payload matching backend expected format
      const payload = {
        display_name: formFields.display_name.trim(),
        subscription_tier: formFields.subscription_tier,
        subscription_status: formFields.subscription_status,
        admin_override_until: formFields.admin_override_until ? `${formFields.admin_override_until}:00Z` : null,
        notes: formFields.notes.trim() || null,
      };

      // Perform update API helper call
      await updatePlatformTenant(companyId, payload);
      
      // Close modal and refresh details
      setIsEditOpen(false);
      await fetchTenantDetail();

      setSuccessMessage('Subscription plan updated successfully.');
      setTimeout(() => setSuccessMessage(null), 5000);
    } catch (err) {
      console.error('Failed to update tenant:', err);
      setModalError(err.message || 'Failed to update subscription metadata.');
    } finally {
      setSaving(false);
    }
  };

  // Helper for computing progress bar colors
  const getUsageBarColor = (used, max) => {
    if (!max || max >= 9999) return '';
    const ratio = used / max;
    if (ratio >= 0.9) return 'danger';
    if (ratio >= 0.75) return 'warning';
    return '';
  };

  const getTierBadgeClass = (tier) => {
    const t = String(tier || '').toLowerCase();
    if (t.includes('starter')) return 'tier-starter';
    if (t.includes('professional')) return 'tier-professional';
    if (t.includes('premium')) return 'tier-premium';
    if (t.includes('enterprise')) return 'tier-enterprise';
    return 'tier-starter';
  };

  const getStatusBadgeClass = (status) => {
    const s = String(status || '').toLowerCase();
    if (s === 'active') return 'status-active';
    if (s === 'trialing') return 'status-trialing';
    if (s === 'past_due') return 'status-past_due';
    if (s === 'canceled') return 'status-canceled';
    if (s === 'disabled') return 'status-disabled';
    if (s === 'paused') return 'status-paused';
    return 'status-paused';
  };

  return (
    <div className="platform-admin-container">
      <Link to="/platform-admin" className="btn-back-platform">← Back to Tenant Registry</Link>

      {successMessage && (
        <div className="platform-card-section" style={{ borderLeft: '4px solid var(--success-color)', padding: '16px 24px', margin: '24px 0 0 0', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '1.2rem' }}>✅</span>
          <p style={{ margin: 0, color: 'var(--success-color)', fontWeight: 600 }}>
            {successMessage}
          </p>
        </div>
      )}

      <header className="platform-header-section" style={{ marginTop: '24px' }}>
        <div className="platform-title-group">
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap' }}>
            <h1>{tenant.profile?.display_name || 'Unnamed Tenant'}</h1>
            <span className={`platform-badge ${getTierBadgeClass(tenant.subscription?.tier)}`} style={{ fontSize: '0.85rem', padding: '6px 14px' }}>
              👑 {formatLabel(tenant.subscription?.tier)}
            </span>
            <span className={`platform-badge ${getStatusBadgeClass(tenant.subscription?.status)}`} style={{ fontSize: '0.85rem', padding: '6px 14px' }}>
              {formatLabel(tenant.subscription?.status)}
            </span>
          </div>
          <p style={{ marginTop: '6px' }}>Company ID: <strong className="monospace" style={{ background: 'var(--card-bg-muted)', padding: '2px 6px', borderRadius: '4px' }}>{tenant.company_id}</strong></p>
        </div>
        <div className="platform-nav-actions">
          <button onClick={handleOpenEdit} className="button-primary">
            ⚙️ Edit Subscription
          </button>
        </div>
      </header>

      <div className="tenant-detail-grid">
        <div className="detail-main-column">
          {/* Metadata Section */}
          <section className="platform-card-section">
            <h3>Metadata & Subscription Profile</h3>
            <div className="platform-metadata-list">
              <div className="metadata-item">
                <span className="metadata-label">Registered Display Name</span>
                <span className="metadata-value">{tenant.profile?.display_name || '—'}</span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">Cognito User Pool ID Reference</span>
                <span className="metadata-value monospace">us-east-1_counlsXGU</span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">Admin Override Expiration</span>
                <span className="metadata-value" style={{ color: isOverrideActive() ? 'var(--success-color)' : 'inherit' }}>
                  {tenant.profile?.admin_override_until ? formatDate(tenant.profile.admin_override_until) : 'No active override'}
                  {isOverrideActive() && ' (Active)'}
                </span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">Account Created At</span>
                <span className="metadata-value">{formatDate(tenant.profile?.created_at)}</span>
              </div>
              <div className="metadata-item">
                <span className="metadata-label">Metadata Last Updated At</span>
                <span className="metadata-value">{formatDate(tenant.profile?.updated_at)}</span>
              </div>
            </div>
          </section>

          {/* Entitlement Summary */}
          <section className="platform-card-section">
            <h3>Tier Entitlements ({formatLabel(activeTier)})</h3>
            <div className="entitlements-grid">
              <div className="entitlement-item">
                <span className="entitlement-name">Max Active Staff Users</span>
                <span className="entitlement-val">{limits.max_staff >= 9999 ? 'Unlimited' : limits.max_staff}</span>
              </div>
              <div className="entitlement-item">
                <span className="entitlement-name">Max Active Clients</span>
                <span className="entitlement-val">{limits.max_active_clients >= 9999 ? 'Unlimited' : limits.max_active_clients}</span>
              </div>
              <div className="entitlement-item">
                <span className="entitlement-name">Max Monthly Care Bookings</span>
                <span className="entitlement-val">{limits.max_monthly_bookings >= 9999 ? 'Unlimited' : limits.max_monthly_bookings}</span>
              </div>
              <div className="entitlement-item">
                <span className="entitlement-name">Max Monthly Push Notifications</span>
                <span className="entitlement-val">{limits.max_monthly_notifications >= 9999 ? 'Unlimited' : limits.max_monthly_notifications}</span>
              </div>
              <div className="entitlement-item">
                <span className="entitlement-name">Google Calendar Integration</span>
                <span className="entitlement-flag">{limits.google_calendar_enabled ? '✅' : '❌'}</span>
              </div>
              <div className="entitlement-item">
                <span className="entitlement-name">Excel Export Utility</span>
                <span className="entitlement-flag">{limits.export_enabled ? '✅' : '❌'}</span>
              </div>
              <div className="entitlement-item">
                <span className="entitlement-name">Custom App Branding</span>
                <span className="entitlement-flag">{limits.custom_branding_enabled ? '✅' : '❌'}</span>
              </div>
              <div className="entitlement-item">
                <span className="entitlement-name">Video Evidence Logs</span>
                <span className="entitlement-flag">{limits.video_evidence_enabled ? '✅' : '❌'}</span>
              </div>
            </div>
          </section>
        </div>

        <div className="detail-sidebar-column">
          {/* Usage Counts */}
          <section className="platform-card-section">
            <h3>Current Usage</h3>
            <div className="usage-summary-list">
              <div className="usage-item-bar">
                <div className="usage-item-info">
                  <span>Staff Users</span>
                  <span>{tenant.usage_counts?.active_staff || 0} / {limits.max_staff >= 9999 ? '∞' : limits.max_staff}</span>
                </div>
                <div className="usage-progress-bg">
                  <div 
                    className={`usage-progress-bar ${getUsageBarColor(tenant.usage_counts?.active_staff || 0, limits.max_staff)}`} 
                    style={{ width: `${limits.max_staff >= 9999 ? 0 : Math.min(100, ((tenant.usage_counts?.active_staff || 0) / limits.max_staff) * 100)}%` }}
                  ></div>
                </div>
              </div>

              <div className="usage-item-bar">
                <div className="usage-item-info">
                  <span>Active Clients</span>
                  <span>{tenant.usage_counts?.active_clients || 0} / {limits.max_active_clients >= 9999 ? '∞' : limits.max_active_clients}</span>
                </div>
                <div className="usage-progress-bg">
                  <div 
                    className={`usage-progress-bar ${getUsageBarColor(tenant.usage_counts?.active_clients || 0, limits.max_active_clients)}`} 
                    style={{ width: `${limits.max_active_clients >= 9999 ? 0 : Math.min(100, ((tenant.usage_counts?.active_clients || 0) / limits.max_active_clients) * 100)}%` }}
                  ></div>
                </div>
              </div>

              <div className="usage-item-bar">
                <div className="usage-item-info">
                  <span>Monthly Care Bookings</span>
                  <span>{tenant.usage_counts?.monthly_bookings || 0} / {limits.max_monthly_bookings >= 9999 ? '∞' : limits.max_monthly_bookings}</span>
                </div>
                <div className="usage-progress-bg">
                  <div 
                    className={`usage-progress-bar ${getUsageBarColor(tenant.usage_counts?.monthly_bookings || 0, limits.max_monthly_bookings)}`} 
                    style={{ width: `${limits.max_monthly_bookings >= 9999 ? 0 : Math.min(100, ((tenant.usage_counts?.monthly_bookings || 0) / limits.max_monthly_bookings) * 100)}%` }}
                  ></div>
                </div>
              </div>
            </div>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '24px', margin: '24px 0 0 0', fontStyle: 'italic', textAlign: 'center' }}>
              ℹ️ Usage counts are approximate and updated periodically.
            </p>
          </section>

          {/* Internal Notes */}
          <section className="platform-card-section">
            <h3>Internal Notes</h3>
            {tenant.profile?.notes ? (
              <div className="platform-notes-display">{tenant.profile.notes}</div>
            ) : (
              <div className="platform-notes-display empty">No platform administrator notes written yet. Notes are only visible inside this Platform Admin Console.</div>
            )}
          </section>
        </div>
      </div>

      {/* EDIT & CONFIRMATION MODAL */}
      {isEditOpen && (
        <div className="platform-modal-overlay">
          <div className="platform-modal-card" style={modalStep === 'review' ? { maxWidth: '480px' } : {}}>
            <header className="platform-modal-header">
              <h2>{modalStep === 'edit' ? 'Edit Subscription Plan' : 'Confirm Tenant Updates'}</h2>
              <button onClick={handleCloseEdit} className="btn-close-modal" aria-label="Close edit modal">×</button>
            </header>
            
            {modalStep === 'edit' ? (
              <form onSubmit={handleSaveAttempt}>
                <div className="platform-modal-body">
                  {modalError && (
                    <div className="platform-alert-banner danger" style={{ marginBottom: '20px' }}>
                      <span>⚠️</span>
                      <div>
                        <strong>Error Saving Changes</strong>
                        <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem' }}>{modalError}</p>
                      </div>
                    </div>
                  )}

                  <div className="edit-form-grid">
                    <div className="field">
                      <label htmlFor="display_name">Business Display Name</label>
                      <input
                        id="display_name"
                        type="text"
                        maxLength={100}
                        value={formFields.display_name}
                        onChange={(e) => setFormFields({ ...formFields, display_name: e.target.value })}
                        required
                      />
                    </div>

                    <div className="field">
                      <label htmlFor="subscription_tier">Subscription Tier</label>
                      <select
                        id="subscription_tier"
                        value={formFields.subscription_tier}
                        onChange={(e) => setFormFields({ ...formFields, subscription_tier: e.target.value })}
                      >
                        <option value="starter">Starter</option>
                        <option value="professional">Professional</option>
                        <option value="premium">Premium</option>
                        <option value="enterprise">Enterprise</option>
                      </select>
                    </div>

                    <div className="field">
                      <label htmlFor="subscription_status">Subscription Status</label>
                      <select
                        id="subscription_status"
                        value={formFields.subscription_status}
                        onChange={(e) => setFormFields({ ...formFields, subscription_status: e.target.value })}
                      >
                        <option value="active">Active</option>
                        <option value="trialing">Trialing</option>
                        <option value="past_due">Past Due</option>
                        <option value="paused">Paused</option>
                        <option value="canceled">Canceled</option>
                        <option value="disabled">Disabled</option>
                      </select>
                    </div>

                    <div className="field">
                      <label htmlFor="admin_override_until">Admin Override Expiration (UTC)</label>
                      <input
                        id="admin_override_until"
                        type="datetime-local"
                        value={formFields.admin_override_until}
                        onChange={(e) => setFormFields({ ...formFields, admin_override_until: e.target.value })}
                      />
                      <small style={{ color: 'var(--text-muted)' }}>
                        Set a future timestamp to override and keep the tenant active regardless of billing status. Clear to let standard billing rule.
                      </small>
                    </div>

                    <div className="field">
                      <label htmlFor="notes">Internal Platform Notes</label>
                      <textarea
                        id="notes"
                        maxLength={1000}
                        rows={4}
                        value={formFields.notes}
                        onChange={(e) => setFormFields({ ...formFields, notes: e.target.value })}
                        placeholder="Enter administrator notes (audits, override explanations, custom arrangements)..."
                      />
                    </div>
                  </div>
                </div>

                <div className="platform-modal-footer">
                  <div style={{ display: 'flex', alignItems: 'center', width: '100%', justifyContent: 'flex-end' }}>
                    {changesList.length === 0 && (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginRight: '16px', fontStyle: 'italic' }}>
                        No changes to review
                      </span>
                    )}
                    <button type="button" onClick={handleCloseEdit} className="button-secondary" style={{ padding: '10px 24px', marginRight: '12px' }}>
                      Cancel
                    </button>
                    <button type="submit" className="button-primary" style={{ padding: '10px 24px' }} disabled={changesList.length === 0}>
                      Next: Review Changes
                    </button>
                  </div>
                </div>
              </form>
            ) : (
              <div>
                <div className="platform-modal-body">
                  {modalError && (
                    <div className="platform-alert-banner danger" style={{ marginBottom: '20px' }}>
                      <span>⚠️</span>
                      <div>
                        <strong>Error Saving Changes</strong>
                        <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem' }}>{modalError}</p>
                      </div>
                    </div>
                  )}

                  <p style={{ margin: '0 0 16px 0', fontSize: '0.95rem' }}>
                    You are updating tenant metadata for <strong className="monospace">{companyId}</strong>. Please review the pending changes:
                  </p>

                  <ul className="changes-diff-list">
                    {changesList.map((ch, idx) => {
                      const isRisky = ['Subscription Tier', 'Subscription Status', 'Admin Override Until'].includes(ch.field);
                      return (
                        <li 
                          key={idx}
                          style={{
                            borderLeft: isRisky ? '4px solid var(--warning-color)' : '4px solid var(--border-color)',
                            backgroundColor: isRisky ? 'rgba(214, 73, 51, 0.03)' : 'var(--card-bg-muted)'
                          }}
                        >
                          <span className="diff-field-name">
                            {isRisky ? '⚠️ ' : ''}{ch.field}
                          </span>
                          <div className="diff-change-vals">
                            <span className="diff-old-val">{ch.oldVal}</span>
                            <span>➔</span>
                            <span className="diff-new-val">{ch.newVal}</span>
                          </div>
                        </li>
                      );
                    })}
                  </ul>

                  {/* Alert Banners for Risky Changes */}
                  {isTierDowngrade() && (
                    <div className="platform-alert-banner warning">
                      <span>⚠️</span>
                      <div>
                        <strong>Downgrade Warning</strong>
                        <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem' }}>
                          Downgrading subscription tier restricts entitlement limits immediately. This may cause the tenant to exceed limits (e.g. staff users: {tenant.usage_counts?.active_staff || 0} vs new limit: {TIER_LIMITS[formFields.subscription_tier]?.max_staff || 0}).
                        </p>
                      </div>
                    </div>
                  )}

                  {isSuspension && (
                    <div className="platform-alert-banner danger">
                      <span>⚠️</span>
                      <div>
                        <strong>Access Suspension Alert</strong>
                        <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem' }}>
                          Setting subscription status to Canceled or Disabled blocks all tenant users (including owners, sitters, and clients) from logging in or using the application.
                        </p>
                      </div>
                    </div>
                  )}

                  {isPastDue && (
                    <div className="platform-alert-banner warning">
                      <span>⚠️</span>
                      <div>
                        <strong>Past Due State</strong>
                        <p style={{ margin: '4px 0 0 0', fontSize: '0.85rem' }}>
                          Marking status as Past Due triggers a 7-day grace period. Users will experience degraded/blocked access after the grace period expires.
                        </p>
                      </div>
                    </div>
                  )}
                </div>

                <div className="platform-modal-footer">
                  <button 
                    type="button" 
                    onClick={() => { setModalStep('edit'); setModalError(null); }} 
                    className="button-secondary" 
                    style={{ padding: '10px 24px', marginRight: '12px' }}
                    disabled={saving}
                  >
                    Back to Edit
                  </button>
                  <button 
                    type="button" 
                    onClick={handleCloseEdit} 
                    className="button-secondary" 
                    style={{ padding: '10px 24px', marginRight: '12px' }}
                    disabled={saving}
                  >
                    Cancel
                  </button>
                  <button 
                    type="button" 
                    onClick={handleConfirmSave} 
                    className="button-primary" 
                    style={{ padding: '10px 24px', backgroundColor: isSuspension ? 'var(--warning-color)' : 'var(--primary)' }}
                    disabled={saving}
                  >
                    {saving ? 'Saving...' : 'Confirm & Save Changes'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default PlatformTenantDetail;
