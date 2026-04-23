import React, { useState } from 'react';
import '../Portal.css';

const CareCard = ({ pet, onClose, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
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
                  />
                </div>
              ) : (
                <p><strong>Instructions/Dosage:</strong> {pet.care_instructions || 'N/A'}</p>
              )}
              
              <div className="contact-actions">
                <p><strong>Vet:</strong> {pet.health?.vet_name || 'N/A'}</p>
                {!isEditing && pet.health?.vet_phone && (
                  <a href={`tel:${pet.health.vet_phone}`} className="action-link tel">📞 Call Vet: {pet.health.vet_phone}</a>
                )}
              </div>
            </div>
          </section>

          <section className="card-section behavior">
            <h3><span className="icon">🐾</span> Behavior & Triggers</h3>
            <div className="content-box">
              {isEditing ? (
                <div className="field-group">
                  <div className="field">
                    <label>Behavioral Notes</label>
                    <textarea 
                      rows="3"
                      value={formData.behavior || ''} 
                      onChange={(e) => handleInputChange('behavior', e.target.value)}
                    />
                  </div>
                  <div className="field-row">
                    <div className="field">
                      <label>Vet Name</label>
                      <input 
                        type="text" 
                        value={formData.health?.vet_name || ''} 
                        onChange={(e) => handleInputChange('health', { ...formData.health, vet_name: e.target.value })}
                      />
                    </div>
                    <div className="field">
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
                <p>{pet.behavior || 'No behavioral notes recorded.'}</p>
              )}
            </div>
          </section>

          <section className="card-section logistics">
            <h3><span className="icon">🔑</span> Access & Logistics</h3>
            <div className="content-box">
              {isEditing ? (
                <div className="field-group">
                  <div className="field">
                    <label>Access & Gate Codes</label>
                    <textarea 
                      rows="3"
                      value={formData.logistics || ''} 
                      onChange={(e) => handleInputChange('logistics', e.target.value)}
                    />
                  </div>
                  <div className="field-row">
                    <div className="field">
                      <label>Emergency Contact</label>
                      <input 
                        type="text" 
                        value={formData.health?.emergency_name || ''} 
                        onChange={(e) => handleInputChange('health', { ...formData.health, emergency_name: e.target.value })}
                      />
                    </div>
                    <div className="field">
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
                <p>{pet.logistics || 'No specific access notes.'}</p>
              )}
              
              <div className="contact-actions">
                <p><strong>Emergency Contact:</strong> {pet.health?.emergency_name || 'N/A'}</p>
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
