import React, { useState } from 'react';
import '../Portal.css';

const CareCard = ({ pet, onClose, onUpdate, onStatusUpdate, userRole }) => {
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

  const handleSave = () => {
    onUpdate(formData);
    if (pet._originItem && onStatusUpdate && selectedStatus !== pet._originItem.status) {
      onStatusUpdate(pet._originItem, selectedStatus, statusNote || "Status updated via record edit.");
    }
    setIsEditing(false);
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
              {pet.photo_url ? (
                <img src={pet.photo_url} alt={pet.name} className="pet-avatar-large" />
              ) : (
                <div className="pet-placeholder-large">{pet.name?.[0]}</div>
              )}
              <div>
                <h2>{isEditing ? <input value={formData.name || ''} onChange={e => handleInputChange('name', e.target.value)} className="form-control-inline" /> : pet.name}</h2>
                <p className="subtitle">
                  {isEditing ? (
                    <span className="edit-inline-group">
                      <input value={formData.breed || ''} onChange={e => handleInputChange('breed', e.target.value)} placeholder="Breed" />
                      <input type="number" value={formData.age || ''} onChange={e => handleInputChange('age', parseInt(e.target.value))} placeholder="Age" />
                    </span>
                  ) : `${pet.breed || 'Unknown Breed'} • ${pet.age || '?'} years old`}
                </p>
              </div>
            </div>
            
            <div className="summary-cards" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '32px' }}>
              <div className="content-box">
                <h4>Health Summary</h4>
                <p>{pet.care_instructions || 'No specific instructions.'}</p>
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
                  <p>{pet.visit_window || 'ANYTIME'}</p>
                </div>
              </div>
            </section>
          </div>
        );

      case 'care':
        return (
          <div className="tab-content">
            <section className="card-section">
              <h3>Behavior & Personality</h3>
              <div className="content-box">
                {isEditing ? (
                  <textarea rows="4" value={formData.behavior || ''} onChange={e => handleInputChange('behavior', e.target.value)} />
                ) : <p>{pet.behavior || 'No behavioral notes.'}</p>}
              </div>
            </section>
            <section className="card-section" style={{ marginTop: '24px' }}>
              <h3>Care Instructions</h3>
              <div className="content-box">
                {isEditing ? (
                  <textarea rows="4" value={formData.care_instructions || ''} onChange={e => handleInputChange('care_instructions', e.target.value)} />
                ) : <p>{pet.care_instructions || 'No specific instructions.'}</p>}
              </div>
            </section>
          </div>
        );

      case 'emergency':
        return (
          <div className="tab-content">
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
                      <p><strong>{pet.health?.vet_name || 'Not specified'}</strong></p>
                      {pet.health?.vet_phone && <a href={`tel:${pet.health.vet_phone}`} className="action-link">📞 {pet.health.vet_phone}</a>}
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
                      <p><strong>{pet.health?.emergency_name || 'Not specified'}</strong></p>
                      {pet.health?.emergency_phone && <a href={`tel:${pet.health.emergency_phone}`} className="action-link">📞 {pet.health.emergency_phone}</a>}
                    </>
                  )}
                </div>
              </section>
            </div>
            <section className="card-section" style={{ marginTop: '24px' }}>
              <h3>Logistics & Access</h3>
              <div className="content-box">
                {isEditing ? (
                  <textarea rows="3" value={formData.logistics || ''} onChange={e => handleInputChange('logistics', e.target.value)} placeholder="Key location, codes, etc." />
                ) : <p className="prominent-note">{pet.logistics || 'No access instructions.'}</p>}
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
                    <p className="price-large">${pet.quote_amount || '0.00'}</p>
                  </div>
                  <div className="price-display">
                    <label className="micro-text">Payment Status</label>
                    <p><strong>{pet.payment_status || 'Not Quoted'}</strong></p>
                  </div>
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
                <p><strong>Assigned To:</strong> {pet.worker_name || pet.worker_id || 'Unassigned'}</p>
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
            <h1 className="serif">{pet.name || 'Record Detail'}</h1>
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
