import React, { useState } from 'react';

const CareCard = ({ pet, onClose, onUpdate }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState({ ...pet });

  if (!pet) return null;

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleSave = () => {
    if (!pet.pet_id) {
      alert("This pet does not have a saved profile yet. Approve or complete intake first.");
      return;
    }
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
                <div className="field">
                  <label>Behavioral Notes</label>
                  <textarea 
                    rows="3"
                    value={formData.behavior || ''} 
                    onChange={(e) => handleInputChange('behavior', e.target.value)}
                  />
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
                <div className="field">
                  <label>Access & Gate Codes</label>
                  <textarea 
                    rows="3"
                    value={formData.logistics || ''} 
                    onChange={(e) => handleInputChange('logistics', e.target.value)}
                  />
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
                className={`button-secondary ${!pet.pet_id ? 'disabled' : ''}`} 
                onClick={() => {
                  if (pet.pet_id) setIsEditing(true);
                  else alert("This pet does not have a saved profile yet. Approve or complete intake first.");
                }}
              >
                Edit Record
              </button>
            )}
          </div>
        </footer>
      </div>

      <style jsx>{`
        .care-card-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0,0,0,0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: 20px;
          backdrop-filter: blur(8px);
        }
        .care-card {
          width: 100%;
          max-width: 900px;
          max-height: 90vh;
          overflow-y: auto;
          background: var(--bg-surface);
          animation: slideUp 0.3s ease-out;
          color: var(--text-main);
          box-shadow: 0 24px 48px rgba(0,0,0,0.4);
          border: 1px solid var(--border-soft);
        }
        @keyframes slideUp {
          from { transform: translateY(30px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
        .card-header-main {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 24px;
          border-bottom: 1px solid var(--border-soft);
          padding-bottom: 20px;
        }
        .pet-identity {
          display: flex;
          align-items: center;
          gap: 20px;
        }
        .pet-identity.editing {
          flex-direction: column;
          align-items: flex-start;
          width: 80%;
          gap: 12px;
        }
        .field-compact {
          display: flex;
          flex-direction: column;
          gap: 4px;
          width: 100%;
        }
        .field-compact label {
          font-size: 0.75rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--text-muted);
          font-weight: 700;
        }
        .field-compact input {
          background: var(--bg-muted);
          border: 1px solid var(--border-soft);
          color: var(--text-main);
          padding: 8px 12px;
          border-radius: 6px;
          font-size: 1rem;
          font-weight: 600;
          width: 100%;
        }
        .field-group-row {
          display: flex;
          gap: 12px;
          width: 100%;
        }
        .field-compact.slice {
          width: 100px;
        }
        .pet-avatar-large {
          width: 80px;
          height: 80px;
          border-radius: 50%;
          object-fit: cover;
          border: 3px solid var(--primary);
        }
        .pet-placeholder-large {
          width: 80px;
          height: 80px;
          border-radius: 50%;
          background: var(--primary);
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 2rem;
          font-weight: 800;
        }
        .close-button {
          background: hsla(0,0%,100%,0.1);
          border: none;
          width: 40px;
          height: 40px;
          border-radius: 50%;
          font-size: 1.5rem;
          cursor: pointer;
          color: var(--text-heading);
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;
        }
        .close-button:hover { background: hsla(0,0%,100%,0.2); }
        .card-grid {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 24px;
        }
        @media (max-width: 768px) {
          .card-grid { grid-template-columns: 1fr; }
        }
        .card-section h3 {
          font-size: 1rem;
          margin-bottom: 12px;
          color: var(--text-muted);
          display: flex;
          align-items: center;
          gap: 8px;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .content-box {
          background: var(--bg-muted);
          padding: 16px;
          border-radius: 12px;
          font-size: 0.95rem;
          color: var(--text-main);
          border: 1px solid var(--border-soft);
        }
        .content-box textarea {
          width: 100%;
          background: var(--bg-surface);
          border: 1px solid var(--border-soft);
          color: var(--text-main);
          padding: 10px;
          border-radius: 8px;
          font-family: inherit;
          resize: vertical;
        }
        .contact-actions {
          margin-top: 12px;
          padding-top: 12px;
          border-top: 1px solid var(--border-soft);
        }
        .action-link {
          display: inline-block;
          margin-top: 8px;
          color: var(--primary);
          text-decoration: none;
          font-weight: 700;
          font-size: 0.9rem;
        }
        .link-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
        }
        .doc-link {
          padding: 8px 16px;
          background: var(--primary);
          color: white;
          border-radius: 8px;
          text-decoration: none;
          font-size: 0.85rem;
          font-weight: 600;
          transition: all 0.2s;
        }
        .doc-link:hover { opacity: 0.8; transform: translateY(-1px); }
        .card-footer {
          margin-top: 32px;
          padding-top: 24px;
          border-top: 1px solid var(--border-soft);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .footer-actions {
          display: flex;
          gap: 12px;
        }
        .button-secondary.disabled {
          opacity: 0.5;
          cursor: not-allowed;
          filter: grayscale(1);
        }
        .button-secondary.outline {
          background: transparent;
          border: 1px solid var(--border-soft);
        }
        .badge-pill {
          padding: 6px 16px;
          border-radius: 99px;
          font-size: 0.8rem;
          font-weight: 800;
          text-transform: uppercase;
          letter-spacing: 0.02em;
        }
        .badge-pill.success { background: hsla(142, 70%, 50%, 0.15); color: #22c55e; border: 1px solid hsla(142, 70%, 50%, 0.3); }
        .badge-pill.warning { background: hsla(0, 100%, 50%, 0.15); color: #ef4444; border: 1px solid hsla(0, 100%, 50%, 0.3); }
      `}</style>
    </div>
  );
};

export default CareCard;
