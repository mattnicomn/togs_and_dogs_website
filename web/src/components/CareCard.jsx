import React, { useState, useEffect } from 'react';
import '../Portal.css';

const CareCard = ({ pet, onClose, onUpdate, onStatusUpdate, userRole, staffList = [], onAssign }) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [isEditing, setIsEditing] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState((pet._originItem?.status || '').toUpperCase());
  const [statusNote, setStatusNote] = useState('');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
  const [formData, setFormData] = useState({ 
    health: {}, 
    document_links: {}, 
    scheduled_duration: 60,
    ...pet 
  });

  // Release 4E: Staff assignment state
  const [isAssigning, setIsAssigning] = useState(false);

  // Release 4B: Multi-pet support — track which pet is selected
  const allPets = (pet._allPets && pet._allPets.length > 0) ? pet._allPets : [pet];
  const [activePetIndex, setActivePetIndex] = useState(0);
  const activePet = allPets[activePetIndex] || pet;
  const hasMultiplePets = allPets.length > 1;

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
      await onUpdate(formData);
      if (pet._originItem && onStatusUpdate && selectedStatus !== pet._originItem.status) {
        await onStatusUpdate(pet._originItem, selectedStatus, statusNote || "Status updated via record edit.");
      }
      setIsEditing(false);
    } catch (e) {
      console.error(e);
    }
  };

  const handleCancel = () => {
    setFormData({ ...pet });
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
          {/* Release 4B: Multi-pet selector — Visible across all relevant tabs */}
          {hasMultiplePets && ['overview', 'care', 'emergency'].includes(activeTab) && (
            <div className="pet-selector-nav" style={{ 
              display: 'flex', gap: '8px', padding: '16px 24px', 
              background: 'var(--bg-muted)', borderBottom: '1px solid var(--border-soft)',
              flexWrap: 'wrap' 
            }}>
              {allPets.map((p, idx) => (
                <button
                  key={idx}
                  onClick={() => setActivePetIndex(idx)}
                  className={`pet-chip ${idx === activePetIndex ? 'active' : ''}`}
                  style={{
                    padding: '6px 14px', borderRadius: '16px', border: 'none', cursor: 'pointer',
                    backgroundColor: idx === activePetIndex ? 'var(--primary)' : 'transparent',
                    color: idx === activePetIndex ? '#fff' : 'var(--text-primary)',
                    border: idx === activePetIndex ? 'none' : '1px solid var(--border)',
                    fontSize: '0.85rem', fontWeight: idx === activePetIndex ? '600' : '400',
                    transition: 'all 0.15s ease'
                  }}
                >
                  {p.name || p.pet_name || `Pet ${idx + 1}`}
                </button>
              ))}
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
             <p className="micro-text">Client ID: {pet.client_id}</p>
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
              >
                {pet.pet_id ? 'Edit Record' : 'Create Profile'}
              </button>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
};

export default CareCard;
