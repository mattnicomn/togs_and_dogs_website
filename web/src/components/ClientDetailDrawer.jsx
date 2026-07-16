/**
 * Phase 1B.1B: Read-only client detail drawer.
 *
 * Displays a safe view model of the selected client. Does not perform
 * any network requests on open or close. Does not expose PK, SK,
 * cognito_sub, company_id, or other internal identifiers.
 */

import React, { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { buildClientDetailViewModel } from '../utils/clientManagement';

const ClientDetailDrawer = ({ client, onClose }) => {
  const closeBtnRef = useRef(null);
  const vm = buildClientDetailViewModel(client);

  // Focus management: move focus into drawer on open
  useEffect(() => {
    if (closeBtnRef.current) {
      closeBtnRef.current.focus();
    }
    // Lock body scroll
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = '';
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
            {vm.petSummary ? (
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
      </div>
    </div>,
    document.body
  );
};

export default ClientDetailDrawer;
