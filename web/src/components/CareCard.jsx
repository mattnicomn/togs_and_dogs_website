import React, { useState } from 'react';
import '../Portal.css';

const CareCard = ({ pet, onClose, onUpdate, onStatusUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState(pet._originItem?.status || '');
  const [statusNote, setStatusNote] = useState('');
  const [formData, setFormData] = useState({ 
    health: {}, 
    document_links: {}, 
    ...pet 
  });

  if (!pet) return null;

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    // Ensure nested objects are sent back
    onUpdate(formData);
    setIsEditing(false);
  };

  const handleCancel = () => {
    setFormData({ ...pet });
    setIsEditing(false);
  };

  return (
    <div className="care-card-overlay">
      <div className="care-card card">
        <header className="card-header-main">
          {isEditing ? (
            <div className="pet-identity editing">
              <div className="field-compact">
                <label>Pet Name</label>
                <input 
                  type="text" 
                  value={formData.name || ''} 
                  onChange={(e) => handleInputChange('name', e.target.value)}
                />
              </div>
              <div className="field-group-row">
                <div className="field-compact">
                  <label>Breed</label>
                  <input 
                    type="text" 
                    value={formData.breed || ''} 
                    onChange={(e) => handleInputChange('breed', e.target.value)}
                  />
                </div>
                <div className="field-compact slice">
                  <label>Age</label>
                  <input 
                    type="number" 
                    value={formData.age || ''} 
                    onChange={(e) => handleInputChange('age', parseInt(e.target.value) || 0)}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div className="pet-identity">
              {pet.photo_url ? (
                <img src={pet.photo_url} alt={pet.name} className="pet-avatar-large" />
              ) : (
                <div className="pet-placeholder-large">{pet.name?.[0]}</div>
              )}
              <div>
                <h2>{pet.name}</h2>
                <p className="subtitle">{pet.breed} • {pet.age} years old</p>
              </div>
            </div>
          )}
          <button className="close-button" onClick={onClose}>&times;</button>
        </header>

        <div className="card-grid">
          <section className="card-section health">
            <h3><span className="icon">💊</span> Health & Medications</h3>
            <div className="content-box">
              {isEditing ? (
                <div className="field">
                  <label>Care Instructions & Dosage</label>
                  <textarea 
                    rows="3"
                    value={formData.care_instructions || ''} 
                    onChange={(e) => handleInputChange('care_instructions', e.target.value)}
                    placeholder="Describe any medical needs or regular medications..."
                  />
                </div>
              ) : (
                <div className="info-display">
                  <p className="prominent-note">{pet.care_instructions || 'No specific care instructions provided.'}</p>
                </div>
              )}
              
              <div className="contact-actions" style={{ marginTop: '16px', borderTop: '1px solid var(--border-soft)', paddingTop: '12px' }}>
                <p><strong>Primary Vet:</strong> {pet.health?.vet_name || 'Not specified'}</p>
                {!isEditing && pet.health?.vet_phone && (
                  <a href={`tel:${pet.health.vet_phone}`} className="action-link tel">📞 Call Vet: {pet.health.vet_phone}</a>
                )}
              </div>
            </div>
          </section>

          <section className="card-section meet-greet">
            <h3><span className="icon">🤝</span> Meet & Greet Info</h3>
            <div className="content-box">
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                <span className={`status-chip ${pet.meet_and_greet_completed ? 'status-chip--ready' : 'status-chip--urgent'}`}>
                  {pet.meet_and_greet_completed ? '✓ Verified' : 'Pending Verification'}
                </span>
                <span className="micro-text">Status for {pet.name}</span>
              </div>
              <p className="small-text" style={{ color: 'var(--text-secondary)' }}>
                {pet.meet_and_greet_completed 
                  ? "Meet & Greet has been completed and verified by Ryan."
                  : "A Meet & Greet must be scheduled and verified before first service."}
              </p>
              {pet.admin_notes && (
                <div className="admin-note-box" style={{ background: 'var(--bg-muted)', padding: '12px', borderRadius: '8px', marginTop: '12px' }}>
                  <label className="micro-text">Staff Notes</label>
                  <p style={{ fontSize: '0.9rem', margin: '4px 0' }}>{pet.admin_notes}</p>
                </div>
              )}
            </div>
          </section>

          <section className="card-section behavior">
            <h3><span className="icon">🐾</span> Behavior & Personality</h3>
            <div className="content-box">
              {isEditing ? (
                <div className="field">
                  <label>Behavioral Notes & Triggers</label>
                  <textarea 
                    rows="3"
                    value={formData.behavior || ''} 
                    onChange={(e) => handleInputChange('behavior', e.target.value)}
                    placeholder="How do they react to other dogs, strangers, or loud noises?"
                  />
                </div>
              ) : (
                <p>{pet.behavior || 'No behavioral notes recorded yet.'}</p>
              )}
            </div>
          </section>

          <section className="card-section logistics">
            <h3><span className="icon">🔑</span> Access & Logistics</h3>
            <div className="content-box">
              {isEditing ? (
                <div className="field">
                  <label>Key Location / Gate Codes</label>
                  <textarea 
                    rows="3"
                    value={formData.logistics || ''} 
                    onChange={(e) => handleInputChange('logistics', e.target.value)}
                    placeholder="Where are the keys? Any gate or door codes?"
                  />
                </div>
              ) : (
                <p className="prominent-note">{pet.logistics || 'No access instructions provided.'}</p>
              )}
              
              <div className="contact-actions" style={{ marginTop: '16px', borderTop: '1px solid var(--border-soft)', paddingTop: '12px' }}>
                <p><strong>Emergency Contact:</strong> {pet.health?.emergency_name || 'Not specified'}</p>
                {!isEditing && pet.health?.emergency_phone && (
                  <a href={`tel:${pet.health.emergency_phone}`} className="action-link tel">📞 Call Emergency: {pet.health.emergency_phone}</a>
                )}
              </div>
            </div>
          </section>

          <section className="card-section records">
            <h3><span className="icon">📂</span> Ryan-Owned Records</h3>
              {isEditing ? (
                <div className="edit-links-grid">
                  <div className="field">
                    <label>Intake Form URL</label>
                    <input 
                      type="text" 
                      value={formData.document_links?.intake_form_url || ''} 
                      onChange={(e) => handleInputChange('document_links', { ...formData.document_links, intake_form_url: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>Vaccination Records URL</label>
                    <input 
                      type="text" 
                      value={formData.document_links?.vaccination_records_url || ''} 
                      onChange={(e) => handleInputChange('document_links', { ...formData.document_links, vaccination_records_url: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>Care Doc URL</label>
                    <input 
                      type="text" 
                      value={formData.document_links?.care_instructions_doc_url || ''} 
                      onChange={(e) => handleInputChange('document_links', { ...formData.document_links, care_instructions_doc_url: e.target.value })}
                    />
                  </div>
                </div>
              ) : (
                <div className="link-grid">
                  {pet.document_links?.intake_form_url && (
                    <a href={pet.document_links.intake_form_url} target="_blank" rel="noopener noreferrer" className="doc-link">Intake Form</a>
                  )}
                  {pet.document_links?.vaccination_records_url && (
                    <a href={pet.document_links.vaccination_records_url} target="_blank" rel="noopener noreferrer" className="doc-link">Vaccination Records</a>
                  )}
                  {pet.document_links?.care_instructions_doc_url && (
                    <a href={pet.document_links.care_instructions_doc_url} target="_blank" rel="noopener noreferrer" className="doc-link">Detailed Care Doc</a>
                  )}
                </div>
              )}
          </section>
          
          {pet._originItem && onStatusUpdate && (
            <section className="card-section admin-status">
              <h3><span className="icon">⚙️</span> Appointment Status</h3>
              <div className="content-box">
                <div className="field">
                  <label>Update Lifecycle Status</label>
                  <select 
                    value={selectedStatus} 
                    onChange={(e) => setSelectedStatus(e.target.value)}
                    className="status-select-admin"
                  >
                    <option value="PENDING_REVIEW">Intake (New)</option>
                    <option value="PROFILE_CREATED">Profile Created</option>
                    <option value="READY_FOR_APPROVAL">New Request</option>
                    <option value="APPROVED">Approved</option>
                    <option value="ASSIGNED">Scheduled</option>
                    <option value="IN_PROGRESS">In Progress</option>
                    <option value="COMPLETED">Completed</option>
                    <option value="CANCELLED">Cancelled</option>
                    <option value="ARCHIVED">Archived</option>
                    <option value="DELETED">Deleted (Soft)</option>
                  </select>
                </div>
                <div className="field">
                  <label>Note / Reason</label>
                  <textarea 
                    rows="2"
                    value={statusNote}
                    onChange={(e) => setStatusNote(e.target.value)}
                    placeholder="Enter reason for change (required for cancellation)..."
                  />
                </div>
                <button 
                  className="button-primary btn-small" 
                  style={{ width: '100%', marginTop: '0.5rem' }}
                  onClick={() => {
                    onStatusUpdate(pet._originItem, selectedStatus, statusNote);
                    setStatusNote('');
                  }}
                  disabled={selectedStatus === pet._originItem.status && !statusNote}
                >
                  Save Status Change
                </button>
              </div>
            </section>
          )}
        </div>

        <footer className="card-footer">
          <div className="status-meta">
            <span className={`badge-pill ${pet.meet_and_greet_completed ? 'success' : 'warning'}`}>
              {pet.meet_and_greet_completed ? 'Meet & Greet: Complete' : 'Meet & Greet: Required'}
            </span>
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
