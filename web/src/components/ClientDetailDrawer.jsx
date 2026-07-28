/**
 * Phase 1B.5B-A: Client Detail and Editor Drawer with Staff Pet Management.
 *
 * Consolidates the read-only client details, profile editing/creation, and
 * pet management (add / view / edit / archive / restore) into a single
 * right-side drawer with a Back-to-Client pet subview.
 *
 * Unsaved-change protection applies for both client profile edits and pet
 * form edits, guarding Close, Cancel, Back, and Escape.
 */

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { buildClientDetailViewModel } from '../utils/clientManagement';

// ---------------------------------------------------------------------------
// Pet form blank values
// ---------------------------------------------------------------------------
const BLANK_PET_FORM = {
  name: '',
  species: '',
  breed: '',
  age: '',
  care_instructions: '',
  feeding_notes: '',
  color: '',
  weight: '',
  medical_notes: '',
  behavioral_notes: '',
  vet_name: '',
  vet_phone: '',
};

// ---------------------------------------------------------------------------
// Normalise a name for duplicate comparison (lowercase, collapse whitespace)
// ---------------------------------------------------------------------------
const normaliseName = (s) => (s || '').trim().toLowerCase().replace(/\s+/g, ' ');

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
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
  onLinkExistingClientOnboard,
  // Phase 1B.5B-A additions
  onPetCreate,   // async (clientId, petData) => pet | throws
  onPetUpdate,   // async (petId, clientId, petData) => pet | throws
  userRole,      // 'owner' | 'admin' | 'staff'
}) => {
  const closeBtnRef = useRef(null);
  const drawerRef = useRef(null);
  const displayNameInputRef = useRef(null);
  const petNameInputRef = useRef(null);
  const [validationError, setValidationError] = useState(null);

  // Pet subview state
  // petSubview: null (client view) | 'add' | <pet object> (edit/view)
  const [petSubview, setPetSubview] = useState(null);
  const [petForm, setPetForm] = useState(BLANK_PET_FORM);
  const [petInitialForm, setPetInitialForm] = useState(BLANK_PET_FORM);
  const [petSubviewMode, setPetSubviewMode] = useState('view'); // 'view' | 'edit' | 'add'
  const [petSaving, setPetSaving] = useState(false);
  const [petError, setPetError] = useState(null);
  const [petDuplicateWarning, setPetDuplicateWarning] = useState(null);

  const vm = buildClientDetailViewModel(client);

  // Derived unsaved-change booleans
  const hasPetUnsavedChanges = (petSubviewMode === 'edit' || petSubviewMode === 'add') && (
    petForm.name !== petInitialForm.name ||
    petForm.species !== petInitialForm.species ||
    petForm.breed !== petInitialForm.breed ||
    petForm.age !== petInitialForm.age ||
    petForm.care_instructions !== petInitialForm.care_instructions ||
    petForm.feeding_notes !== petInitialForm.feeding_notes ||
    petForm.color !== petInitialForm.color ||
    petForm.weight !== petInitialForm.weight ||
    petForm.medical_notes !== petInitialForm.medical_notes ||
    petForm.behavioral_notes !== petInitialForm.behavioral_notes ||
    petForm.vet_name !== petInitialForm.vet_name ||
    petForm.vet_phone !== petInitialForm.vet_phone
  );

  // ---------------------------------------------------------------------------
  // Pet subview helpers
  // ---------------------------------------------------------------------------
  const openAddPet = () => {
    setPetForm(BLANK_PET_FORM);
    setPetInitialForm(BLANK_PET_FORM);
    setPetSubview('add');
    setPetSubviewMode('add');
    setPetError(null);
    setPetDuplicateWarning(null);
  };

  const mapApiToForm = (pet) => {
    if (!pet) return BLANK_PET_FORM;
    return {
      name: pet.name || '',
      species: pet.species || '',
      breed: pet.breed || '',
      age: pet.age || '',
      care_instructions: pet.care_instructions || '',
      feeding_notes: pet.feeding_notes || '',
      color: pet.color || '',
      weight: pet.weight || '',
      medical_notes: pet.medication_notes || '',
      behavioral_notes: pet.behavior_notes || '',
      vet_name: pet.health?.vet_name || '',
      vet_phone: pet.health?.vet_phone || '',
    };
  };

  const openViewPet = (pet) => {
    const populated = mapApiToForm(pet);
    setPetForm(populated);
    setPetInitialForm(populated);
    setPetSubview(pet);
    setPetSubviewMode('view');
    setPetError(null);
    setPetDuplicateWarning(null);
  };

  const openEditPet = (pet) => {
    const populated = mapApiToForm(pet);
    setPetForm(populated);
    setPetInitialForm(populated);
    setPetSubview(pet);
    setPetSubviewMode('edit');
    setPetError(null);
    setPetDuplicateWarning(null);
  };

  const handleBackToClient = useCallback(() => {
    if (hasPetUnsavedChanges) {
      if (!window.confirm('You have unsaved pet changes. Discard them?')) return;
    }
    setPetSubview(null);
    setPetSubviewMode('view');
    setPetError(null);
    setPetDuplicateWarning(null);
  }, [hasPetUnsavedChanges]);

  const handlePetFieldChange = (field, value) => {
    setPetForm((prev) => ({ ...prev, [field]: value }));
    if (field === 'name') setPetDuplicateWarning(null);
  };

  const handlePetSave = async () => {
    setPetError(null);
    if (!petForm.name.trim()) {
      setPetError('Pet name is required.');
      return;
    }

    // Duplicate name check (non-blocking warning)
    if (!petDuplicateWarning) {
      const normNew = normaliseName(petForm.name);
      const existing = pets.filter((p) => {
        const normExisting = normaliseName(p.name);
        if (petSubviewMode === 'edit' && petSubview?.pet_id) {
          return p.pet_id !== petSubview.pet_id && normExisting === normNew;
        }
        return normExisting === normNew;
      });
      if (existing.length > 0) {
        setPetDuplicateWarning(
          `A pet named "${existing[0].name}" already exists for this client. Continue anyway?`
        );
        return; // pause — user must confirm or rename
      }
    }

    setPetSaving(true);
    setPetDuplicateWarning(null);
    try {
      const payload = {
        name: petForm.name,
        species: petForm.species,
        breed: petForm.breed,
        age: petForm.age,
        care_instructions: petForm.care_instructions,
        feeding_notes: petForm.feeding_notes,
        medication_notes: petForm.medical_notes,
        behavior_notes: petForm.behavioral_notes,
        health: {
          ...(petSubview?.health || {}),
          vet_name: petForm.vet_name,
          vet_phone: petForm.vet_phone,
        },
      };

      if (petSubviewMode === 'add') {
        const created = await onPetCreate(client.client_id, payload);
        openViewPet(created);
      } else {
        const updated = await onPetUpdate(petSubview.pet_id, client.client_id, payload, 'update');
        openViewPet(updated);
      }
    } catch (err) {
      setPetError(err?.message || 'Failed to save pet. Please try again.');
    } finally {
      setPetSaving(false);
    }
  };

  const handlePetArchive = async (pet) => {
    if (!window.confirm(`Archive ${pet.name || 'this pet'}? They will be hidden from active lists.`)) return;
    setPetError(null);
    try {
      const updated = await onPetUpdate(pet.pet_id, client.client_id, { is_active: false }, 'archive');
      // If we are in the pet subview for this pet, refresh it
      if (petSubview && petSubview.pet_id === pet.pet_id) {
        openViewPet(updated);
      }
    } catch (err) {
      setPetError(err?.message || 'Failed to archive pet.');
    }
  };

  const handlePetRestore = async (pet) => {
    setPetError(null);
    try {
      const updated = await onPetUpdate(pet.pet_id, client.client_id, { is_active: true }, 'restore');
      if (petSubview && petSubview.pet_id === pet.pet_id) {
        openViewPet(updated);
      }
    } catch (err) {
      setPetError(err?.message || 'Failed to restore pet.');
    }
  };

  const handlePetCancelEdit = () => {
    if (hasPetUnsavedChanges) {
      if (!window.confirm('Discard unsaved pet changes?')) return;
    }
    if (petSubviewMode === 'add') {
      // Cancelling add → go back to client
      setPetSubview(null);
      setPetSubviewMode('view');
    } else {
      // Cancelling edit → return to view of same pet
      setPetSubviewMode('view');
      setPetForm(petInitialForm);
    }
    setPetError(null);
    setPetDuplicateWarning(null);
  };

  // ---------------------------------------------------------------------------
  // Focus management
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (petSubview !== null && petNameInputRef.current && (petSubviewMode === 'add' || petSubviewMode === 'edit')) {
      petNameInputRef.current.focus();
    } else if ((mode === 'edit' || mode === 'create') && displayNameInputRef.current && petSubview === null) {
      displayNameInputRef.current.focus();
    } else if (closeBtnRef.current) {
      closeBtnRef.current.focus();
    }
  }, [mode, petSubview, petSubviewMode, client?.client_id]);

  // Lock body scroll
  useEffect(() => {
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prevOverflow; };
  }, []);

  // Escape key listener with refs to avoid stale closure bindings
  const petSubviewRef = useRef(petSubview);
  const handleBackToClientRef = useRef(handleBackToClient);

  useEffect(() => {
    petSubviewRef.current = petSubview;
    handleBackToClientRef.current = handleBackToClient;
  }, [petSubview, handleBackToClient]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key !== 'Escape') return;
      if (petSubviewRef.current !== null) {
        handleBackToClientRef.current();
      } else {
        onClose();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Focus containment
  useEffect(() => {
    const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])';
    const handleTab = (e) => {
      if (e.key !== 'Tab' || !drawerRef.current) return;
      const focusable = Array.from(drawerRef.current.querySelectorAll(FOCUSABLE))
        .filter((el) => el.offsetParent !== null);
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
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
      setValidationError('Display name is required');
      return;
    }
    const isProfileOnly = formValues.creation_mode === 'profile_only' && (mode === 'create');
    if (!isProfileOnly && !formValues.email.trim()) {
      setValidationError('Email is required for login invitation');
      return;
    }
    onSave(e);
  };

  const isEditingOrCreating = mode === 'edit' || mode === 'create';
  const headerTitle = mode === 'create'
    ? 'Add New Client Profile'
    : (mode === 'edit'
      ? `Edit Client: ${client.display_name || 'Unnamed Client'}`
      : vm?.displayName || 'Client Details');

  // Whether staff can manage pets (owner / admin / staff)
  const canManagePets = ['owner', 'admin', 'staff'].includes(userRole);

  // ---------------------------------------------------------------------------
  // Render pet subview (add / view / edit)
  // ---------------------------------------------------------------------------
  const renderPetSubview = () => {
    const isFormMode = petSubviewMode === 'add' || petSubviewMode === 'edit';
    const petName = petSubview === 'add' ? 'New Pet' : (petSubview?.name || 'Pet Details');
    const petIsArchived = petSubview !== 'add' && petSubview?.is_active === false;

    return (
      <>
        {/* Pet subview header */}
        <div className="client-detail-drawer-header" style={{ gap: '8px' }}>
          <button
            type="button"
            className="btn-small"
            style={{ marginRight: 'auto', fontWeight: 500 }}
            onClick={handleBackToClient}
            aria-label="Back to client details"
          >
            ← Back to Client
          </button>
          <h3 style={{ margin: 0, fontSize: '1rem', flexShrink: 0 }}>
            {petSubviewMode === 'add' ? 'Add Pet' : (petSubviewMode === 'edit' ? `Edit: ${petName}` : petName)}
          </h3>
          <button
            type="button"
            ref={closeBtnRef}
            className="drawer-close-button"
            aria-label="Close drawer"
            onClick={onClose}
          >&times;</button>
        </div>

        {/* Pet subview content */}
        <div className="client-detail-drawer-content">
          {petIsArchived && (
            <div style={{ background: 'rgba(255,152,0,0.1)', border: '1px solid #ff9800', borderRadius: '8px', padding: '10px 14px', fontSize: '0.85rem', color: '#e65100', marginBottom: '4px' }}>
              ⚠️ This pet is archived.
            </div>
          )}

          {petError && (
            <div style={{ background: 'rgba(244,67,54,0.08)', border: '1px solid #f44336', borderRadius: '8px', padding: '10px 14px', fontSize: '0.85rem', color: '#c62828', marginBottom: '4px' }}>
              {petError}
            </div>
          )}

          {petDuplicateWarning && (
            <div style={{ background: 'rgba(255,152,0,0.1)', border: '1px solid #ff9800', borderRadius: '8px', padding: '10px 14px', fontSize: '0.85rem', color: '#e65100', marginBottom: '4px' }}>
              ⚠️ {petDuplicateWarning}
              <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                <button type="button" className="button-primary btn-small" onClick={handlePetSave}>
                  Save Anyway
                </button>
                <button type="button" className="button-secondary btn-small" onClick={() => setPetDuplicateWarning(null)}>
                  Go Back
                </button>
              </div>
            </div>
          )}

          <section className="drawer-section">
            <h4 className="drawer-section-title">Pet Information</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>

              {/* Name */}
              <div className="field">
                <label htmlFor="pet-name-field">
                  Name {isFormMode && <span aria-hidden="true">*</span>}
                </label>
                {isFormMode ? (
                  <input
                    id="pet-name-field"
                    ref={petNameInputRef}
                    type="text"
                    value={petForm.name}
                    onChange={(e) => handlePetFieldChange('name', e.target.value)}
                    placeholder="e.g. Buddy"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  />
                ) : (
                  <span style={{ fontSize: '0.95rem', fontWeight: 600 }}>{petForm.name || '—'}</span>
                )}
              </div>

              {/* Species */}
              <div className="field">
                <label htmlFor="pet-species-field">Species</label>
                {isFormMode ? (
                  <select
                    id="pet-species-field"
                    value={petForm.species}
                    onChange={(e) => handlePetFieldChange('species', e.target.value)}
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem', background: 'var(--card-bg)' }}
                  >
                    <option value="">— Select —</option>
                    <option value="DOG">Dog</option>
                    <option value="CAT">Cat</option>
                    <option value="BIRD">Bird</option>
                    <option value="RABBIT">Rabbit</option>
                    <option value="OTHER">Other</option>
                  </select>
                ) : (
                  <span style={{ fontSize: '0.9rem' }}>{petForm.species || '—'}</span>
                )}
              </div>

              {/* Breed */}
              <div className="field">
                <label htmlFor="pet-breed-field">Breed</label>
                {isFormMode ? (
                  <input
                    id="pet-breed-field"
                    type="text"
                    value={petForm.breed}
                    onChange={(e) => handlePetFieldChange('breed', e.target.value)}
                    placeholder="e.g. Golden Retriever"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  />
                ) : (
                  <span style={{ fontSize: '0.9rem' }}>{petForm.breed || '—'}</span>
                )}
              </div>

              {/* Age */}
              <div className="field">
                <label htmlFor="pet-age-field">Age</label>
                {isFormMode ? (
                  <input
                    id="pet-age-field"
                    type="text"
                    value={petForm.age}
                    onChange={(e) => handlePetFieldChange('age', e.target.value)}
                    placeholder="e.g. 3 years or 36 months"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  />
                ) : (
                  <span style={{ fontSize: '0.9rem' }}>{petForm.age || '—'}</span>
                )}
              </div>

              {/* Color */}
              {!isFormMode && (
                <div className="field">
                  <label htmlFor="pet-color-field">Color / Markings</label>
                  <span style={{ fontSize: '0.9rem' }}>{petForm.color || '—'}</span>
                </div>
              )}

              {/* Weight */}
              {!isFormMode && (
                <div className="field">
                  <label htmlFor="pet-weight-field">Weight (lbs)</label>
                  <span style={{ fontSize: '0.9rem' }}>{petForm.weight ? `${petForm.weight} lbs` : '—'}</span>
                </div>
              )}
            </div>
          </section>

          <section className="drawer-section">
            <h4 className="drawer-section-title">Care &amp; Feeding</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {/* Care Instructions */}
              <div className="field">
                <label htmlFor="pet-care-instructions-field">Care Instructions</label>
                {isFormMode ? (
                  <textarea
                    id="pet-care-instructions-field"
                    rows={3}
                    value={petForm.care_instructions}
                    onChange={(e) => handlePetFieldChange('care_instructions', e.target.value)}
                    placeholder="Special handling, daily routine, care needs…"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem', resize: 'vertical' }}
                  />
                ) : (
                  <span style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{petForm.care_instructions || '—'}</span>
                )}
              </div>

              {/* Feeding Notes */}
              <div className="field">
                <label htmlFor="pet-feeding-notes-field">Feeding Notes</label>
                {isFormMode ? (
                  <textarea
                    id="pet-feeding-notes-field"
                    rows={3}
                    value={petForm.feeding_notes}
                    onChange={(e) => handlePetFieldChange('feeding_notes', e.target.value)}
                    placeholder="Portions, schedule, dietary restrictions…"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem', resize: 'vertical' }}
                  />
                ) : (
                  <span style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{petForm.feeding_notes || '—'}</span>
                )}
              </div>
            </div>
          </section>

          <section className="drawer-section">
            <h4 className="drawer-section-title">Medical &amp; Veterinary</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>

              {/* Medical notes */}
              <div className="field">
                <label htmlFor="pet-medical-field">Medical Notes</label>
                {isFormMode ? (
                  <textarea
                    id="pet-medical-field"
                    rows={3}
                    value={petForm.medical_notes}
                    onChange={(e) => handlePetFieldChange('medical_notes', e.target.value)}
                    placeholder="Allergies, medications, conditions…"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem', resize: 'vertical' }}
                  />
                ) : (
                  <span style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{petForm.medical_notes || '—'}</span>
                )}
              </div>

              {/* Vet name */}
              <div className="field">
                <label htmlFor="pet-vet-name-field">Vet Name</label>
                {isFormMode ? (
                  <input
                    id="pet-vet-name-field"
                    type="text"
                    value={petForm.vet_name}
                    onChange={(e) => handlePetFieldChange('vet_name', e.target.value)}
                    placeholder="e.g. Dr. Smith"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  />
                ) : (
                  <span style={{ fontSize: '0.9rem' }}>{petForm.vet_name || '—'}</span>
                )}
              </div>

              {/* Vet phone */}
              <div className="field">
                <label htmlFor="pet-vet-phone-field">Vet Phone</label>
                {isFormMode ? (
                  <input
                    id="pet-vet-phone-field"
                    type="tel"
                    value={petForm.vet_phone}
                    onChange={(e) => handlePetFieldChange('vet_phone', e.target.value)}
                    placeholder="e.g. (555) 123-4567"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                  />
                ) : (
                  <span style={{ fontSize: '0.9rem' }}>{petForm.vet_phone || '—'}</span>
                )}
              </div>
            </div>
          </section>

          <section className="drawer-section">
            <h4 className="drawer-section-title">Behavior</h4>
            <div className="field">
              <label htmlFor="pet-behavioral-field">Behavioral Notes</label>
              {isFormMode ? (
                <textarea
                  id="pet-behavioral-field"
                  rows={3}
                  value={petForm.behavioral_notes}
                  onChange={(e) => handlePetFieldChange('behavioral_notes', e.target.value)}
                  placeholder="Temperament, quirks, special handling…"
                  style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem', resize: 'vertical' }}
                />
              ) : (
                <span style={{ fontSize: '0.9rem', whiteSpace: 'pre-wrap' }}>{petForm.behavioral_notes || '—'}</span>
              )}
            </div>
          </section>
        </div>

        {/* Pet subview footer */}
        <div className="client-detail-drawer-footer" style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', display: 'flex', gap: '10px', flexWrap: 'wrap', flexShrink: 0, backgroundColor: 'var(--card-bg)' }}>
          {isFormMode ? (
            <>
              <button
                type="button"
                className="button-primary btn-small"
                onClick={handlePetSave}
                disabled={petSaving}
              >
                {petSaving ? 'Saving…' : 'Save Pet'}
              </button>
              <button
                type="button"
                className="button-secondary btn-small"
                onClick={handlePetCancelEdit}
                disabled={petSaving}
              >
                Cancel
              </button>
            </>
          ) : (
            <>
              {canManagePets && (
                <button
                  type="button"
                  className="button-primary btn-small"
                  onClick={() => openEditPet(petSubview)}
                >
                  Edit Pet
                </button>
              )}
              {canManagePets && !petIsArchived && (
                <button
                  type="button"
                  className="btn-small error"
                  onClick={() => handlePetArchive(petSubview)}
                >
                  Archive
                </button>
              )}
              {canManagePets && petIsArchived && (
                <button
                  type="button"
                  className="btn-small"
                  onClick={() => handlePetRestore(petSubview)}
                >
                  Restore
                </button>
              )}
            </>
          )}
        </div>
      </>
    );
  };

  // ---------------------------------------------------------------------------
  // Main render
  // ---------------------------------------------------------------------------
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
        {/* ------------------------------------------------------------------ */}
        {/* Pet subview (replaces entire drawer content while active)           */}
        {/* ------------------------------------------------------------------ */}
        {petSubview !== null ? renderPetSubview() : (
          <>
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
                        Create Login &amp; Profile
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

                    {(formValues.creation_mode !== 'profile_only' || mode !== 'create') && (
                      <div className="field">
                        <label htmlFor="drawer-email">
                          Email {formValues.creation_mode !== 'profile_only' && <span aria-hidden="true">*</span>}
                        </label>
                        <input
                          id="drawer-email"
                          type="email"
                          value={formValues.email || ''}
                          onChange={(e) => setFormValues({ ...formValues, email: e.target.value })}
                          style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                        />
                      </div>
                    )}

                    <div className="field">
                      <label htmlFor="drawer-phone">Phone</label>
                      <input
                        id="drawer-phone"
                        type="tel"
                        value={formValues.phone || ''}
                        onChange={(e) => setFormValues({ ...formValues, phone: e.target.value })}
                        style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                      />
                    </div>

                    <div className="field">
                      <label htmlFor="drawer-address">Address</label>
                      <input
                        id="drawer-address"
                        type="text"
                        value={formValues.address || ''}
                        onChange={(e) => setFormValues({ ...formValues, address: e.target.value })}
                        style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                      />
                    </div>

                    <div className="field">
                      <label htmlFor="drawer-emergency">Emergency Contact</label>
                      <input
                        id="drawer-emergency"
                        type="text"
                        value={formValues.emergency_contact || ''}
                        onChange={(e) => setFormValues({ ...formValues, emergency_contact: e.target.value })}
                        style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem' }}
                      />
                    </div>

                    <div className="field">
                      <label htmlFor="drawer-notes">Notes</label>
                      <textarea
                        id="drawer-notes"
                        rows={3}
                        value={formValues.notes || ''}
                        onChange={(e) => setFormValues({ ...formValues, notes: e.target.value })}
                        style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid var(--border)', fontSize: '0.9rem', resize: 'vertical' }}
                      />
                    </div>

                    {mode === 'create' && formValues.creation_mode === 'onboard' && (
                      <div className="field" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <input
                          id="drawer-send-invite"
                          type="checkbox"
                          checked={formValues.send_invite !== false}
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
                      <button type="button" className="button-primary btn-small" onClick={onLinkExistingClientOnboard}>Link Existing</button>
                      <button type="button" className="button-secondary btn-small" onClick={() => setClientLinkPrompt(null)}>Cancel</button>
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
                    {vm.email && (<><dt>Email</dt><dd>{vm.email}</dd></>)}
                    {vm.phone && (<><dt>Phone</dt><dd>{vm.phone}</dd></>)}
                    {vm.address && (<><dt>Address</dt><dd>{vm.address}</dd></>)}
                    {vm.emergencyContact && (<><dt>Emergency Contact</dt><dd>{vm.emergencyContact}</dd></>)}
                    {vm.notes && (<><dt>Notes</dt><dd className="client-detail-notes">{vm.notes}</dd></>)}
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
                      <><dt>Login State</dt><dd>{vm.cognitoLifecycleLabel}</dd></>
                    )}
                  </dl>
                </section>

                {/* Section 3: Pets */}
                <section className="drawer-section">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                    <h4 className="drawer-section-title" style={{ margin: 0 }}>Pets</h4>
                    {canManagePets && !loadingPets && (
                      <button
                        type="button"
                        className="button-primary btn-small"
                        style={{ fontSize: '0.8rem', padding: '4px 10px' }}
                        onClick={openAddPet}
                      >
                        + Add Pet
                      </button>
                    )}
                  </div>

                  {loadingPets ? (
                    <p className="client-detail-empty" style={{ fontStyle: 'italic' }}>Loading pets…</p>
                  ) : pets && pets.length > 0 ? (
                    <ul className="client-drawer-pet-list" style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {pets.map((p, idx) => (
                        <li
                          key={p.pet_id || idx}
                          style={{ padding: '8px 12px', background: 'var(--bg-muted, #f8fafc)', borderRadius: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}
                        >
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <strong>{p.name || 'Unnamed'}</strong>
                            {p.species ? ` (${p.species})` : ''}
                            {p.breed ? ` — ${p.breed}` : ''}
                            {p.pet_id && (
                              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted, #64748b)', marginLeft: '8px', fontFamily: 'monospace' }}>
                                ID: …{p.pet_id.slice(-6)}
                              </span>
                            )}
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
                            {p.is_active === false ? (
                              <span className="access-badge status-offline" style={{ fontSize: '10px' }}>Archived</span>
                            ) : (
                              <span className="access-badge status-profile-active" style={{ fontSize: '10px' }}>Active</span>
                            )}
                            {canManagePets && (
                              <button
                                type="button"
                                className="btn-small"
                                style={{ fontSize: '0.75rem', padding: '2px 8px' }}
                                onClick={() => openViewPet(p)}
                              >
                                View
                              </button>
                            )}
                          </div>
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
                <button type="button" className="button-secondary" onClick={onCancel} disabled={isSaving}>
                  Cancel
                </button>
                <button type="submit" className="button-primary" disabled={isSaving}>
                  {isSaving ? 'Saving...' : (mode === 'create' ? 'Create Client' : 'Save Changes')}
                </button>
              </div>
            ) : (
              <div className="client-detail-drawer-footer" style={{ padding: '20px 24px', borderTop: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '12px', flexShrink: 0, backgroundColor: 'var(--card-bg)' }}>
                <h4 style={{ margin: 0, fontSize: '1rem', fontWeight: 600 }}>Actions</h4>

                <div className="btn-group" style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button type="button" className="button-primary btn-small" onClick={() => onEdit(client)}>
                    Edit Profile
                  </button>

                  {client.is_virtual ? (
                    <button type="button" className="btn-small" onClick={() => onCreateProfile(client)}>
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
                        <button type="button" className="btn-small secondary" onClick={() => onLinkEmail(client)}>
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
                          <button type="button" className="btn-small" onClick={() => onExecuteAction(client.client_id, 'enable')}>
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
                          <button type="button" className="btn-small" onClick={() => onExecuteAction(client.client_id, 'enable')}>
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
          </>
        )}
      </form>
    </div>,
    document.body
  );
};

export default ClientDetailDrawer;
