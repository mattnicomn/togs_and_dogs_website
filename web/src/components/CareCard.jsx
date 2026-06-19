import React, { useState, useEffect } from 'react';
import '../Portal.css';
import { createPaymentSession, sendPaymentEmail } from '../api/client';

const CareCard = ({ pet, onClose, onUpdate, onStatusUpdate, userRole, staffList = [], onAssign, onAddPet, onPaymentSessionCreated }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [isEditing, setIsEditing] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState((pet._originItem?.status || '').toUpperCase());
  const [statusNote, setStatusNote] = useState('');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  // Release 5B: Add pet form state
  const [isAddingPet, setIsAddingPet] = useState(false);
  const [isCreatingPet, setIsCreatingPet] = useState(false);
  const [newPetForm, setNewPetForm] = useState({ name: '', species: 'DOG', breed: '', age: '', feeding_notes: '', medication_notes: '', behavior_notes: '', vet_notes: '', emergency_notes: '' });
  // Release 5C: Archive pet confirmation state
  const [archiveConfirm, setArchiveConfirm] = useState(false);
  const [isArchiving, setIsArchiving] = useState(false);
  // Release 5F: Archived pets visibility toggle
  const [showArchived, setShowArchived] = useState(false);
  const [formData, setFormData] = useState({ 
    health: {}, 
    document_links: {}, 
    scheduled_duration: 60,
    ...pet 
  });

  // Release 4E: Staff assignment state
  const [isAssigning, setIsAssigning] = useState(false);

  // Release 12R: Stripe payment session states
  const [paymentAmount, setPaymentAmount] = useState('');
  const [isGeneratingLink, setIsGeneratingLink] = useState(false);
  const [paymentError, setPaymentError] = useState('');
  const [showConfirmPaymentGen, setShowConfirmPaymentGen] = useState(false);
  const [copySuccess, setCopySuccess] = useState(false);

  // Release 12V: Send payment-link email states
  const [showConfirmEmailModal, setShowConfirmEmailModal] = useState(false);
  const [isSendingEmail, setIsSendingEmail] = useState(false);
  const [emailSendSuccess, setEmailSendSuccess] = useState(false);
  const [emailSendError, setEmailSendError] = useState('');
  const [secondsRemaining, setSecondsRemaining] = useState(0);

  // Release 12R: Initialize and reset payment states when pet prop changes
  // Note: activePet is derived later from _normalizePets(); use pet prop directly here
  useEffect(() => {
    const originItem = pet._originItem || {};
    const initialAmount = originItem.payment_amount_cents 
      ? (originItem.payment_amount_cents / 100).toFixed(2) 
      : (pet.quote_amount ? parseFloat(pet.quote_amount).toFixed(2) : '');
    setPaymentAmount(initialAmount);
    setPaymentError('');
    setShowConfirmPaymentGen(false);
    setCopySuccess(false);

    // Release 12V: Reset email send states on pet prop change
    setShowConfirmEmailModal(false);
    setEmailSendSuccess(false);
    setEmailSendError('');
  }, [pet]);

  // Release 12V: Countdown timer for rate limiting/disabled state (recently sent within 2 minutes)
  const lastSentAt = pet._originItem?.payment_email_sent_at;
  const clientEmail = pet._originItem?.client_email || pet.client_email || '';
  useEffect(() => {
    if (!lastSentAt) {
      setSecondsRemaining(0);
      return;
    }
    const updateCountdown = () => {
      const diffMs = Date.now() - new Date(lastSentAt).getTime();
      const remainingMs = 120000 - diffMs;
      if (remainingMs > 0) {
        setSecondsRemaining(Math.ceil(remainingMs / 1000));
      } else {
        setSecondsRemaining(0);
      }
    };
    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [lastSentAt]);

  const handleGeneratePaymentLink = async () => {
    const trimmed = typeof paymentAmount === 'string' ? paymentAmount.trim() : String(paymentAmount || '');
    if (!trimmed) {
      setPaymentError("Amount is required and cannot be blank.");
      return;
    }
    const parsedAmount = parseFloat(trimmed);
    if (isNaN(parsedAmount)) {
      setPaymentError("Amount must be a valid number.");
      return;
    }
    if (parsedAmount <= 0) {
      setPaymentError("Amount must be greater than $0.00.");
      return;
    }
    // Limit maximum charge to $10,000.00 to prevent accidental large charges
    const maxUsd = 10000;
    if (parsedAmount > maxUsd) {
      setPaymentError(`Amount cannot exceed the maximum limit of $${maxUsd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}.`);
      return;
    }

    const amountCents = Math.round(parsedAmount * 100);
    const reqId = pet._originItem?.request_id || pet.request_id;
    const clientId = pet._originItem?.linked_client_profile_id || pet._originItem?.client_id || pet.client_id;

    if (!reqId || !clientId) {
      setPaymentError("Could not resolve Request ID or Client ID.");
      return;
    }

    setIsGeneratingLink(true);
    setPaymentError('');

    try {
      const response = await createPaymentSession(reqId, clientId, amountCents);
      setShowConfirmPaymentGen(false);
      
      if (onPaymentSessionCreated) {
        const updatedOrigin = {
          ...pet._originItem,
          payment_status: response.payment_status,
          stripe_payment_url: response.stripe_payment_url,
          stripe_checkout_session_id: response.stripe_checkout_session_id,
          payment_amount_cents: amountCents
        };
        await onPaymentSessionCreated(updatedOrigin);
      } else if (onUpdate) {
        await onUpdate({ ...activePet });
      }
    } catch (err) {
      console.error("Payment session generation failed:", err);
      setPaymentError(err.message || "Failed to generate payment session. Please try again.");
    } finally {
      setIsGeneratingLink(false);
    }
  };

  const handleSendPaymentEmail = async () => {
    const reqId = pet._originItem?.request_id || pet.request_id;
    const clientId = pet._originItem?.linked_client_profile_id || pet._originItem?.client_id || pet.client_id;

    if (!reqId || !clientId) {
      setEmailSendError("Could not resolve Request ID or Client ID.");
      return;
    }

    setIsSendingEmail(true);
    setEmailSendError('');
    setEmailSendSuccess(false);

    try {
      const response = await sendPaymentEmail(reqId, clientId);
      setEmailSendSuccess(true);
      setShowConfirmEmailModal(false);
      setSecondsRemaining(120); // Immediately trigger 2-minute cooldown locally

      if (onPaymentSessionCreated) {
        const updatedOrigin = {
          ...pet._originItem,
          payment_email_sent_at: new Date().toISOString(),
          payment_email_last_recipient: clientEmail
        };
        await onPaymentSessionCreated(updatedOrigin);
      }
    } catch (err) {
      console.error("Payment email send failed:", err);
      if (err.message && (err.message.includes('429') || err.message.toLowerCase().includes('too many requests') || err.message.toLowerCase().includes('rate limit'))) {
        setEmailSendError("Rate limit exceeded. Maximum 3 payment email sends per request per hour. Please wait before trying again.");
      } else {
        setEmailSendError(err.message || "Failed to send payment email. Please try again.");
      }
    } finally {
      setIsSendingEmail(false);
    }
  };


  const getPaymentStatusBadge = (status) => {
    const normalizedStatus = (status || '').toLowerCase().trim();
    switch (normalizedStatus) {
      case 'paid':
        return { label: 'Paid', className: 'status-chip--ready', style: { backgroundColor: '#10b981', color: '#fff' } };
      case 'payment_link_sent':
        return { label: 'Payment Link Sent', className: 'status-chip--primary', style: { backgroundColor: '#3b82f6', color: '#fff' } };
      case 'payment_failed':
        return { label: 'Payment Failed', className: 'status-chip--urgent', style: { backgroundColor: '#ef4444', color: '#fff' } };
      case 'expired':
        return { label: 'Expired', className: 'status-chip--expired', style: { backgroundColor: '#f59e0b', color: '#fff' } };
      case 'refunded':
        return { label: 'Refunded', className: 'status-chip--neutral', style: { backgroundColor: '#6b7280', color: '#fff' } };
      case 'waived':
        return { label: 'Waived', className: 'status-chip--neutral', style: { backgroundColor: '#6b7280', color: '#fff' } };
      default:
        return { label: 'Unpaid / Not Set', className: 'status-chip--pending', style: { backgroundColor: '#9ca3af', color: '#fff' } };
    }
  };

  // Release 5A Hotfix 2: Comprehensive multi-pet normalization.
  // Builds a reliable pet array from any record format and tags each pet with metadata.
  const _normalizePets = () => {
    // Priority 1: True PET# records fetched from backend (have pet_id)
    if (pet._allPets && pet._allPets.length > 0 && pet._allPets.some(p => p.pet_id)) {
      // Release 5F: Show archived pets when toggle is on, otherwise filter them out
      const visiblePets = showArchived
        ? pet._allPets
        : pet._allPets.filter(p => p.is_active !== false);
      return {
        pets: visiblePets.length > 0 ? visiblePets : pet._allPets,
        hasTrueRecords: true,
        isLegacy: false,
        source: 'pet_records',
        hasArchivedPets: pet._allPets.some(p => p.is_active === false)
      };
    }
    
    // Priority 2: Request-level pets[] array (pre-approval, no PET# records yet)
    const requestPets = pet._originItem?.pets || pet._allPets?.filter(p => p._source === 'request') || [];
    if (requestPets.length > 0 && requestPets.some(p => p.name)) {
      return {
        pets: requestPets.filter(p => p.name).map((p, i) => ({ ...p, _source: 'request', _index: i })),
        hasTrueRecords: false,
        isLegacy: false,
        source: 'request_pets'
      };
    }
    
    // Priority 3: Legacy comma-separated pet_names — split into read-only tabs
    const petNamesStr = pet.name || pet._originItem?.pet_names || pet.pet_names || '';
    if (petNamesStr.includes(',')) {
      const names = petNamesStr.split(',').map(n => n.trim()).filter(n => n);
      if (names.length > 1) {
        return {
          pets: names.map((name, i) => ({ name, _source: 'legacy_split', _index: i })),
          hasTrueRecords: false,
          isLegacy: true,
          source: 'legacy_split'
        };
      }
    }
    
    // Fallback: single pet display
    return {
      pets: [pet],
      hasTrueRecords: !!pet.pet_id,
      isLegacy: false,
      source: 'single'
    };
  };

  const petInfo = _normalizePets();
  const allPets = petInfo.pets;
  const [activePetIndex, setActivePetIndex] = useState(0);
  const activePet = allPets[activePetIndex] || pet;
  const hasMultiplePets = allPets.length > 1;
  const canEditActivePet = petInfo.hasTrueRecords && !!activePet.pet_id && !activePet._fetchFailed;

  // Release 5B Hotfix 2: Auto-select newly added pet when _newPetIndex is set
  useEffect(() => {
    if (pet._newPetIndex !== undefined && pet._newPetIndex >= 0 && pet._newPetIndex < allPets.length) {
      setActivePetIndex(pet._newPetIndex);
    }
  }, [pet._newPetIndex, allPets.length]);

  // Release 5A Hotfix 2: Reinitialize formData when active pet changes.
  // Only runs when NOT in edit mode (edit mode blocks tab switching).
  useEffect(() => {
    if (!isEditing) {
      setFormData({
        health: {},
        document_links: {},
        scheduled_duration: 60,
        ...activePet
      });
    }
  }, [activePetIndex]);

  // Release 4B: Improved name fallback logic
  // Prioritizes actual pet names over the client name (common in legacy records)
  const activePetDisplayName = 
    (activePet.name && activePet.name !== pet.client_name ? activePet.name : null) || 
    activePet.pet_name || 
    pet.pet_names || 
    (pet._originItem && (pet._originItem.pet_names || pet._originItem.pet_name)) ||
    activePet.name || 
    'Pet';

  // Scroll lock: prevent background scrolling when CareCard is open
  useEffect(() => {
    const scrollY = window.scrollY;
    document.body.style.overflow = 'hidden';
    document.body.style.position = 'fixed';
    document.body.style.width = '100%';
    document.body.style.top = `-${scrollY}px`;

    return () => {
      document.body.style.overflow = '';
      document.body.style.position = '';
      document.body.style.width = '';
      document.body.style.top = '';
      window.scrollTo(0, scrollY);
    };
  }, []);

  if (!pet) return null;

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'visit', label: 'Visit Details' },
    { id: 'care', label: 'Pet Care' },
    { id: 'emergency', label: 'Vet & Emergency' },
    { id: 'quoting', label: 'Meet & Greet / Quote' },
    { id: 'scheduling', label: 'Scheduling / Staff' },
    { id: 'history', label: 'Admin Notes / History' }
  ];

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = async () => {
    try {
      // Release 5A: Save targets the active pet, not always the first pet.
      // Ensure pet_id and client_id come from activePet so the correct PET# record is updated.
      const saveData = {
        ...formData,
        pet_id: activePet.pet_id || formData.pet_id,
        client_id: activePet.client_id || formData.client_id
      };
      await onUpdate(saveData);
      if (pet._originItem && onStatusUpdate && selectedStatus !== pet._originItem.status) {
        await onStatusUpdate(pet._originItem, selectedStatus, statusNote || "Status updated via record edit.");
      }
      setIsEditing(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleCancel = () => {
    // Release 5A: Reset to activePet data, not the original first pet
    setFormData({ health: {}, document_links: {}, scheduled_duration: 60, ...activePet });
    setIsEditing(false);
  };

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview':
        return (
          <div className="tab-content">
            <div className="pet-identity">
              {activePet.photo_url ? (
                <img src={activePet.photo_url} alt={activePet.name} className="pet-avatar-large" />
              ) : (
                <div className="pet-placeholder-large">{activePet.name?.[0]}</div>
              )}
              <div>
                <h2>{isEditing ? <input value={formData.name || ''} onChange={e => handleInputChange('name', e.target.value)} className="form-control-inline" /> : activePetDisplayName}</h2>
                <p className="subtitle">
                  {isEditing ? (
                    <span className="edit-inline-group">
                      <input value={formData.breed || ''} onChange={e => handleInputChange('breed', e.target.value)} placeholder="Breed" />
                      <input type="number" value={formData.age || ''} onChange={e => handleInputChange('age', parseInt(e.target.value))} placeholder="Age" />
                    </span>
                  ) : `${activePet.species ? activePet.species + ' • ' : ''}${activePet.breed || 'Unknown Breed'} • ${activePet.age || '?'} years old`}
                </p>
              </div>
            </div>
            
            <div className="summary-cards" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '32px' }}>
              <div className="content-box">
                <h4>Health Summary</h4>
                <p>{activePet.care_instructions || 'No specific instructions.'}</p>
              </div>
              <div className="content-box">
                <h4>Status Overview</h4>
                <span className={`status-chip status-chip--${pet.status?.toLowerCase().replace(/_/g, '-') || 'pending'}`}>
                  {pet.status || 'PENDING'}
                </span>
                <p className="micro-text" style={{ marginTop: '8px' }}>Last updated: {pet.updated_at ? new Date(pet.updated_at).toLocaleDateString() : 'N/A'}</p>
              </div>
            </div>

            {/* Release 8Z: CareCard Visit Schedule Breakdown */}
            {pet._originItem?.job_completion_summary && (
              <section className="card-section" style={{ marginTop: '24px' }}>
                <h3>Visit Schedule ({pet._originItem.job_completion_summary.completed}/{pet._originItem.job_completion_summary.total} completed)</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '12px' }}>
                  {pet._originItem.job_completion_summary.jobs.map((job, idx) => {
                    const isDone = job.status === 'COMPLETED';
                    return (
                      <div key={job.job_id || idx} className="content-box" style={{
                        borderLeft: isDone ? '4px solid var(--success, #10b981)' : '4px solid var(--primary, #3b82f6)',
                        padding: '12px 16px',
                        background: 'var(--bg-muted, #f8f9fa)'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: '700', fontSize: '0.9rem' }}>
                            {isDone ? '✅' : '⏳'} Visit {job.occurrence_index || (idx + 1)} — {job.occurrence_date ? new Date(job.occurrence_date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Date TBD'}
                          </span>
                          <span className={`status-chip status-chip--${job.status.toLowerCase().replace(/_/g, '-')}`} style={{ margin: 0, padding: '2px 8px', fontSize: '0.7rem' }}>
                            {job.status}
                          </span>
                        </div>
                        {isDone ? (
                          <div style={{ marginTop: '8px', fontSize: '0.85rem', color: 'var(--text-muted, #6c757d)' }}>
                            <p style={{ margin: '2px 0' }}>
                              <strong>Completed By:</strong> {job.completed_by || 'Unknown'}
                            </p>
                            <p style={{ margin: '2px 0' }}>
                              <strong>Completed At:</strong> {job.completed_at ? new Date(job.completed_at).toLocaleString() : 'N/A'}
                            </p>
                            {job.visit_notes && (
                              <div style={{
                                marginTop: '8px',
                                padding: '10px',
                                background: 'var(--bg-card, #ffffff)',
                                borderRadius: '4px',
                                border: '1px solid var(--border-soft, #e9ecef)',
                                color: 'var(--text-main, #212529)',
                                fontStyle: 'normal'
                              }}>
                                <strong>Visit Notes:</strong> {job.visit_notes}
                              </div>
                            )}
                          </div>
                        ) : (
                          <div style={{ marginTop: '8px', fontSize: '0.85rem', color: 'var(--text-muted, #6c757d)' }}>
                            <p style={{ margin: 0 }}>
                              <strong>Assigned To:</strong> {job.worker_name || 'Unassigned'}
                            </p>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Completion Notes Section */}
            {pet._originItem && pet._originItem.status === 'COMPLETED' && (
              <section className="card-section" style={{ marginTop: '24px' }}>
                <h3>Visit Completion Info</h3>
                <div className="content-box">
                  <p><strong>Completed By:</strong> {pet._originItem.completed_by || 'Unknown'}</p>
                  <p><strong>Completed At:</strong> {pet._originItem.completed_at 
                    ? new Date(pet._originItem.completed_at).toLocaleString('en-US', { 
                        month: 'short', day: 'numeric', year: 'numeric', 
                        hour: 'numeric', minute: '2-digit', hour12: true 
                      })
                    : 'Not recorded'}</p>
                  <div style={{ marginTop: '12px' }}>
                    <strong>Visit Notes:</strong>
                    <p style={{ 
                      whiteSpace: 'pre-wrap', 
                      marginTop: '6px', 
                      padding: '12px', 
                      background: 'var(--bg-muted, #f8f9fa)', 
                      borderRadius: '6px', 
                      border: '1px solid var(--border-soft, #e9ecef)',
                      color: 'var(--text-main, #212529)',
                      fontStyle: pet._originItem.visit_notes ? 'normal' : 'italic'
                    }}>
                      {pet._originItem.visit_notes || 'No completion notes provided'}
                    </p>
                  </div>
                </div>
              </section>
            )}

            {/* Release 9A: Archive Info */}
            {pet._originItem && pet._originItem.status === 'ARCHIVED' && (
              <section className="card-section" style={{ marginTop: '24px' }}>
                <h3>Archive Info</h3>
                <div className="content-box">
                  <p><strong>Archived By:</strong> {pet._originItem.archived_by || 'Unknown'}</p>
                  <p><strong>Archived At:</strong> {pet._originItem.archived_at ? new Date(pet._originItem.archived_at).toLocaleString() : 'N/A'}</p>
                  <p><strong>Archive Reason:</strong> {pet._originItem.archive_reason || 'N/A'}</p>
                </div>
              </section>
            )}

            {/* Release 9A: Booking Controls */}
            {['owner', 'admin'].includes(userRole) && pet._originItem && (
              <section className="card-section" style={{ marginTop: '24px', borderTop: '1px solid var(--border-soft, #e9ecef)', paddingTop: '20px' }}>
                <h3>Booking Controls</h3>
                <div className="content-box" style={{ background: 'var(--bg-muted, #f8f9fa)', padding: '16px', borderRadius: '8px' }}>
                  {/* Test Data Toggle */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                    <div>
                      <strong style={{ fontSize: '0.95rem' }}>Test Data Status</strong>
                      <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted, #6c757d)' }}>
                        Toggle whether this is a validation/test booking.
                      </p>
                    </div>
                    <button
                      className={`btn-small ${pet._originItem.is_test_booking ? 'success' : 'primary-outline'}`}
                      onClick={() => {
                        const nextAction = pet._originItem.is_test_booking ? 'UNMARK_TEST' : 'MARK_TEST';
                        onStatusUpdate(pet._originItem, nextAction);
                      }}
                    >
                      {pet._originItem.is_test_booking ? 'Disable Test Mode' : 'Enable Test Mode'}
                    </button>
                  </div>

                  {/* Archive/Unarchive Action */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', borderTop: '1px solid var(--border-soft, #e9ecef)', paddingTop: '16px' }}>
                    <div>
                      <strong style={{ fontSize: '0.95rem' }}>Archive Booking</strong>
                      <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted, #6c757d)' }}>
                        {pet._originItem.status === 'ARCHIVED' ? 'Restore this archived booking back to active.' : 'Soft-archive this booking from active dashboards.'}
                      </p>
                    </div>
                    {pet._originItem.status === 'ARCHIVED' ? (
                      <button
                        className="btn-small primary-outline"
                        onClick={() => onStatusUpdate(pet._originItem, 'UNARCHIVE')}
                      >
                        Restore Booking
                      </button>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-end', width: '60%' }}>
                        {/* Archive reason & warning */}
                        {(() => {
                          const jobs = pet._originItem.job_completion_summary?.jobs || [];
                          const hasCompleted = jobs.some(j => j.status === 'COMPLETED');
                          return hasCompleted ? (
                            <span style={{ fontSize: '0.75rem', color: 'var(--warning, #f59e0b)', textAlign: 'right' }}>
                              ⚠️ Contains completed visits! Archiving preserves them but soft-archives active children.
                            </span>
                          ) : null;
                        })()}
                        
                        <div style={{ display: 'flex', gap: '8px', width: '100%', justifyContent: 'flex-end' }}>
                          <input 
                            id="archive-reason-input"
                            type="text" 
                            placeholder="Reason for archiving..." 
                            className="form-control-inline" 
                            style={{ flex: 1, fontSize: '0.85rem', padding: '4px 8px' }}
                          />
                          <button
                            className="btn-small dangerous-outline"
                            onClick={() => {
                              const inputEl = document.getElementById('archive-reason-input');
                              const reason = inputEl ? inputEl.value : '';
                              onStatusUpdate(pet._originItem, 'ARCHIVE', reason);
                            }}
                          >
                            Archive
                          </button>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Move to Trash (Delete) */}
                  {pet._originItem.status !== 'DELETED' && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-soft, #e9ecef)', paddingTop: '16px' }}>
                      <div>
                        <strong style={{ fontSize: '0.95rem' }}>Move to Trash</strong>
                        <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: 'var(--text-muted, #6c757d)' }}>
                          Soft-delete this record (requires Cancel or Archive first if active).
                        </p>
                      </div>
                      <button
                        className="btn-small dangerous-outline"
                        onClick={() => onStatusUpdate(pet._originItem, 'DELETE')}
                      >
                        Move to Trash
                      </button>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* Terms & Privacy Acceptance */}
            {pet._originItem && (
              <section className="card-section" style={{ marginTop: '24px' }}>
                <h3>Terms & Privacy</h3>
                <div className="content-box">
                  <p><strong>Terms Accepted:</strong> {pet._originItem.accepted_terms === true ? 'Yes' : 'Not recorded'}</p>
                  <p><strong>Privacy Accepted:</strong> {pet._originItem.accepted_privacy === true ? 'Yes' : 'Not recorded'}</p>
                  <p><strong>Terms Version:</strong> {pet._originItem.terms_version || 'Not recorded'}</p>
                  <p><strong>Privacy Version:</strong> {pet._originItem.privacy_version || 'Not recorded'}</p>
                  <p><strong>Accepted At:</strong> {pet._originItem.accepted_at 
                    ? new Date(pet._originItem.accepted_at).toLocaleString('en-US', { 
                        month: 'short', day: 'numeric', year: 'numeric', 
                        hour: 'numeric', minute: '2-digit', hour12: true 
                      })
                    : 'Not recorded'}</p>
                  <p><strong>Accepted By Email:</strong> {pet._originItem.accepted_by_email || 'Not recorded'}</p>
                  <p><strong>Source:</strong> {pet._originItem.source || 'Not recorded'}</p>
                </div>
              </section>
            )}
          </div>
        );

      case 'visit':
        return (
          <div className="tab-content">
            <section className="card-section">
              <h3>Service Information</h3>
              <div className="content-box">
                <div className="field">
                  <label>Service Type</label>
                  {isEditing ? (
                    <select value={formData.service_type || ''} onChange={e => handleInputChange('service_type', e.target.value)}>
                      <option value="PET_SITTING">Pet Sitting</option>
                      <option value="WALKING">Dog Walking</option>
                      <option value="OVERNIGHT">Overnight Stay</option>
                      <option value="OTHER">Other</option>
                    </select>
                  ) : <p>{pet.service_type || 'Not Specified'}</p>}
                </div>
                
                {pet.preferred_time && (
                  <div className="legacy-info">
                    <label>Legacy: Specific Time Requests</label>
                    <p>{pet.preferred_time}</p>
                  </div>
                )}

                <div className="field">
                  <label>Requested Window</label>
                  {/* Release 2: Display multi-select visit windows with backward compat */}
                  <p>{(pet.visit_windows || [pet.visit_window || 'ANYTIME']).join(', ')}</p>
                </div>
              </div>
            </section>
          </div>
        );

      case 'care':
        return (
          <div className="tab-content">
            {/* Release 4B: Show structured per-pet notes from activePet */}
            {(activePet.feeding_notes || activePet.medication_notes || activePet.behavior_notes) && (
              <>
                {activePet.feeding_notes && (
                  <section className="card-section">
                    <h3>Feeding Notes</h3>
                    <div className="content-box"><p>{activePet.feeding_notes}</p></div>
                  </section>
                )}
                {activePet.medication_notes && (
                  <section className="card-section" style={{ marginTop: '24px' }}>
                    <h3>Medication Notes</h3>
                    <div className="content-box"><p>{activePet.medication_notes}</p></div>
                  </section>
                )}
                {activePet.behavior_notes && (
                  <section className="card-section" style={{ marginTop: '24px' }}>
                    <h3>Behavior Notes</h3>
                    <div className="content-box"><p>{activePet.behavior_notes}</p></div>
                  </section>
                )}
              </>
            )}
            <section className="card-section" style={{ marginTop: '24px' }}>
              <h3>Behavior & Personality</h3>
              <div className="content-box">
                {isEditing ? (
                  <textarea rows="4" value={formData.behavior || ''} onChange={e => handleInputChange('behavior', e.target.value)} />
                ) : <p>{activePet.behavior || 'No behavioral notes.'}</p>}
              </div>
            </section>
            <section className="card-section" style={{ marginTop: '24px' }}>
              <h3>Care Instructions</h3>
              <div className="content-box">
                {isEditing ? (
                  <textarea rows="4" value={formData.care_instructions || ''} onChange={e => handleInputChange('care_instructions', e.target.value)} />
                ) : <p>{activePet.care_instructions || 'No specific instructions.'}</p>}
              </div>
            </section>
          </div>
        );

      case 'emergency':
        return (
          <div className="tab-content">
            {/* Release 4B: Household-level vet/emergency from request or client profile */}
            {(pet._originItem?.vet_info || pet._originItem?.emergency_contact_info) && (
              <section className="card-section" style={{ marginBottom: '24px' }}>
                <h3>Household Vet & Emergency</h3>
                <div className="content-box">
                  {pet._originItem?.vet_info && (
                    <div style={{ marginBottom: '12px' }}>
                      <p><strong>{pet._originItem.vet_info.vet_name || ''}{pet._originItem.vet_info.clinic_name ? ` — ${pet._originItem.vet_info.clinic_name}` : ''}</strong></p>
                      {pet._originItem.vet_info.clinic_phone && <p>📞 {pet._originItem.vet_info.clinic_phone}</p>}
                      {pet._originItem.vet_info.clinic_address && <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{pet._originItem.vet_info.clinic_address}</p>}
                    </div>
                  )}
                  {pet._originItem?.emergency_contact_info && (
                    <div style={{ borderTop: '1px solid var(--border-soft)', paddingTop: '12px' }}>
                      <p><strong>Emergency:</strong> {pet._originItem.emergency_contact_info.name || ''} {pet._originItem.emergency_contact_info.phone ? `— ${pet._originItem.emergency_contact_info.phone}` : ''}</p>
                    </div>
                  )}
                </div>
              </section>
            )}
            <div className="grid-2">
              <section className="card-section">
                <h3>Primary Vet</h3>
                <div className="content-box">
                  {isEditing ? (
                    <div className="edit-stack">
                      <input placeholder="Vet Name" value={formData.health?.vet_name || ''} onChange={e => handleInputChange('health', {...formData.health, vet_name: e.target.value})} />
                      <input placeholder="Vet Phone" value={formData.health?.vet_phone || ''} onChange={e => handleInputChange('health', {...formData.health, vet_phone: e.target.value})} />
                    </div>
                  ) : (
                    <>
                      <p><strong>{activePet.health?.vet_name || 'Not specified'}</strong></p>
                      {activePet.health?.vet_phone && <a href={`tel:${activePet.health.vet_phone}`} className="action-link">📞 {activePet.health.vet_phone}</a>}
                    </>
                  )}
                </div>
              </section>
              <section className="card-section">
                <h3>Emergency Contact</h3>
                <div className="content-box">
                  {isEditing ? (
                    <div className="edit-stack">
                      <input placeholder="Name" value={formData.health?.emergency_name || ''} onChange={e => handleInputChange('health', {...formData.health, emergency_name: e.target.value})} />
                      <input placeholder="Phone" value={formData.health?.emergency_phone || ''} onChange={e => handleInputChange('health', {...formData.health, emergency_phone: e.target.value})} />
                    </div>
                  ) : (
                    <>
                      <p><strong>{activePet.health?.emergency_name || 'Not specified'}</strong></p>
                      {activePet.health?.emergency_phone && <a href={`tel:${activePet.health.emergency_phone}`} className="action-link">📞 {activePet.health.emergency_phone}</a>}
                    </>
                  )}
                </div>
              </section>
            </div>
            {/* Release 4B: Per-pet vet/emergency notes */}
            {(activePet.vet_notes || activePet.emergency_notes) && (
              <section className="card-section" style={{ marginTop: '24px' }}>
                <h3>Per-Pet Notes — {activePet.name}</h3>
                <div className="content-box">
                  {activePet.vet_notes && <p><strong>Vet Notes:</strong> {activePet.vet_notes}</p>}
                  {activePet.emergency_notes && <p style={{ marginTop: '8px' }}><strong>Emergency Notes:</strong> {activePet.emergency_notes}</p>}
                </div>
              </section>
            )}
            <section className="card-section" style={{ marginTop: '24px' }}>
              <h3>Logistics & Access</h3>
              <div className="content-box">
                {isEditing ? (
                  <textarea rows="3" value={formData.logistics || ''} onChange={e => handleInputChange('logistics', e.target.value)} placeholder="Key location, codes, etc." />
                ) : <p className="prominent-note">{activePet.logistics || pet.logistics || 'No access instructions.'}</p>}
              </div>
            </section>
          </div>
        );

      case 'quoting':
        return (
          <div className="tab-content">
            <section className="card-section">
              <h3>Meet & Greet</h3>
              <div className="content-box">
                <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                  <span className={`status-chip status-chip--${pet.meet_and_greet_completed ? 'ready' : 'urgent'}`}>
                    {pet.meet_and_greet_completed ? '✓ Completed' : 'Required'}
                  </span>
                  {pet.meet_and_greet_scheduled_at && <span className="small-text">Scheduled: {new Date(pet.meet_and_greet_scheduled_at).toLocaleString()}</span>}
                </div>
              </div>
            </section>
            <section className="card-section" style={{ marginTop: '24px' }}>
              <h3>Pricing & Quote</h3>
              <div className="content-box">
                <div className="grid-2">
                  <div className="price-display">
                    <label className="micro-text">Quote Amount</label>
                    {/* Release 4D: Editable quote amount */}
                    {isEditing ? (
                      <input type="number" step="0.01" min="0" value={formData.quote_amount || ''} onChange={e => handleInputChange('quote_amount', e.target.value ? parseFloat(e.target.value) : 0)} style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '1.1rem' }} placeholder="0.00" />
                    ) : (
                      <p className="price-large">${activePet.quote_amount || '0.00'}</p>
                    )}
                  </div>
                  <div className="price-display">
                    <label className="micro-text">Payment Status</label>
                    {/* Release 4D: Editable payment status dropdown */}
                    {isEditing ? (
                      <select value={formData.payment_status || 'Not Quoted'} onChange={e => handleInputChange('payment_status', e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                        <option value="Not Quoted">Not Requested</option>
                        <option value="Quote Sent">Quote Sent</option>
                        <option value="Payment Pending">Payment Pending</option>
                        <option value="Accepted">Accepted</option>
                        <option value="Deposit Paid">Deposit Paid</option>
                        <option value="Partially Paid">Partially Paid</option>
                        <option value="Paid in Full">Paid in Full</option>
                        <option value="Refunded">Refunded</option>
                        <option value="Waived">Waived</option>
                      </select>
                    ) : (
                      <p><strong>{activePet.payment_status || 'Not Quoted'}</strong></p>
                    )}
                  </div>
                </div>
                {/* Release 4D: Deposit toggles */}
                {isEditing && (
                  <div style={{ display: 'flex', gap: '24px', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-soft)' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
                      <input type="checkbox" checked={formData.deposit_required || false} onChange={e => handleInputChange('deposit_required', e.target.checked)} />
                      Deposit Required
                    </label>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', fontSize: '0.9rem' }}>
                      <input type="checkbox" checked={formData.deposit_paid || false} onChange={e => handleInputChange('deposit_paid', e.target.checked)} />
                      Deposit Paid
                    </label>
                  </div>
                )}
                {!isEditing && (activePet.deposit_required || activePet.deposit_paid) && (
                  <div style={{ display: 'flex', gap: '16px', marginTop: '12px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                    {activePet.deposit_required && <span>💰 Deposit Required</span>}
                    {activePet.deposit_paid && <span>✅ Deposit Paid</span>}
                  </div>
                )}
                {/* Release 4D: Quote notes */}
                <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-soft)' }}>
                  <label className="micro-text">Quote Notes</label>
                  {isEditing ? (
                    <textarea rows="2" value={formData.quote_notes || ''} onChange={e => handleInputChange('quote_notes', e.target.value)} placeholder="Payment terms, special pricing notes..." style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)', marginTop: '4px' }} />
                  ) : (
                    <p style={{ marginTop: '4px', fontSize: '0.9rem' }}>{activePet.quote_notes || 'No notes.'}</p>
                  )}
                </div>
                {pet.document_links?.intake_form_url && (
                  <div style={{ marginTop: '16px', borderTop: '1px solid var(--border-soft)', paddingTop: '16px' }}>
                    <a href={pet.document_links.intake_form_url} target="_blank" rel="noopener noreferrer" className="doc-link">View Original Intake Form</a>
                  </div>
                )}
              </div>
            </section>

            {/* Release 12R: Pricing & Payment Section (Stripe Sandbox) */}
            {['owner', 'admin'].includes(userRole) && pet._originItem && (
              <section className="card-section" style={{ marginTop: '24px' }}>
                <h3>Pricing & Payment (Stripe Sandbox)</h3>
                <div className="content-box">
                  {/* Sandbox Warnings */}
                  <div style={{
                    background: 'rgba(245, 158, 11, 0.1)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    marginBottom: '20px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px'
                  }}>
                    <span style={{ fontSize: '1.2rem' }}>⚠️</span>
                    <div style={{ fontSize: '0.85rem', color: '#b45309', fontWeight: '500' }}>
                      <strong>Sandbox Payment Link:</strong> Do not send to real clients yet. Use test cards only.
                    </div>
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'top', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
                    <div>
                      <label className="micro-text">Stripe Payment Status</label>
                      <div style={{ marginTop: '6px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {(() => {
                          const statusDetails = getPaymentStatusBadge(pet._originItem?.payment_status);
                          return (
                            <span className={`status-chip ${statusDetails.className}`} style={{ ...statusDetails.style, padding: '4px 12px', borderRadius: '12px', fontSize: '0.85rem', fontWeight: '700', width: 'fit-content' }}>
                              {statusDetails.label}
                            </span>
                          );
                        })()}
                        {pet._originItem?.payment_email_send_count > 0 && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
                            ✉️ Sent {pet._originItem.payment_email_send_count} time(s)
                            {pet._originItem.payment_email_sent_at && ` (Last: ${new Date(pet._originItem.payment_email_sent_at).toLocaleDateString()})`}
                          </div>
                        )}
                      </div>
                    </div>

                    {pet._originItem?.payment_amount_cents > 0 && (
                      <div>
                        <label className="micro-text">Payment Amount</label>
                        <p style={{ margin: '4px 0 0 0', fontSize: '1.25rem', fontWeight: '800' }}>
                          ${(pet._originItem.payment_amount_cents / 100).toFixed(2)}
                        </p>
                      </div>
                    )}
                  </div>

                  {/* Error Banner */}
                  {paymentError && (
                    <div style={{
                      background: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid rgba(239, 68, 68, 0.3)',
                      padding: '12px',
                      borderRadius: '8px',
                      color: '#dc2626',
                      fontSize: '0.85rem',
                      marginBottom: '16px',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {paymentError}
                    </div>
                  )}

                  {/* Status-specific actions */}
                  {(() => {
                    const status = (pet._originItem?.payment_status || '').toLowerCase().trim();
                    
                    if (status === 'paid') {
                      return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#10b981', fontWeight: '600', fontSize: '0.95rem' }}>
                            <span>✓</span> Payment completed via Stripe sandbox. No actions required.
                          </div>
                          <div style={{ borderTop: '1px solid var(--border-soft)', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                            <div>🚫 <strong>Generate Payment Link:</strong> Disabled (Request is already paid)</div>
                            <div>🚫 <strong>Send Payment Email:</strong> Disabled (Request is already paid)</div>
                          </div>
                        </div>
                      );
                    }

                    if (status === 'refunded' || status === 'waived') {
                      return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6b7280', fontWeight: '600', fontSize: '0.95rem' }}>
                            <span>🛡️</span> Safe Mode: This request has been marked as {status}. No further payments or charge links can be created or processed.
                          </div>
                          <div style={{ borderTop: '1px solid var(--border-soft)', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                            <div>🚫 <strong>Generate Payment Link:</strong> Disabled (Request is {status})</div>
                            <div>🚫 <strong>Send Payment Email:</strong> Disabled (Request is {status})</div>
                          </div>
                        </div>
                      );
                    }

                    if (status === 'payment_link_sent') {
                      const paymentUrl = pet._originItem?.stripe_payment_url || '';
                      return (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                          <p style={{ margin: 0, fontSize: '0.95rem', color: 'var(--text-main)', fontWeight: '500' }}>
                            🔗 An active payment link exists for this request. The client may have been sent this link via email to complete their payment.
                          </p>
                          
                          {paymentUrl && (
                            <div style={{
                              display: 'flex',
                              gap: '8px',
                              background: 'var(--bg-muted, #f3f4f6)',
                              padding: '8px 12px',
                              borderRadius: '6px',
                              alignItems: 'center',
                              border: '1px solid var(--border-soft, #e5e7eb)',
                              width: '100%',
                              boxSizing: 'border-box'
                            }}>
                              <span style={{
                                fontSize: '0.85rem',
                                color: 'var(--text-main, #374151)',
                                textOverflow: 'ellipsis',
                                overflow: 'hidden',
                                whiteSpace: 'nowrap',
                                flex: 1
                              }}>
                                {paymentUrl}
                              </span>
                              <button
                                onClick={() => {
                                  navigator.clipboard.writeText(paymentUrl);
                                  setCopySuccess(true);
                                  setTimeout(() => setCopySuccess(false), 3000);
                                }}
                                className="btn-small secondary-outline"
                                style={{ flexShrink: 0, padding: '4px 8px', fontSize: '0.8rem' }}
                              >
                                {copySuccess ? 'Copied!' : 'Copy Link'}
                              </button>
                            </div>
                          )}

                          <div style={{ display: 'flex', gap: '12px', marginTop: '4px' }}>
                            {paymentUrl && (
                              <a 
                                href={paymentUrl} 
                                target="_blank" 
                                rel="noopener noreferrer" 
                                className="button-primary outline" 
                                style={{ 
                                  padding: '8px 16px', 
                                  fontSize: '0.9rem', 
                                  display: 'inline-flex', 
                                  alignItems: 'center', 
                                  justifyContent: 'center',
                                  textDecoration: 'none',
                                  cursor: 'pointer',
                                  minHeight: '38px',
                                  borderRadius: '6px'
                                }}
                              >
                                Test Payment Page
                              </a>
                            )}
                            <button
                              disabled={isGeneratingLink}
                              onClick={handleGeneratePaymentLink}
                              className="button-secondary"
                              style={{ padding: '8px 16px', fontSize: '0.9rem', minHeight: '38px', borderRadius: '6px' }}
                            >
                              {isGeneratingLink ? 'Retrieving...' : 'Retrieve Existing Link'}
                            </button>
                          </div>
                          <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            Note: Retrieving verifies the existing session state and does not create a new charge.
                          </p>

                          {/* Release 12V: Send Payment Email UI */}
                          {paymentUrl && (
                            <div style={{
                              marginTop: '16px',
                              paddingTop: '16px',
                              borderTop: '1px solid var(--border-soft, #e5e7eb)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '8px'
                            }}>
                              <h4 style={{ margin: '0 0 4px 0', fontSize: '0.95rem', fontWeight: '600', color: 'var(--text-heading)' }}>Send Payment Email</h4>
                              
                              <div style={{ fontSize: '0.85rem', color: 'var(--text-muted, #6b7280)', lineHeight: '1.4', background: 'rgba(255, 255, 255, 0.02)', padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--border)', marginBottom: '4px' }}>
                                ✉️ <strong>About this email:</strong> This will send the active Stripe Checkout link to the client email on file. To avoid spam, please do not resend repeatedly unless the client specifically requests it or the prior email delivery failed.
                              </div>

                              {clientEmail ? (
                                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                                  <strong>Recipient Email:</strong> {clientEmail}
                                </p>
                              ) : (
                                <p style={{ margin: 0, fontSize: '0.85rem', color: '#dc2626', fontWeight: 'bold' }}>
                                  ⚠️ Recipient Email is missing on this request record.
                                </p>
                              )}

                              {pet._originItem?.payment_email_sent_at && (
                                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                                  <strong>Last Sent Email:</strong> {new Date(pet._originItem.payment_email_sent_at).toLocaleString()}
                                </p>
                              )}
                              {pet._originItem?.payment_email_last_recipient && (
                                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                                  <strong>Last Recipient:</strong> {pet._originItem.payment_email_last_recipient}
                                </p>
                              )}
                              {pet._originItem?.payment_email_send_count !== undefined && (
                                <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                                  <strong>Email Send Count:</strong> {pet._originItem.payment_email_send_count} send(s)
                                </p>
                              )}
                              
                              <div style={{
                                background: 'rgba(245, 158, 11, 0.05)',
                                border: '1px dashed rgba(245, 158, 11, 0.4)',
                                padding: '10px 12px',
                                borderRadius: '6px',
                                fontSize: '0.8rem',
                                color: '#b45309',
                                marginTop: '4px'
                              }}>
                                <strong>⚠️ Sandbox Warning:</strong> The email will contain a Stripe Sandbox checkout link. Do not send this to clients for real payment processing.
                              </div>

                              <button
                                type="button"
                                disabled={isSendingEmail || secondsRemaining > 0 || !clientEmail}
                                onClick={() => {
                                  setEmailSendError('');
                                  setEmailSendSuccess(false);
                                  setShowConfirmEmailModal(true);
                                }}
                                className="button-primary"
                                style={{ marginTop: '8px', width: 'fit-content', minHeight: '38px', borderRadius: '6px' }}
                              >
                                {isSendingEmail ? 'Sending...' : `Send Payment Email${secondsRemaining > 0 ? ` (Wait ${secondsRemaining}s)` : ''}`}
                              </button>

                              {/* Disabled explanations for Send Payment Email */}
                              {!clientEmail && (
                                <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#dc2626' }}>
                                  ❌ <strong>Send Disabled:</strong> A client email address is required to send the payment link.
                                </p>
                              )}
                              {secondsRemaining > 0 && (
                                <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#b45309' }}>
                                  ⏳ <strong>Send Disabled (Cooldown):</strong> Please wait {secondsRemaining} seconds before sending another payment email to prevent duplicates.
                                </p>
                              )}

                              {/* Success / Error Banners */}
                              {emailSendError && (
                                <div style={{
                                  background: 'rgba(239, 68, 68, 0.1)',
                                  border: '1px solid rgba(239, 68, 68, 0.3)',
                                  padding: '12px',
                                  borderRadius: '8px',
                                  color: '#dc2626',
                                  fontSize: '0.85rem',
                                  marginTop: '12px',
                                  whiteSpace: 'pre-wrap'
                                }}>
                                  {emailSendError}
                                </div>
                              )}

                              {emailSendSuccess && (
                                <div style={{
                                  background: 'rgba(16, 185, 129, 0.1)',
                                  border: '1px solid rgba(16, 185, 129, 0.3)',
                                  padding: '12px',
                                  borderRadius: '8px',
                                  color: '#10b981',
                                  fontSize: '0.85rem',
                                  marginTop: '12px',
                                  whiteSpace: 'pre-wrap'
                                }}>
                                  ✓ Payment email sent successfully to {clientEmail}!
                                </div>
                              )}
                            </div>
                          )}

                          <div style={{ borderTop: '1px solid var(--border-soft)', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '6px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                            <div>🚫 <strong>Generate Payment Link:</strong> Disabled (A payment link already exists for this request. Use 'Retrieve Existing Link' to check status.)</div>
                          </div>
                        </div>
                      );
                    }

                    // Fallback for unpaid, payment_failed, expired, or not set
                    const trimmedAmount = typeof paymentAmount === 'string' ? paymentAmount.trim() : String(paymentAmount || '');
                    const parsedAmount = parseFloat(trimmedAmount);
                    const isAmountInvalid = !trimmedAmount || isNaN(parsedAmount) || parsedAmount <= 0;
                    const isEmailMissing = !clientEmail;
                    const isGenerateDisabled = isAmountInvalid || isEmailMissing || isGeneratingLink;

                    return (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted, #6b7280)', lineHeight: '1.4', background: 'rgba(255, 255, 255, 0.02)', padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                          💡 <strong>Before generating:</strong> Confirm the request amount is correct and final. Once generated, the payment link must be sent separately using the <strong>Send Payment Email</strong> action.
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#6b7280', fontWeight: '600', fontSize: '0.95rem' }}>
                          <span>❌</span> No payment has been completed for this request yet.
                        </div>

                        <div className="field" style={{ margin: 0 }}>
                          <label style={{ fontWeight: '600' }}>Amount to Charge (USD)</label>
                          <div style={{ position: 'relative', marginTop: '6px' }}>
                            <span style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }}>$</span>
                            <input
                              type="number"
                              step="0.01"
                              min="0.01"
                              value={paymentAmount}
                              onChange={(e) => setPaymentAmount(e.target.value)}
                              placeholder="0.00"
                              style={{ paddingLeft: '24px', width: '100%', boxSizing: 'border-box' }}
                              disabled={isGeneratingLink}
                            />
                          </div>
                        </div>

                        {!showConfirmPaymentGen ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <button
                              onClick={() => {
                                if (isGenerateDisabled) return;
                                setPaymentError('');
                                setShowConfirmPaymentGen(true);
                              }}
                              className="button-primary"
                              style={{ width: 'fit-content', padding: '10px 20px', minHeight: '40px', borderRadius: '8px', opacity: isGenerateDisabled ? 0.5 : 1, cursor: isGenerateDisabled ? 'not-allowed' : 'pointer' }}
                              disabled={isGenerateDisabled}
                            >
                              Generate Payment Link
                            </button>

                            {/* Disabled explanations for Generate Payment Link */}
                            {isAmountInvalid && (
                              <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#b45309' }}>
                                ⚠️ <strong>Generate Disabled:</strong> A valid, positive charge amount (greater than $0.00) is required.
                              </p>
                            )}
                            {isEmailMissing && (
                              <p style={{ margin: '4px 0 0 0', fontSize: '0.8rem', color: '#dc2626' }}>
                                ❌ <strong>Generate Disabled:</strong> Client email address is missing.
                              </p>
                            )}
                            <p style={{ margin: '8px 0 0 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                              🚫 <strong>Send Payment Email:</strong> Disabled (No active payment link exists. Please generate a payment link first.)
                            </p>
                          </div>
                        ) : (
                          <div style={{
                            background: 'var(--bg-muted, #f9fafb)',
                            padding: '16px',
                            borderRadius: '8px',
                            border: '1px solid var(--border-soft, #e5e7eb)'
                          }}>
                            <p style={{ margin: '0 0 12px 0', fontSize: '0.9rem', fontWeight: '600', color: 'var(--text-heading)' }}>
                              Confirm Payment Link Generation
                            </p>
                            <p style={{ margin: '0 0 16px 0', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                              Are you sure you want to generate a sandbox Stripe Checkout Session for <strong>${parseFloat(paymentAmount).toFixed(2)}</strong>?
                            </p>
                            <div style={{ display: 'flex', gap: '12px' }}>
                              <button
                                disabled={isGeneratingLink}
                                onClick={handleGeneratePaymentLink}
                                className="button-primary"
                                style={{ padding: '8px 16px', fontSize: '0.9rem', minHeight: '38px', borderRadius: '6px' }}
                              >
                                {isGeneratingLink ? 'Generating...' : 'Yes, Generate Link'}
                              </button>
                              <button
                                disabled={isGeneratingLink}
                                onClick={() => setShowConfirmPaymentGen(false)}
                                className="button-secondary outline"
                                style={{ padding: '8px 16px', fontSize: '0.9rem', minHeight: '38px', borderRadius: '6px' }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              </section>
            )}
          </div>
        );

      case 'scheduling':
        return (
          <div className="tab-content">
            <section className="card-section">
              <h3>Exact Scheduling</h3>
              <p className="micro-text" style={{ marginBottom: '16px' }}>Setting these will reflect in the Google Calendar event upon assignment.</p>
              <div className="content-box">
                <div className="edit-fields-stack">
                  <div className="field">
                    <label>Scheduled Date</label>
                    {isEditing ? (
                      <input type="date" value={formData.scheduled_date || formData.start_date || ''} onChange={e => handleInputChange('scheduled_date', e.target.value)} />
                    ) : <p>{formData.scheduled_date || formData.start_date || 'Not Set'}</p>}
                  </div>
                  <div className="field-group-row">
                    <div className="field-compact">
                      <label>Scheduled Time</label>
                      {isEditing ? (
                        <input type="time" value={formData.scheduled_time || ''} onChange={e => handleInputChange('scheduled_time', e.target.value)} />
                      ) : <p>{formData.scheduled_time || 'Not Set'}</p>}
                    </div>
                    <div className="field-compact">
                      <label>Duration (mins)</label>
                      {isEditing ? (
                        <input type="number" step="15" value={formData.scheduled_duration || 60} onChange={e => handleInputChange('scheduled_duration', parseInt(e.target.value))} />
                      ) : <p>{formData.scheduled_duration || 60} minutes</p>}
                    </div>
                  </div>
                </div>
              </div>
            </section>
            
            <section className="card-section" style={{ marginTop: '24px' }}>
              <h3>Staff Assignment</h3>
              <div className="content-box">
                {/* Release 4E: Inline staff assignment dropdown for owner/admin */}
                {onAssign && ['owner', 'admin'].includes(userRole) && pet._originItem?.job_id ? (
                  <div className="field">
                    <label>Assigned To</label>
                    <select
                      value={pet._originItem?.worker_id || pet.worker_id || ''}
                      onChange={async (e) => {
                        if (!e.target.value) return;
                        setIsAssigning(true);
                        try {
                          await onAssign(pet._originItem, e.target.value);
                        } catch(err) {
                          // Error handled by parent
                        } finally {
                          setIsAssigning(false);
                        }
                      }}
                      disabled={isAssigning}
                      style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)' }}
                    >
                      <option value="">Select Staff...</option>
                      {staffList.filter(s => s.is_assignable !== false && s.is_active !== false).map(s => (
                        <option key={s.email || s.display_name} value={s.email || s.display_name}>
                          {s.display_name}{s.email ? ` <${s.email}>` : ''}
                        </option>
                      ))}
                    </select>
                    {isAssigning && <p className="micro-text" style={{ marginTop: '6px' }}>Assigning...</p>}
                  </div>
                ) : onAssign && ['owner', 'admin'].includes(userRole) && !pet._originItem?.job_id ? (
                  <div>
                    <p><strong>Assigned To:</strong> {pet.worker_name || pet.worker_id || 'Unassigned'}</p>
                    <p className="micro-text" style={{ marginTop: '8px', color: 'var(--text-muted)' }}>
                      Approve this request to enable staff assignment.
                    </p>
                  </div>
                ) : (
                  <p><strong>Assigned To:</strong> {pet.worker_name || pet.worker_id || 'Unassigned'}</p>
                )}
                {/* Release 2: Show preferred sitter separately from assigned staff */}
                {pet.preferred_sitter_name && (
                  <p style={{ marginTop: '8px', fontSize: '0.9rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                    <strong>Client Prefers:</strong> {pet.preferred_sitter_name}
                  </p>
                )}
                {pet.google_event_id && (
                  <div className="calendar-status" style={{ marginTop: '12px', display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--primary)', fontSize: '0.9rem' }}>
                    <span className="icon">📅</span> Linked to Google Calendar
                  </div>
                )}
              </div>
            </section>
          </div>
        );

      case 'history':
        return (
          <div className="tab-content">
            <section className="card-section">
              <h3>Internal Admin Notes</h3>
              <div className="content-box">
                {isEditing ? (
                  <textarea rows="4" value={formData.admin_notes || ''} onChange={e => handleInputChange('admin_notes', e.target.value)} placeholder="Internal notes only visible to admins..." />
                ) : <p>{pet.admin_notes || 'No internal notes.'}</p>}
              </div>
            </section>
            
            {pet._originItem?.audit_log && (
              <section className="card-section" style={{ marginTop: '24px' }}>
                <h3>Audit History</h3>
                <div className="audit-log-compact">
                  {pet._originItem.audit_log.slice().reverse().map((log, i) => (
                    <div key={i} className="audit-entry">
                      <span className="audit-date">{new Date(log.timestamp).toLocaleString()}</span>
                      <span className="audit-action">{log.action}: {log.from} → {log.to}</span>
                    </div>
                  )).slice(0, 10)}
                </div>
              </section>
            )}
          </div>
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="care-card-overlay">
      <div className="care-card card">
        <header className="card-header-main">
          <div className="header-left">
            <h1 className="serif">{activePetDisplayName}</h1>
            <div className="status-badge-container">
              <span className={`status-chip status-chip--${pet.status?.toLowerCase().replace(/_/g, '-') || 'pending'}`}>
                {pet.status}
              </span>
            </div>
          </div>
          <button className="close-button" onClick={onClose}>&times;</button>
        </header>

        <nav className="care-card-tabs">
          {tabs.map(tab => (
            <div 
              key={tab.id} 
              className={`care-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </div>
          ))}
        </nav>

        <div className="care-card-body">
          {/* Release 5A Hotfix 2: Multi-pet selector with edit-mode blocking and source-aware display */}
          {hasMultiplePets && ['overview', 'care', 'emergency', 'quoting'].includes(activeTab) && (
            <div className="pet-selector-nav" style={{ 
              display: 'flex', gap: '8px', padding: '16px 24px', 
              background: 'var(--bg-muted)', borderBottom: '1px solid var(--border-soft)',
              flexWrap: 'wrap', alignItems: 'center'
            }}>
              {allPets.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => {
                    if (isEditing) return;
                    setActivePetIndex(idx);
                  }}
                  disabled={isEditing && idx !== activePetIndex}
                  className={`pet-chip ${idx === activePetIndex ? 'active' : ''}`}
                  style={{
                    padding: '6px 14px', borderRadius: '16px', cursor: isEditing && idx !== activePetIndex ? 'not-allowed' : 'pointer',
                    backgroundColor: idx === activePetIndex ? 'var(--primary)' : 'transparent',
                    color: idx === activePetIndex ? '#fff' : 'var(--text-primary)',
                    border: idx === activePetIndex ? 'none' : '1px solid var(--border)',
                    fontSize: '0.85rem', fontWeight: idx === activePetIndex ? '600' : '400',
                    opacity: isEditing && idx !== activePetIndex ? 0.5 : 1,
                    transition: 'all 0.15s ease'
                  }}
                >
                  {p.name || p.pet_name || `Pet ${idx + 1}`}
                  {/* Release 5F: Visual label for archived pets */}
                  {p.is_active === false && <span style={{ marginLeft: '4px', fontSize: '0.7rem', opacity: 0.7 }}>⊘</span>}
                </button>
              ))}
              {isEditing && (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginLeft: '8px' }}>
                  Save or cancel before switching pets
                </span>
              )}
              {/* Release 5B: Add Pet button — owner/admin only, requires linked client profile */}
              {onAddPet && ['owner', 'admin'].includes(userRole) && !isEditing && !isAddingPet && (pet._originItem?.linked_client_profile_id || pet._originItem?.client_id) && (
                <button
                  onClick={() => setIsAddingPet(true)}
                  style={{ padding: '6px 14px', borderRadius: '16px', border: '2px dashed var(--border)', background: 'none', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-muted)' }}
                >
                  + Add Pet
                </button>
              )}
              {/* Release 5F: Archive/Restore Pet with inline confirmation */}
              {['owner', 'admin'].includes(userRole) && !isEditing && !isAddingPet && canEditActivePet && hasMultiplePets && (
                activePet.is_active === false ? (
                  // Restore button for archived pets
                  <button
                    disabled={isArchiving}
                    onClick={async () => {
                      const pid = activePet.pet_id;
                      const cid = activePet.client_id || pet._originItem?.linked_client_profile_id || pet._originItem?.client_id;
                      if (!pid || !cid) return;
                      setIsArchiving(true);
                      try {
                        await onUpdate({ pet_id: pid, client_id: cid, is_active: true });
                        setActivePetIndex(0);
                      } catch (e) { console.error('Restore failed:', e); }
                      finally { setIsArchiving(false); }
                    }}
                    style={{ padding: '4px 10px', borderRadius: '12px', border: '1px solid rgba(76, 175, 80, 0.4)', background: 'rgba(76, 175, 80, 0.08)', cursor: 'pointer', fontSize: '0.75rem', color: 'var(--success, #4caf50)', marginLeft: 'auto' }}
                  >
                    {isArchiving ? 'Restoring...' : 'Restore Pet'}
                  </button>
                ) : archiveConfirm ? (
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', marginLeft: 'auto' }}>
                    <span style={{ fontSize: '0.75rem', color: 'var(--danger, #dc3545)' }}>Archive "{activePet.name}"?</span>
                    <button
                      disabled={isArchiving}
                      onClick={async () => {
                        const pid = activePet.pet_id;
                        const cid = activePet.client_id || pet._originItem?.linked_client_profile_id || pet._originItem?.client_id;
                        if (!pid || !cid) { setArchiveConfirm(false); return; }
                        setIsArchiving(true);
                        try {
                          await onUpdate({ pet_id: pid, client_id: cid, is_active: false });
                          setArchiveConfirm(false);
                          const newIndex = activePetIndex > 0 ? activePetIndex - 1 : 0;
                          setActivePetIndex(newIndex);
                        } catch (e) { console.error('Archive failed:', e); }
                        finally { setIsArchiving(false); }
                      }}
                      style={{ padding: '3px 10px', borderRadius: '8px', border: 'none', background: 'var(--danger, #dc3545)', color: '#fff', cursor: 'pointer', fontSize: '0.75rem' }}
                    >
                      {isArchiving ? '...' : 'Yes'}
                    </button>
                    <button onClick={() => setArchiveConfirm(false)} style={{ padding: '3px 10px', borderRadius: '8px', border: '1px solid var(--border)', background: 'none', cursor: 'pointer', fontSize: '0.75rem' }}>No</button>
                  </span>
                ) : (
                  <button
                    onClick={() => setArchiveConfirm(true)}
                    style={{ padding: '4px 10px', borderRadius: '12px', border: '1px solid rgba(220, 53, 69, 0.3)', background: 'rgba(220, 53, 69, 0.05)', cursor: 'pointer', fontSize: '0.75rem', color: 'var(--danger, #dc3545)', marginLeft: 'auto' }}
                  >
                    Archive Pet
                  </button>
                )
              )}
              {/* Release 5F: Show Archived toggle when archived pets exist */}
              {petInfo.hasArchivedPets && ['owner', 'admin'].includes(userRole) && !isEditing && (
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: 'var(--text-muted)', cursor: 'pointer', marginLeft: hasMultiplePets ? '0' : 'auto' }}>
                  <input type="checkbox" checked={showArchived} onChange={() => { setShowArchived(!showArchived); setActivePetIndex(0); }} style={{ width: '14px', height: '14px' }} />
                  Show Archived
                </label>
              )}
            </div>
          )}
          {/* Release 5B: Show Add Pet button even for single-pet records (no multi-pet selector visible) */}
          {!hasMultiplePets && ['overview'].includes(activeTab) && onAddPet && ['owner', 'admin'].includes(userRole) && !isEditing && !isAddingPet && (pet._originItem?.linked_client_profile_id || pet._originItem?.client_id) && (
            <div style={{ padding: '12px 24px', borderBottom: '1px solid var(--border-soft)', display: 'flex', gap: '12px', alignItems: 'center' }}>
              <button
                onClick={() => setIsAddingPet(true)}
                style={{ padding: '6px 14px', borderRadius: '16px', border: '2px dashed var(--border)', background: 'none', cursor: 'pointer', fontSize: '0.85rem', color: 'var(--text-muted)' }}
              >
                + Add Pet
              </button>
              {/* Release 5F Hotfix: Show Archived toggle even when only 1 active pet remains */}
              {petInfo.hasArchivedPets && ['owner', 'admin'].includes(userRole) && (
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: 'var(--text-muted)', cursor: 'pointer' }}>
                  <input type="checkbox" checked={showArchived} onChange={() => { setShowArchived(!showArchived); setActivePetIndex(0); }} style={{ width: '14px', height: '14px' }} />
                  Show Archived
                </label>
              )}
            </div>
          )}
          {/* Release 5F Hotfix: Show Archived toggle standalone when no Add Pet button and no multi-pet selector */}
          {!hasMultiplePets && !(['overview'].includes(activeTab) && onAddPet && ['owner', 'admin'].includes(userRole) && !isEditing && !isAddingPet && (pet._originItem?.linked_client_profile_id || pet._originItem?.client_id)) && petInfo.hasArchivedPets && ['owner', 'admin'].includes(userRole) && ['overview', 'care', 'emergency', 'quoting'].includes(activeTab) && (
            <div style={{ padding: '8px 24px', borderBottom: '1px solid var(--border-soft)' }}>
              <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '0.75rem', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <input type="checkbox" checked={showArchived} onChange={() => { setShowArchived(!showArchived); setActivePetIndex(0); }} style={{ width: '14px', height: '14px' }} />
                Show Archived
              </label>
            </div>
          )}
          {/* Release 5B: Add Pet inline form */}
          {isAddingPet && (
            <div style={{ padding: '20px 24px', background: 'rgba(76, 175, 80, 0.05)', borderBottom: '1px solid rgba(76, 175, 80, 0.2)' }}>
              <h4 style={{ margin: '0 0 12px 0' }}>Add New Pet</h4>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="field">
                  <label>Pet Name *</label>
                  <input type="text" value={newPetForm.name} onChange={e => setNewPetForm({...newPetForm, name: e.target.value})} placeholder="e.g. Luna" style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }} />
                </div>
                <div className="field">
                  <label>Species</label>
                  <select value={newPetForm.species} onChange={e => setNewPetForm({...newPetForm, species: e.target.value})} style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                    <option value="DOG">Dog</option>
                    <option value="CAT">Cat</option>
                    <option value="OTHER">Other</option>
                  </select>
                </div>
                <div className="field">
                  <label>Breed</label>
                  <input type="text" value={newPetForm.breed} onChange={e => setNewPetForm({...newPetForm, breed: e.target.value})} placeholder="e.g. Golden Retriever" style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }} />
                </div>
                <div className="field">
                  <label>Age</label>
                  <input type="number" min="0" max="30" value={newPetForm.age} onChange={e => setNewPetForm({...newPetForm, age: e.target.value})} placeholder="Years" style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }} />
                </div>
                <div className="field" style={{ gridColumn: 'span 2' }}>
                  <label>Feeding Notes</label>
                  <input type="text" value={newPetForm.feeding_notes} onChange={e => setNewPetForm({...newPetForm, feeding_notes: e.target.value})} placeholder="Food type, schedule..." style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }} />
                </div>
                <div className="field" style={{ gridColumn: 'span 2' }}>
                  <label>Medication Notes</label>
                  <input type="text" value={newPetForm.medication_notes} onChange={e => setNewPetForm({...newPetForm, medication_notes: e.target.value})} placeholder="Medications, dosage..." style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }} />
                </div>
                <div className="field" style={{ gridColumn: 'span 2' }}>
                  <label>Behavior Notes</label>
                  <input type="text" value={newPetForm.behavior_notes} onChange={e => setNewPetForm({...newPetForm, behavior_notes: e.target.value})} placeholder="Temperament, triggers..." style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid var(--border)' }} />
                </div>
              </div>
              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button
                  disabled={!newPetForm.name.trim() || isCreatingPet}
                  onClick={async () => {
                    setIsCreatingPet(true);
                    try {
                      const clientId = pet._originItem?.linked_client_profile_id || pet._originItem?.client_id || pet.client_id;
                      await onAddPet(clientId, {
                        ...newPetForm,
                        age: newPetForm.age ? parseInt(newPetForm.age) : null
                      });
                      setIsAddingPet(false);
                      setNewPetForm({ name: '', species: 'DOG', breed: '', age: '', feeding_notes: '', medication_notes: '', behavior_notes: '', vet_notes: '', emergency_notes: '' });
                    } catch (e) {
                      console.error('Failed to create pet:', e);
                    } finally {
                      setIsCreatingPet(false);
                    }
                  }}
                  className="button-primary"
                  style={{ padding: '8px 20px' }}
                >
                  {isCreatingPet ? 'Creating...' : 'Create Pet'}
                </button>
                <button onClick={() => setIsAddingPet(false)} className="button-secondary" style={{ padding: '8px 20px' }}>Cancel</button>
              </div>
              {!(pet._originItem?.linked_client_profile_id) && !(pet._originItem?.job_id) && (
                <p style={{ marginTop: '8px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                  ⚠️ Approve this request before adding pets.
                </p>
              )}
            </div>
          )}
          {/* Release 7B Phase 2: Warning notice for deleted/unavailable pets */}
          {activePet._fetchFailed && ['overview', 'care'].includes(activeTab) && (
            <div style={{ padding: '12px 24px', background: 'rgba(220, 53, 69, 0.08)', borderBottom: '1px solid rgba(220, 53, 69, 0.2)', fontSize: '0.85rem', color: 'var(--danger, #dc3545)' }}>
              ⚠️ Deleted/Unavailable pet record — this pet's database record is no longer available.
            </div>
          )}
          {/* Release 5A Hotfix 2: Legacy/request-level notice */}
          {hasMultiplePets && petInfo.isLegacy && ['overview', 'care'].includes(activeTab) && (
            <div style={{ padding: '12px 24px', background: 'rgba(255, 193, 7, 0.1)', borderBottom: '1px solid rgba(255, 193, 7, 0.3)', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              ⚠️ Legacy multi-pet record — individual pet editing is unavailable until pets are normalized.
            </div>
          )}
          {hasMultiplePets && petInfo.source === 'request_pets' && ['overview', 'care'].includes(activeTab) && (
            <div style={{ padding: '12px 24px', background: 'rgba(33, 150, 243, 0.08)', borderBottom: '1px solid rgba(33, 150, 243, 0.2)', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              ℹ️ Pre-approval pet data — editing will be available after this request is approved and pet records are created.
            </div>
          )}
          {renderTabContent()}
        </div>

        {pet._originItem && onStatusUpdate && (
          <div className="admin-quick-actions" style={{ marginTop: '32px', padding: '24px', background: 'var(--bg-warm)', borderRadius: '20px', border: '1px solid var(--border-soft)' }}>
            <h4 style={{ marginBottom: '16px' }}>Status & Lifecycle Actions</h4>
            <div className="grid-2" style={{ alignItems: 'flex-end', gap: '16px' }}>
              <div className="field" style={{ margin: 0 }}>
                <label>Change Status</label>
                <select 
                  value={selectedStatus} 
                  onChange={(e) => setSelectedStatus(e.target.value)}
                  className="status-select-admin"
                >
                  <optgroup label="Intake & Review">
                    <option value="PENDING_REVIEW">Needs Review</option>
                    <option value="PROFILE_CREATED">Profile Created</option>
                    <option value="READY_FOR_APPROVAL">New Request</option>
                  </optgroup>
                  <optgroup label="Meet & Greet">
                    <option value="MEET_GREET_REQUIRED">Needs M&G</option>
                    <option value="MG_SCHEDULED">M&G Scheduled</option>
                    <option value="MG_COMPLETED">M&G Completed</option>
                  </optgroup>
                  <optgroup label="Execution">
                    <option value="APPROVED">Approved / Booked</option>
                    <option value="ASSIGNED">Scheduled</option>
                    <option value="IN_PROGRESS">In Progress</option>
                    <option value="COMPLETED">Completed</option>
                  </optgroup>
                  <optgroup label="Lifecycle">
                    <option value="CANCELLED">Cancelled</option>
                    <option value="ARCHIVED">Archived</option>
                    <option value="DELETED">Trash (Soft)</option>
                  </optgroup>
                </select>
              </div>
              <button 
                className="button-primary" 
                style={{ height: '48px' }}
                disabled={isUpdatingStatus || (selectedStatus === (pet._originItem?.status || '').toUpperCase() && !statusNote)}
                onClick={async () => {
                  setIsUpdatingStatus(true);
                  try {
                    await onStatusUpdate(pet._originItem, selectedStatus, statusNote);
                    setStatusNote('');
                  } finally {
                    setIsUpdatingStatus(false);
                  }
                }}
              >
                {isUpdatingStatus ? 'Updating...' : 'Apply Status Change'}
              </button>
            </div>
            {selectedStatus === 'CANCELLED' && (
              <div className="field" style={{ marginTop: '16px' }}>
                <label>Cancellation Reason (Required)</label>
                <textarea 
                  rows="2"
                  value={statusNote}
                  onChange={(e) => setStatusNote(e.target.value)}
                  placeholder="Reason for cancellation..."
                />
              </div>
            )}
          </div>
        )}

        <footer className="card-footer">
          <div className="footer-left">
             {/* Release 5D Hotfix 1: Enhanced client traceability */}
             <p className="micro-text">Client ID: {pet.client_id}</p>
             {pet._originItem?.linked_client_profile_id && pet._originItem.linked_client_profile_id !== pet.client_id && (
               <p className="micro-text">Profile ID: {pet._originItem.linked_client_profile_id}</p>
             )}
             {pet._originItem?.client_name && (
               <p className="micro-text">Client: {pet._originItem.client_name}</p>
             )}
          </div>
          <div className="footer-actions">
            {isEditing ? (
              <>
                <button className="button-secondary outline" onClick={handleCancel}>Cancel</button>
                <button className="button-primary" onClick={handleSave}>Save Changes</button>
              </>
            ) : (
              <button 
                className="button-secondary" 
                onClick={() => setIsEditing(true)}
                disabled={activePet._fetchFailed}
              >
                {activePet._fetchFailed ? 'Record Unavailable' : (pet.pet_id ? 'Edit Record' : 'Create Profile')}
              </button>
            )}
          </div>
        </footer>
      </div>

      {/* Release 12V: Send Payment Email Confirmation Modal */}
      {showConfirmEmailModal && (
        <div className="modal-overlay" style={{ zIndex: 1100 }}>
          <div className="modal-content" style={{ maxWidth: '500px', padding: '24px' }}>
            <button
              className="modal-close-btn"
              onClick={() => setShowConfirmEmailModal(false)}
              aria-label="Close dialog"
            >
              ✕
            </button>
            <div className="modal-header" style={{ marginBottom: '16px' }}>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-heading)' }}>
                Confirm Send Payment Email
              </h2>
            </div>
            
            <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.9rem', color: 'var(--text-main)' }}>
              <p>Are you sure you want to send the payment-link email to the client?</p>
              
              <div style={{
                background: 'var(--bg-muted, #f9fafb)',
                padding: '16px',
                borderRadius: '8px',
                border: '1px solid var(--border-soft, #e5e7eb)',
                display: 'flex',
                flexDirection: 'column',
                gap: '8px'
              }}>
                <p style={{ margin: 0 }}><strong>Recipient Email:</strong> {clientEmail}</p>
                <p style={{ margin: 0 }}>
                  <strong>Amount:</strong> ${((pet._originItem?.payment_amount_cents || 0) / 100).toFixed(2)}
                </p>
                <p style={{ margin: 0 }}>
                  <strong>Client Name:</strong> {pet._originItem?.client_name || pet.client_name || 'N/A'}
                </p>
                <p style={{ margin: 0 }}>
                  <strong>Pet Name(s):</strong> {pet.name || pet._originItem?.pet_names || pet.pet_names || 'N/A'}
                </p>
                <p style={{ margin: 0 }}>
                  <strong>Request ID:</strong> {pet._originItem?.request_id || pet.request_id || 'N/A'}
                </p>
              </div>

              <div style={{
                background: 'rgba(245, 158, 11, 0.08)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                padding: '12px 16px',
                borderRadius: '8px',
                fontSize: '0.85rem',
                color: '#b45309',
                fontWeight: '500',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
                marginTop: '8px'
              }}>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                  <span>⚠️</span>
                  <strong>Sandbox / Test Mode Warning:</strong>
                </div>
                <div>
                  This request is in sandbox mode. The email will contain sandbox Stripe links for testing.
                </div>
              </div>

              <div style={{
                background: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                padding: '12px 16px',
                borderRadius: '8px',
                fontSize: '0.85rem',
                color: '#dc2626',
                fontWeight: '500',
                display: 'flex',
                gap: '8px',
                alignItems: 'center',
                marginTop: '4px'
              }}>
                <span>❗</span>
                <strong>Explicit Warning: Clicking "Send Email" will send a real email.</strong>
              </div>
            </div>

            <div className="modal-footer" style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '20px' }}>
              <button
                disabled={isSendingEmail}
                onClick={() => setShowConfirmEmailModal(false)}
                className="button-secondary outline"
                style={{ padding: '8px 16px', fontSize: '0.9rem', minHeight: '38px', borderRadius: '6px' }}
              >
                Cancel
              </button>
              <button
                disabled={isSendingEmail}
                onClick={handleSendPaymentEmail}
                className="button-primary"
                style={{ padding: '8px 16px', fontSize: '0.9rem', minHeight: '38px', borderRadius: '6px' }}
              >
                {isSendingEmail ? 'Sending...' : 'Send Email'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CareCard;
