/**
 * Phase 1B.1B & 1B.3: Read-only client detail drawer.
 *
 * Displays a safe view model of the selected client. Relocates client-action
 * buttons from the card to the drawer footer. Displays individual PET records.
 */

import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { buildClientDetailViewModel } from '../utils/clientManagement';

const ClientDetailDrawer = ({
  client,
  pets,
  onClose,
  onEdit,
  onExecuteAction,
  onLinkEmail,
  onCreateProfile,
  isProtectedProfile
}) => {
  const closeBtnRef = useRef(null);
  const drawerRef = useRef(null);
  const vm = buildClientDetailViewModel(client);

  // Focus management: move focus into drawer on open
  useEffect(() => {
    if (closeBtnRef.current) {
      closeBtnRef.current.focus();
    }
    // Lock body scroll, preserving prior value
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

  if (!vm) return null;

  return createPortal(
    <div
      className="client-detail-drawer-overlay"
      role="dialog"
      aria-modal="true"
      aria-label={`Client details: ${vm.displayName}`}
      onClick={(e) => { e.stopPropagation(); onClose(); }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      <div
        className="client-detail-drawer"
        ref={drawerRef}
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="client-detail-drawer-header">
          <h3>{vm.displayName}</h3>
          <button
            type="button"
            ref={closeBtnRef}
            className="drawer-close-button"
            aria-label="Close client details"
            onClick={onClose}
          >&times;</button>
        </div>

        {/* Scrollable content */}
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
            {pets && pets.length > 0 ? (
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

        {/* Section 5: Actions & Danger Zone */}
        <div className="client-detail-drawer-footer" style={{ padding: '20px 24px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '12px', flexShrink: 0, backgroundColor: 'var(--card-bg)' }}>
          <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Actions</h4>
          
          <div className="btn-group" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="button-primary btn-small"
              onClick={() => {
                onEdit(client);
                onClose();
              }}
            >
              Edit Profile
            </button>

            {client.is_virtual ? (
              <button
                type="button"
                className="btn-small"
                onClick={() => {
                  onCreateProfile(client);
                  onClose();
                }}
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
      </div>
    </div>,
    document.body
  );
};

export default ClientDetailDrawer;
