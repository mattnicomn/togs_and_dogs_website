import React, { useState } from 'react';
import '../Portal.css';

const CareCard = ({ pet, onClose, onUpdate, onStatusUpdate, userRole }) => {

  const [isEditing, setIsEditing] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState((pet._originItem?.status || '').toUpperCase());
  const [statusNote, setStatusNote] = useState('');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);
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

    // If status was changed in the dropdown but the user clicked the main Save button, 
    // trigger the status update as well to meet user expectations.
    if (pet._originItem && onStatusUpdate && selectedStatus !== pet._originItem.status) {
      onStatusUpdate(pet._originItem, selectedStatus, statusNote || "Status updated via record edit.");
    }

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
                <div className="edit-fields-stack">
                  <div className="field">
                    <label>Care Instructions & Dosage</label>
                    <textarea 
                      rows="2"
                      value={formData.care_instructions || ''} 
                      onChange={(e) => handleInputChange('care_instructions', e.target.value)}
                      placeholder="Describe any medical needs..."
                    />
                  </div>
                  <div className="field">
                    <label>Primary Vet Notes</label>
                    <textarea 
                      rows="2"
                      value={formData.health?.vet_notes || ''} 
                      onChange={(e) => handleInputChange('health', { ...formData.health, vet_notes: e.target.value })}
                      placeholder="Special instructions for the vet..."
                    />
                  </div>
                  <div className="field-group-row">
                    <div className="field-compact">
                      <label>Vet Name</label>
                      <input 
                        type="text" 
                        value={formData.health?.vet_name || ''} 
                        onChange={(e) => handleInputChange('health', { ...formData.health, vet_name: e.target.value })}
                      />
                    </div>
                    <div className="field-compact">
                      <label>Vet Phone</label>
                      <input 
                        type="text" 
                        value={formData.health?.vet_phone || ''} 
                        onChange={(e) => handleInputChange('health', { ...formData.health, vet_phone: e.target.value })}
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="info-display">
                  <p className="prominent-note">{pet.care_instructions || 'No specific care instructions provided.'}</p>
                  {pet.health?.vet_notes && (
                    <div className="sub-note">
                      <strong>Vet Notes:</strong> {pet.health.vet_notes}
                    </div>
                  )}
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
              {isEditing ? (
                <div className="edit-fields-stack">
                  <div className="field-checkbox">
                    <input 
                      type="checkbox" 
                      id="mg_required"
                      checked={formData.meet_and_greet_required !== false} // Default to true
                      onChange={(e) => handleInputChange('meet_and_greet_required', e.target.checked)}
                    />
                    <label htmlFor="mg_required">Meet & Greet Required</label>
                  </div>
                  <div className="field">
                    <label>Scheduled Date/Time</label>
                    <input 
                      type="datetime-local" 
                      value={formData.meet_and_greet_scheduled_at || ''} 
                      onChange={(e) => handleInputChange('meet_and_greet_scheduled_at', e.target.value)}
                    />
                  </div>
                  <div className="field-checkbox">
                    <input 
                      type="checkbox" 
                      id="mg_completed"
                      checked={formData.meet_and_greet_completed || false} 
                      onChange={(e) => handleInputChange('meet_and_greet_completed', e.target.checked)}
                    />
                    <label htmlFor="mg_completed">M&G Completed</label>
                  </div>
                  {formData.meet_and_greet_completed && (
                    <div className="field">
                      <label>Completion Date</label>
                      <input 
                        type="date" 
                        value={formData.meet_and_greet_completed_at || ''} 
                        onChange={(e) => handleInputChange('meet_and_greet_completed_at', e.target.value)}
                      />
                    </div>
                  )}
                  {userRole !== 'staff' && (
                    <div className="field">
                      <label>M&G Staff Notes</label>
                      <textarea 
                        rows="2"
                        value={formData.meet_and_greet_notes || ''} 
                        onChange={(e) => handleInputChange('meet_and_greet_notes', e.target.value)}
                      />
                    </div>
                  )}

                </div>
              ) : (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                    <span className={`status-chip ${pet.meet_and_greet_completed ? 'status-chip--ready' : (pet.meet_and_greet_required === false ? 'status-chip--profile' : 'status-chip--urgent')}`}>
                      {pet.meet_and_greet_completed ? '✓ Verified' : (pet.meet_and_greet_required === false ? 'Not Required' : 'Required')}
                    </span>
                    <span className="micro-text">Status for {pet.name}</span>
                  </div>
                  <p className="small-text" style={{ color: 'var(--text-secondary)' }}>
                    {pet.meet_and_greet_completed 
                      ? `Completed on ${pet.meet_and_greet_completed_at || 'record'}.`
                      : pet.meet_and_greet_required === false ? "No M&G necessary for this client." : "Must be completed before first service."}
                  </p>
                  {userRole !== 'staff' && pet.meet_and_greet_notes && (
                    <div className="admin-note-box" style={{ background: 'var(--bg-muted)', padding: '12px', borderRadius: '8px', marginTop: '12px' }}>
                      <label className="micro-text">M&G Notes</label>
                      <p style={{ fontSize: '0.9rem', margin: '4px 0' }}>{pet.meet_and_greet_notes}</p>
                    </div>
                  )}

                </>
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
                <div className="edit-fields-stack">
                  <div className="field">
                    <label>Key Location / Gate Codes</label>
                    <textarea 
                      rows="2"
                      value={formData.logistics || ''} 
                      onChange={(e) => handleInputChange('logistics', e.target.value)}
                      placeholder="Where are the keys? Any gate or door codes?"
                    />
                  </div>
                  <div className="field-group-row">
                    <div className="field-compact">
                      <label>Emergency Name</label>
                      <input 
                        type="text" 
                        value={formData.health?.emergency_name || ''} 
                        onChange={(e) => handleInputChange('health', { ...formData.health, emergency_name: e.target.value })}
                      />
                    </div>
                    <div className="field-compact">
                      <label>Emergency Phone</label>
                      <input 
                        type="text" 
                        value={formData.health?.emergency_phone || ''} 
                        onChange={(e) => handleInputChange('health', { ...formData.health, emergency_phone: e.target.value })}
                      />
                    </div>
                  </div>
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

          <section className="card-section quote">
            <h3><span className="icon">💰</span> Quote & Pricing</h3>
            <div className="content-box">
              {isEditing ? (
                <div className="edit-fields-stack">
                  <div className="field-group-row">
                    <div className="field-compact">
                      <label>Quote Amount ($)</label>
                      <input 
                        type="number" 
                        value={formData.quote_amount || ''} 
                        onChange={(e) => handleInputChange('quote_amount', parseFloat(e.target.value) || 0)}
                      />
                    </div>
                    <div className="field-compact">
                      <label>Deposit Required ($)</label>
                      <input 
                        type="number" 
                        value={formData.deposit_required || ''} 
                        onChange={(e) => handleInputChange('deposit_required', parseFloat(e.target.value) || 0)}
                      />
                    </div>
                  </div>
                  <div className="field">
                    <label>Payment Status</label>
                    <select 
                      value={formData.payment_status || 'Not Quoted'} 
                      onChange={(e) => handleInputChange('payment_status', e.target.value)}
                    >
                      <option value="Not Quoted">Not Quoted</option>
                      <option value="Quote Needed">Quote Needed</option>
                      <option value="Quote Sent">Quote Sent</option>
                      <option value="Accepted">Accepted</option>
                      <option value="Declined">Declined</option>
                      <option value="Deposit Paid">Deposit Paid</option>
                      <option value="Paid in Full">Paid in Full</option>
                    </select>
                  </div>
                  <div className="field-group-row">
                    <div className="field-compact">
                      <label>Sent Date</label>
                      <input 
                        type="date" 
                        value={formData.quote_sent_date || ''} 
                        onChange={(e) => handleInputChange('quote_sent_date', e.target.value)}
                      />
                    </div>
                    <div className="field-compact">
                      <label>Accepted Date</label>
                      <input 
                        type="date" 
                        value={formData.quote_accepted_date || ''} 
                        onChange={(e) => handleInputChange('quote_accepted_date', e.target.value)}
                      />
                    </div>
                  </div>
                  {userRole !== 'staff' && (
                    <div className="field">
                      <label>Internal Pricing Notes</label>
                      <textarea 
                        rows="2"
                        value={formData.internal_pricing_notes || ''} 
                        onChange={(e) => handleInputChange('internal_pricing_notes', e.target.value)}
                      />
                    </div>
                  )}

                </div>
              ) : (
                <div className="quote-display">
                  <div className="price-row">
                    <span className="price-label">Quote Amount:</span>
                    <span className="price-value">${pet.quote_amount || '0.00'}</span>
                  </div>
                  <div className="price-row">
                    <span className="price-label">Status:</span>
                    <span className={`status-pill ${pet.payment_status?.toLowerCase().replace(/ /g, '-') || 'not-quoted'}`}>
                      {pet.payment_status || 'Not Quoted'}
                    </span>
                  </div>
                  {pet.quote_sent_date && <p className="micro-text">Sent on: {pet.quote_sent_date}</p>}
                </div>
              )}
            </div>
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
                    <optgroup label="Quoting">
                      <option value="QUOTE_NEEDED">Quote Needed</option>
                      <option value="QUOTE_SENT">Quote Sent</option>
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
                      <option value="DELETED">Deleted (Soft)</option>
                    </optgroup>
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
                  {isUpdatingStatus ? 'Updating...' : 'Save Status Change'}
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
