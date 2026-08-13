import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { validateOnboardingTenant, previewOnboardingTenant } from '../api/platform';
import './PlatformAdmin.css';

const PlatformAdminOnboarding = () => {
  // Form fields
  const [companyId, setCompanyId] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [tier, setTier] = useState('starter');
  const [status, setStatus] = useState('disabled');
  const [notes, setNotes] = useState('');

  // Flow & State
  const [step, setStep] = useState(1); // 1: Input, 2: Validated, 3: Preview
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [previewResult, setPreviewResult] = useState(null);

  // Track if form was modified after generating preview (stale preview detector)
  const [previewIsStale, setPreviewIsStale] = useState(false);

  const resetFlow = () => {
    setValidationResult(null);
    setPreviewResult(null);
    setPreviewIsStale(false);
    setStep(1);
    setApiError(null);
  };

  const handleFieldChange = (setter) => (e) => {
    setter(e.target.value);
    if (previewResult) {
      setPreviewIsStale(true);
    }
  };

  const getPayload = () => ({
    company_id: companyId.trim(),
    display_name: displayName.trim(),
    subscription_tier: tier,
    subscription_status: status,
    notes: notes.trim(),
  });

  const handleValidate = async (e) => {
    if (e) e.preventDefault();
    if (loading) return;

    try {
      setLoading(true);
      setApiError(null);
      setPreviewIsStale(false);

      const res = await validateOnboardingTenant(getPayload());
      setValidationResult(res);

      if (res.valid) {
        setStep(2);
      } else {
        setStep(1);
      }
    } catch (err) {
      console.error('Validation API Error:', err);
      setApiError(err.message || 'Validation request failed. Please check input formatting.');
    } finally {
      setLoading(false);
    }
  };

  const handleGeneratePreview = async () => {
    if (loading) return;

    try {
      setLoading(true);
      setApiError(null);

      const res = await previewOnboardingTenant(getPayload());
      setPreviewResult(res);

      if (res.preview_state === 'PREVIEW_READY') {
        setPreviewIsStale(false);
        setStep(3);
      } else {
        setApiError(res.message || 'Failed to generate tenant preview.');
      }
    } catch (err) {
      console.error('Preview API Error:', err);
      setApiError(err.message || 'Preview generation failed.');
    } finally {
      setLoading(false);
    }
  };

  const formatLabel = (str) => {
    if (!str) return '—';
    return str.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  };

  return (
    <div className="platform-admin-container">
      {/* Header */}
      <header className="platform-header-section">
        <div className="platform-title-group">
          <h1>Tenant Onboarding Orchestrator</h1>
          <p>Preview & validate new tenant provisioning (V1 Preview Mode)</p>
        </div>
        <div className="platform-nav-actions">
          <Link to="/platform-admin" className="btn-back-platform">
            ← Back to Platform Registry
          </Link>
        </div>
      </header>

      {/* Prominent Safety & No-Writes Banner */}
      <div className="platform-alert-banner warning" style={{ display: 'block', marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', fontWeight: 'bold' }}>
          <span style={{ fontSize: '1.2rem' }}>⚠️</span>
          <span>PREVIEW-ONLY MODE — NO WRITES WILL OCCUR</span>
        </div>
        <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: '1.4' }}>
          This orchestrator operates strictly in read-only preview mode. No tenant will be created in DynamoDB,
          and no Cognito or Stripe provisioning will be triggered.
          <strong> Tenant creation requires separate approval and is not available in V1.</strong>
        </p>
      </div>

      {/* API Error Message */}
      {apiError && (
        <div className="platform-alert-banner danger" style={{ marginBottom: '24px' }}>
          <span>❌</span>
          <div>
            <strong>Error:</strong> {apiError}
          </div>
        </div>
      )}

      {/* Wizard Progress Bar */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '32px' }}>
        <div
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: 'var(--radius-sm)',
            background: step === 1 ? 'var(--primary)' : 'var(--card-bg-muted)',
            color: step === 1 ? '#fff' : 'var(--text-muted)',
            textAlign: 'center',
            fontWeight: 'bold',
            fontSize: '0.85rem',
          }}
        >
          1. Business Identity
        </div>
        <div
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: 'var(--radius-sm)',
            background: step === 2 ? 'var(--primary)' : 'var(--card-bg-muted)',
            color: step === 2 ? '#fff' : 'var(--text-muted)',
            textAlign: 'center',
            fontWeight: 'bold',
            fontSize: '0.85rem',
          }}
        >
          2. Field Validation
        </div>
        <div
          style={{
            flex: 1,
            padding: '12px',
            borderRadius: 'var(--radius-sm)',
            background: step === 3 ? 'var(--primary)' : 'var(--card-bg-muted)',
            color: step === 3 ? '#fff' : 'var(--text-muted)',
            textAlign: 'center',
            fontWeight: 'bold',
            fontSize: '0.85rem',
          }}
        >
          3. Proposed End State Preview
        </div>
      </div>

      {/* Form Container */}
      <div className="platform-card-section">
        <form onSubmit={handleValidate}>
          <h3>New Business Details</h3>

          <div className="edit-form-grid">
            {/* Company ID */}
            <div>
              <label htmlFor="onboarding-company-id" className="metadata-label">
                Company ID (Tenant Slug) *
              </label>
              <input
                id="onboarding-company-id"
                type="text"
                value={companyId}
                onChange={handleFieldChange(setCompanyId)}
                placeholder="e.g. acme_pets"
                className="modal-input"
                style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}
                disabled={loading}
              />
              <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '4px' }}>
                3–64 characters. Lowercase letters, numbers, and underscores only. Reserved: <code>tog_and_dogs</code>.
              </small>
            </div>

            {/* Display Name */}
            <div>
              <label htmlFor="onboarding-display-name" className="metadata-label">
                Display Name *
              </label>
              <input
                id="onboarding-display-name"
                type="text"
                value={displayName}
                onChange={handleFieldChange(setDisplayName)}
                placeholder="e.g. Acme Pet Care LLC"
                className="modal-input"
                style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}
                disabled={loading}
              />
              <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '4px' }}>
                Max 100 characters. Customer-facing business name.
              </small>
            </div>

            {/* Tier */}
            <div>
              <label htmlFor="onboarding-tier" className="metadata-label">
                Subscription Tier
              </label>
              <select
                id="onboarding-tier"
                value={tier}
                onChange={handleFieldChange(setTier)}
                style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', background: 'var(--card-bg)' }}
                disabled={loading}
              >
                <option value="starter">Starter (Max 20 clients, 1 staff)</option>
                <option value="professional">Professional (Max 100 clients, 5 staff)</option>
                <option value="premium">Premium (Max 500 clients, 15 staff)</option>
                <option value="enterprise">Enterprise (Unlimited)</option>
              </select>
            </div>

            {/* Status */}
            <div>
              <label htmlFor="onboarding-status" className="metadata-label">
                Initial Subscription Status
              </label>
              <select
                id="onboarding-status"
                value={status}
                onChange={handleFieldChange(setStatus)}
                style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', background: 'var(--card-bg)' }}
                disabled={loading}
              >
                <option value="disabled">Disabled (Default / Recommended prior to onboarding completion)</option>
                <option value="active">Active</option>
                <option value="trialing">Trialing</option>
                <option value="paused">Paused</option>
                <option value="canceled">Canceled</option>
              </select>
            </div>

            {/* Notes */}
            <div>
              <label htmlFor="onboarding-notes" className="metadata-label">
                Platform Admin Notes (Optional)
              </label>
              <textarea
                id="onboarding-notes"
                value={notes}
                onChange={handleFieldChange(setNotes)}
                placeholder="Internal onboarding notes or customer contact details..."
                rows={3}
                style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', background: 'var(--card-bg)' }}
                disabled={loading}
              />
            </div>
          </div>

          {/* Form Action Buttons */}
          <div style={{ display: 'flex', gap: '12px', marginTop: '24px' }}>
            <button
              type="submit"
              className="button-primary"
              disabled={loading || !companyId || !displayName}
            >
              {loading ? 'Processing...' : '1. Validate Fields'}
            </button>

            {step >= 2 && (
              <button
                type="button"
                className="button-secondary"
                onClick={handleGeneratePreview}
                disabled={loading}
              >
                {loading ? 'Generating Preview...' : '2. Generate Full Preview →'}
              </button>
            )}

            {(step > 1 || validationResult || previewResult) && (
              <button type="button" className="button-secondary" onClick={resetFlow} disabled={loading}>
                Reset
              </button>
            )}
          </div>
        </form>
      </div>

      {/* Validation Results Card */}
      {validationResult && (
        <div className="platform-card-section">
          <h3>Validation Outcome</h3>
          {validationResult.valid ? (
            <div className="platform-alert-banner" style={{ backgroundColor: 'rgba(74, 124, 89, 0.1)', color: 'var(--success-color)', borderLeftColor: 'var(--success-color)' }}>
              <span>✅</span>
              <div>
                <strong>Validation Passed!</strong> All fields match domain requirements and no company ID conflicts were found.
              </div>
            </div>
          ) : (
            <div className="platform-alert-banner danger">
              <span>❌</span>
              <div>
                <strong>Validation Failed:</strong> Please resolve the errors below.
              </div>
            </div>
          )}

          {/* Validation Errors */}
          {validationResult.errors && validationResult.errors.length > 0 && (
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ color: 'var(--warning-color)', marginBottom: '8px' }}>Errors</h4>
              <ul style={{ margin: 0, paddingLeft: '20px', color: 'var(--warning-color)' }}>
                {validationResult.errors.map((err, idx) => (
                  <li key={idx}>
                    {err.field ? <strong>{err.field}: </strong> : null}
                    {err.error}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Validation Warnings */}
          {validationResult.warnings && validationResult.warnings.length > 0 && (
            <div>
              <h4 style={{ color: '#c05621', marginBottom: '8px' }}>Warnings</h4>
              <ul style={{ margin: 0, paddingLeft: '20px', color: '#c05621' }}>
                {validationResult.warnings.map((warn, idx) => (
                  <li key={idx}>
                    {warn.field ? <strong>{warn.field}: </strong> : null}
                    {warn.warning}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Stale Preview Warning Banner */}
      {previewIsStale && previewResult && (
        <div className="platform-alert-banner warning" style={{ marginBottom: '24px' }}>
          <span>⚠️</span>
          <div>
            <strong>Inputs Modified:</strong> You have modified form fields since generating the preview.
            Click <strong>"2. Generate Full Preview"</strong> to regenerate an updated preview payload.
          </div>
        </div>
      )}

      {/* Step 3: Full Preview Display */}
      {previewResult && previewResult.preview_state === 'PREVIEW_READY' && (
        <div className="platform-card-section" style={{ border: '2px solid var(--primary)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3 style={{ margin: 0, border: 'none', padding: 0 }}>Proposed End State Preview</h3>
            <span className="platform-badge platform-badge status-active" style={{ fontSize: '0.85rem' }}>
              NO WRITES PERFORMED
            </span>
          </div>

          <div style={{ background: 'var(--card-bg-muted)', padding: '16px', borderRadius: 'var(--radius-sm)', marginBottom: '24px', fontFamily: 'monospace', fontSize: '0.85rem' }}>
            <div><strong>Preview Hash (SHA-256):</strong> {previewResult.preview_hash}</div>
            <div><strong>Generated At:</strong> {previewResult.generated_at}</div>
            <div><strong>Catalog Version:</strong> {previewResult.catalog_version}</div>
            <div><strong>No-Writes Marker:</strong> {String(previewResult.no_writes)}</div>
          </div>

          {/* Proposed Metadata */}
          <h4 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginBottom: '16px' }}>
            Proposed Tenant Metadata (TENANT#{companyId}/METADATA)
          </h4>
          <div className="platform-metadata-list" style={{ marginBottom: '24px' }}>
            <div className="metadata-item">
              <span className="metadata-label">Company ID</span>
              <span className="metadata-value monospace">{previewResult.proposed_metadata?.company_id}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Display Name</span>
              <span className="metadata-value">{previewResult.proposed_metadata?.display_name}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Subscription Tier</span>
              <span className="metadata-value">{formatLabel(previewResult.proposed_metadata?.subscription_tier)}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Subscription Status</span>
              <span className="metadata-value">{formatLabel(previewResult.proposed_metadata?.subscription_status)}</span>
            </div>
            <div className="metadata-item">
              <span className="metadata-label">Created By</span>
              <span className="metadata-value monospace">{previewResult.proposed_metadata?.created_by}</span>
            </div>
          </div>

          {/* Tier Limits */}
          <h4 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginBottom: '16px' }}>
            Derived Tier Entitlement Limits
          </h4>
          <div className="entitlements-grid" style={{ marginBottom: '24px' }}>
            {previewResult.tier_limits &&
              Object.entries(previewResult.tier_limits).map(([key, val]) => (
                <div key={key} className="entitlement-item">
                  <span className="entitlement-name">{formatLabel(key)}</span>
                  <span className="entitlement-val">
                    {typeof val === 'boolean' ? (val ? '✅ Yes' : '❌ No') : val.toLocaleString()}
                  </span>
                </div>
              ))}
          </div>

          {/* Proposed Audit Record */}
          <h4 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginBottom: '16px' }}>
            Proposed Platform Audit Log Entry
          </h4>
          <div style={{ background: 'var(--card-bg-muted)', padding: '16px', borderRadius: 'var(--radius-sm)', marginBottom: '24px', fontFamily: 'monospace', fontSize: '0.85rem' }}>
            <div><strong>PK:</strong> {previewResult.proposed_audit?.PK}</div>
            <div><strong>SK:</strong> {previewResult.proposed_audit?.SK}</div>
            <div><strong>Action:</strong> {previewResult.proposed_audit?.action}</div>
            <div><strong>Actor:</strong> {previewResult.proposed_audit?.actor}</div>
          </div>

          {/* Approval Checklist */}
          <h4 style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginBottom: '16px' }}>
            Pre-Apply Approval Checklist
          </h4>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {previewResult.approval_checklist?.map((item, idx) => (
              <li
                key={idx}
                style={{
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-xs)',
                  background: item.satisfied ? 'rgba(74, 124, 89, 0.1)' : 'var(--card-bg-muted)',
                  border: '1px solid var(--border-color)',
                  marginBottom: '8px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  fontSize: '0.9rem',
                }}
              >
                <span>{item.satisfied ? '✅' : '⏳'}</span>
                <span style={{ flex: 1 }}>{item.item}</span>
                <span style={{ fontSize: '0.75rem', fontWeight: 'bold', textTransform: 'uppercase', opacity: 0.7 }}>
                  {item.required ? 'Required' : 'Optional'}
                </span>
              </li>
            ))}
          </ul>

          {/* Bottom Confirmation Notice */}
          <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--border-color)', color: 'var(--text-muted)', fontSize: '0.85rem', textAlign: 'center' }}>
            📌 <strong>V1 Orchestrator Note:</strong> There is intentionally no "Apply" or "Create Tenant" button in V1.
            Tenant metadata provisioning remains gated on explicit Matthew approval.
          </div>
        </div>
      )}
    </div>
  );
};

export default PlatformAdminOnboarding;
