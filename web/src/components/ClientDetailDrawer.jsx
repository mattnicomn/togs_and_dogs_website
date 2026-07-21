/**
 * Phase 1B.4A-E: Client Detail and Editor Drawer.
 *
 * Consolidates the read-only client details and profile editing/creation
 * workflows into a single right-side profile drawer.
 */

import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { buildClientDetailViewModel } from '../utils/clientManagement';

const ClientDetailDrawer = ({
  client,
  mode = 'view', // 'view' | 'edit' | 'create'
  formValues,
  setFormValues,
  onClose,
  onEdit,
  onCancel,
  onSave,
  isSaving = false,
  pets = [],
  loadingPets = false,
  onExecuteAction,
  onLinkEmail,
  onCreateProfile,
  isProtectedProfile,
  clientLinkPrompt,
  setClientLinkPrompt,
  onLinkExistingClientOnboard
}) => {
  const closeBtnRef = useRef(null);
  const drawerRef = useRef(null);
  const displayNameInputRef = useRef(null);
  const [validationError, setValidationError] = useState(null);

  const vm = buildClientDetailViewModel(client);

  // Focus management: move focus into drawer on open / mode change
  useEffect(() => {
    if ((mode === 'edit' || mode === 'create') && displayNameInputRef.current) {
      displayNameInputRef.current.focus();
    } else if (closeBtnRef.current) {
      closeBtnRef.current.focus();
    }
  }, [mode, client?.client_id]);

  // Lock body scroll, preserving prior value
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, []);

  // Escape key closes
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Focus containment: Tab/Shift+Tab stay within the drawer
  useEffect(() => {
    const FOCUSABLE_SELECTOR = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])';

    const handleTab = (e) => {
      if (e.key !== 'Tab' || !drawerRef.current) return;
      const focusable = Array.from(drawerRef.current.querySelectorAll(FOCUSABLE_SELECTOR))
        .filter(el => el.offsetParent !== null); // exclude hidden
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', handleTab);
    return () => document.removeEventListener('keydown', handleTab);
  }, []);

  if (!client) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    setValidationError(null);

    if (!formValues.display_name.trim()) {
      setValidationError("Display name is required");
      return;
    }

    const isProfileOnly = formValues.creation_mode === 'profile_only' && (mode === 'create');
    if (!isProfileOnly && !formValues.email.trim()) {
      setValidationError("Email is required for login invitation");
      return;
    }

    onSave(e);
  };

  const isEditingOrCreating = mode === 'edit' || mode === 'create';
  const headerTitle = mode === 'create'
    ? 'Add New Client Profile'
    : (mode === 'edit' ? `Edit Client: ${client.display_name || 'Unnamed Client'}` : vm?.displayName || 'Client Details');

  return createPortal(
    <div
      className="client-detail-drawer-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={mode === 'create' ? 'Add New Client Profile' : `Client details: ${client.display_name || 'Unnamed Client'}`}
      onClick={(e) => { e.stopPropagation(); onClose(); }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <form
        className="client-detail-drawer"
        ref={drawerRef}
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="client-detail-drawer-header">
          <h3>{headerTitle}</h3>
          <button
            type="button"
            ref={closeBtnRef}
            className="drawer-close-button"
            aria-label="Close client details"
            onClick={onClose}
          >&times;</button>
        </div>

        {/* Content Area */}
        {isEditingOrCreating ? (
          <div className="client-detail-drawer-content">
            {validationError && (
              <div className="error-banner" style={{ color: 'var(--warning-color, #f44336)', border: '1px solid var(--warning-color, #f44336)', padding: '12px', borderRadius: '8px', backgroundColor: 'rgba(244, 67, 54, 0.05)', fontSize: '0.9rem' }}>
                {validationError}
              </div>
            )}

            {/* Creation Settings (only in Create mode) */}
            {mode === 'create' && (
              <section className="drawer-section">
                <h4 className="drawer-section-title">Onboarding Settings</h4>
                <div className="field" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
                    <input
                      type="radio"
                      name="drawer_client_creation_mode"
                      value="onboard"
                      checked={formValues.creation_mode === 'onboard'}
                      onChange={(e) => setFormValues({ ...formValues, creation_mode: e.target.value })}
                    />
                    Create Login & Profile
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
                    <input
                      type="radio"
                      name="drawer_client_creation_mode"
                      value="profile_only"
                      checked={formValues.creation_mode === 'profile_only'}
                      onChange={(e) => setFormValues({ ...formValues, creation_mode: e.target.value })}
                    />
                    Create Profile Only (No Login)
                  </label>
                </div>
              </section>
            )}

            {/* Profile Fields Form */}
            <section className="drawer-section">
              <h4 className="drawer-section-title">Profile Details</h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div className="field">
                  <label htmlFor="drawer-display-name">Display Name *</label>
                  <input
                    id="drawer-display-name"
                    type="text"
                    ref={displayNameInputRef}
                    value={formValues.display_name || ''}
                    onChange={(e) => setFormValues({ ...formValues, display_name: e.target.value })}
                    required
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  />
                </div>

                <div className="field">
                  <label htmlFor="drawer-email">
                    Email Address {mode === 'edit' && '(Read-only)'} {formValues.creation_mode === 'onboard' ? '*' : '(Optional)'}
                  </label>
                  <input
                    id="drawer-email"
                    type="email"
                    value={formValues.email || ''}
                    onChange={(e) => setFormValues({ ...formValues, email: e.target.value })}
                    disabled={mode === 'edit'}
                    required={formValues.creation_mode === 'onboard'}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', backgroundColor: mode === 'edit' ? 'var(--bg-muted, #f8fafc)' : 'inherit', fontSize: '0.9rem' }}
                  />
                </div>

                <div className="field">
                  <label htmlFor="drawer-phone">Phone</label>
                  <input
                    id="drawer-phone"
                    type="text"
                    value={formValues.phone || ''}
                    onChange={(e) => setFormValues({ ...formValues, phone: e.target.value })}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  />
                </div>

                <div className="field">
                  <label htmlFor="drawer-address">Physical Address</label>
                  <textarea
                    id="drawer-address"
                    rows="2"
                    value={formValues.address || ''}
                    onChange={(e) => setFormValues({ ...formValues, address: e.target.value })}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  ></textarea>
                </div>

                <div className="field">
                  <label htmlFor="drawer-emergency-contact">Emergency Contact</label>
                  <input
                    id="drawer-emergency-contact"
                    type="text"
                    value={formValues.emergency_contact || ''}
                    onChange={(e) => setFormValues({ ...formValues, emergency_contact: e.target.value })}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  />
                </div>

                <div className="field">
                  <label htmlFor="drawer-notes">Client Notes (Internal)</label>
                  <textarea
                    id="drawer-notes"
                    rows="3"
                    value={formValues.notes || ''}
                    onChange={(e) => setFormValues({ ...formValues, notes: e.target.value })}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  ></textarea>
                </div>

                {mode === 'create' && formValues.creation_mode === 'onboard' && (
                  <div className="field" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <input
                      id="drawer-send-invite"
                      type="checkbox"
                      checked={formValues.send_invite}
                      onChange={(e) => setFormValues({ ...formValues, send_invite: e.target.checked })}
                    />
                    <label htmlFor="drawer-send-invite" style={{ cursor: 'pointer', margin: 0, fontSize: '0.9rem' }}>Send welcome invite email</label>
                  </div>
                )}
              </div>
            </section>

            {clientLinkPrompt && (
              <div className="existing-user-warning" style={{ border: '1px solid var(--border)', padding: '16px', borderRadius: '8px', backgroundColor: 'var(--bg-muted, #f8fafc)', fontSize: '0.9rem' }}>
                <p><strong>A login account already exists for {clientLinkPrompt.email}.</strong> Link it instead?</p>
                <div style={{ display: 'flex', gap: '10px', marginTop: '10px' }}>
                  <button
                    type="button"
                    className="button-primary btn-small"
                    onClick={onLinkExistingClientOnboard}
                  >
                    Link Existing
                  </button>
                  <button
                    type="button"
                    className="button-secondary btn-small"
                    onClick={() => setClientLinkPrompt(null)}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="client-detail-drawer-content">
            {/* Section 1: Client / Household Overview */}
            <section className="drawer-section">
              <h4 className="drawer-section-title">Client Overview</h4>
              <div className="client-detail-badges">
                <span className={`access-badge ${vm.profileStatusClass}`}>{vm.profileStatus}</span>
                <span className={`access-badge ${vm.accountStatusClass}`}>{vm.accountStatusLabel}</span>
                {vm.isVirtual && <span className="access-badge status-offline">Cognito Only</span>}
                {vm.isAutoCreated && <span className="access-badge status-offline">Auto-created</span>}
              </div>

              <dl className="client-detail-fields">
                {vm.email && (
                  <>
                    <dt>Email</dt>
                    <dd>{vm.email}</dd>
                  </>
                )}
                {vm.phone && (
                  <>
                    <dt>Phone</dt>
                    <dd>{vm.phone}</dd>
                  </>
                )}
                {vm.address && (
                  <>
                    <dt>Address</dt>
                    <dd>{vm.address}</dd>
                  </>
                )}
                {vm.emergencyContact && (
                  <>
                    <dt>Emergency Contact</dt>
                    <dd>{vm.emergencyContact}</dd>
                  </>
                )}
                {vm.notes && (
                  <>
                    <dt>Notes</dt>
                    <dd className="client-detail-notes">{vm.notes}</dd>
                  </>
                )}
                {!vm.email && !vm.phone && !vm.address && !vm.emergencyContact && !vm.notes && (
                  <dd className="client-detail-empty">No contact information on file.</dd>
                )}
              </dl>
            </section>

            {/* Section 2: Login Identity */}
            <section className="drawer-section">
              <h4 className="drawer-section-title">Login Identity</h4>
              <dl className="client-detail-fields">
                <dt>Client ID</dt>
                <dd style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>{client.client_id}</dd>
                <dt>Account Status</dt>
                <dd><span className={`access-badge ${vm.accountStatusClass}`}>{vm.accountStatusLabel}</span></dd>
                <dt>Portal Access</dt>
                <dd>{vm.portalAvailable ? 'Available' : 'Not available'}</dd>
                {vm.cognitoLifecycleLabel && (
                  <>
                    <dt>Login State</dt>
                    <dd>{vm.cognitoLifecycleLabel}</dd>
                  </>
                )}
              </dl>
            </section>

            {/* Section 3: Pets */}
            <section className="drawer-section">
              <h4 className="drawer-section-title">Pets</h4>
              {loadingPets ? (
                <p className="client-detail-empty" style={{ fontStyle: 'italic' }}>Loading pets...</p>
              ) : pets && pets.length > 0 ? (
                <ul className="client-drawer-pet-list" style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {pets.map((p, idx) => (
                    <li key={p.pet_id || idx} style={{ padding: '8px 12px', background: 'var(--bg-muted, #f8fafc)', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <strong>{p.name || 'Unnamed'}</strong> {p.species ? `(${p.species})` : ''} {p.breed ? `— ${p.breed}` : ''}
                      </div>
                      {p.is_active === false ? (
                        <span className="access-badge status-offline" style={{ fontSize: '10px' }}>Archived</span>
                      ) : (
                        <span className="access-badge status-profile-active" style={{ fontSize: '10px' }}>Active</span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : vm.petSummary ? (
                <p className="client-detail-pet-summary">🐾 {vm.petSummary}</p>
              ) : (
                <p className="client-detail-empty">No pet information available.</p>
              )}
            </section>

            {/* Section 4: Requests / History */}
            <section className="drawer-section">
              <h4 className="drawer-section-title">Requests</h4>
              {vm.requestCount !== null ? (
                <p>{vm.requestCount} request{vm.requestCount !== 1 ? 's' : ''} on record</p>
              ) : (
                <p className="client-detail-empty">
                  Detailed request history will be added in a later Client Management phase.
                </p>
              )}
            </section>
          </div>
        )}

        {/* Footer Area */}
        {isEditingOrCreating ? (
          <div className="client-detail-drawer-footer" style={{ padding: '20px 24px', borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end', gap: '12px', flexShrink: 0, backgroundColor: 'var(--card-bg)' }}>
            <button
              type="button"
              className="button-secondary"
              onClick={onCancel}
              disabled={isSaving}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="button-primary"
              disabled={isSaving}
            >
              {isSaving ? 'Saving...' : (mode === 'create' ? 'Create Client' : 'Save Changes')}
            </button>
          </div>
        ) : (
          <div className="client-detail-drawer-footer" style={{ padding: '20px 24px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '12px', flexShrink: 0, backgroundColor: 'var(--card-bg)' }}>
            <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Actions</h4>

            <div className="btn-group" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              <button
                type="button"
                className="button-primary btn-small"
                onClick={() => onEdit(client)}
              >
                Edit Profile
              </button>

              {client.is_virtual ? (
                <button
                  type="button"
                  className="btn-small"
                  onClick={() => onCreateProfile(client)}
                >
                  Create Profile
                </button>
              ) : null}

              {client.cognito_sub ? (
                <>
                  <button
                    type="button"
                    className="btn-small"
                    onClick={() => onExecuteAction(client.client_id, 'resend-invite')}
                    disabled={!['FORCE_CHANGE_PASSWORD', 'UNCONFIRMED'].includes(client.cognito_status)}
                  >
                    Resend Invite
                  </button>
                  <button
                    type="button"
                    className="btn-small"
                    onClick={() => onExecuteAction(client.client_id, 'reset-password')}
                    disabled={isProtectedProfile(client)}
                    title={isProtectedProfile(client) ? 'This account is protected and cannot be modified' : undefined}
                  >
                    Send Password Reset Email
                  </button>
                  <button
                    type="button"
                    className="btn-small"
                    onClick={() => onExecuteAction(client.client_id, 'set-temp-password')}
                    disabled={isProtectedProfile(client)}
                    title={isProtectedProfile(client) ? 'This account is protected and cannot be modified' : undefined}
                  >
                    Set Temporary Password
                  </button>
                </>
              ) : (
                !client.is_virtual && (
                  client.email ? (
                    <button
                      type="button"
                      className="btn-small secondary"
                      onClick={() => onLinkEmail(client)}
                    >
                      Link Login Account
                    </button>
                  ) : (
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      Offline client — add email to enable login
                    </span>
                  )
                )
              )}
            </div>

            {/* Danger Zone */}
            <div className="danger-zone" style={{ marginTop: '8px', padding: '12px', border: '1px solid var(--warning-color, #f44336)', borderRadius: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <h5 style={{ margin: 0, color: 'var(--warning-color, #f44336)', fontSize: '0.85rem', fontWeight: 600 }}>Danger Zone</h5>
              <div className="btn-group" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {client.is_virtual ? (
                  client.is_active !== false ? (
                    <button
                      type="button"
                      className="btn-small error"
                      disabled={isProtectedProfile(client)}
                      title={isProtectedProfile(client) ? 'This account is protected and cannot be modified' : undefined}
                      onClick={() => onExecuteAction(client.client_id, 'disable')}
                    >
                      Turn Off Login Access
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        className="btn-small"
                        onClick={() => onExecuteAction(client.client_id, 'enable')}
                      >
                        Restore Login Access
                      </button>
                      <button
                        type="button"
                        className="btn-small error"
                        disabled={isProtectedProfile(client)}
                        title={isProtectedProfile(client) ? 'This account is protected and cannot be modified' : undefined}
                        onClick={() => onExecuteAction(client.client_id, 'delete_cognito')}
                      >
                        Delete Login Account
                      </button>
                    </>
                  )
                ) : (
                  <>
                    {client.is_active !== false ? (
                      <button
                        type="button"
                        className="btn-small error"
                        disabled={isProtectedProfile(client)}
                        title={isProtectedProfile(client) ? 'This account is protected and cannot be modified' : undefined}
                        onClick={() => onExecuteAction(client.client_id, 'disable')}
                      >
                        Turn Off Login Access
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn-small"
                        onClick={() => onExecuteAction(client.client_id, 'enable')}
                      >
                        Restore Login Access
                      </button>
                    )}
                    {client.cognito_sub && (
                      <button
                        type="button"
                        className="btn-small"
                        disabled={isProtectedProfile(client)}
                        title={isProtectedProfile(client) ? 'This account is protected and cannot be modified' : undefined}
                        onClick={() => onExecuteAction(client.client_id, 'unlink')}
                      >
                        Unlink
                      </button>
                    )}
                    {client.is_active === false && (
                      <button
                        type="button"
                        className="btn-small error"
                        disabled={isProtectedProfile(client)}
                        title={isProtectedProfile(client) ? 'This account is protected and cannot be modified' : undefined}
                        onClick={() => onExecuteAction(client.client_id, 'delete_profile')}
                      >
                        Delete
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </form>
    </div>,
    document.body
  );
};

export default ClientDetailDrawer;
